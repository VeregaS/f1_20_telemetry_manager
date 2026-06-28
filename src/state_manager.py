import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session as DBSession

from src.parser import process_packet, ParsedSession, ParsedLap, ParsedTelemetry
from src.database import SessionLocal
from src.models import Session, Lap, TelemetryData

logger = logging.getLogger(__name__)

class TelemetryStateManager:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Внутреннее состояние
        self.current_session_id = None
        self.current_lap_id = None
        self.current_lap_num = 0
        
        # Буфер для пакетной вставки
        self.telemetry_buffer = []
        self.BATCH_SIZE = 600  # Примерно 10 секунд при частоте 60 Гц

    async def run(self):
        """Основной цикл обработки очереди пакетов."""
        logger.info("Менеджер состояния запущен.")
        loop = asyncio.get_running_loop()
        
        while True:
            data = await self.queue.get()
            parsed_data = process_packet(data)
            
            if parsed_data is None:
                self.queue.task_done()
                continue
                
            # Маршрутизация обработчиков в зависимости от типа данных
            if isinstance(parsed_data, ParsedSession):
                await loop.run_in_executor(self.executor, self._handle_session, parsed_data)
            elif isinstance(parsed_data, ParsedLap):
                await loop.run_in_executor(self.executor, self._handle_lap, parsed_data)
            elif isinstance(parsed_data, ParsedTelemetry):
                self._handle_telemetry(parsed_data)
                
                # Сброс буфера по достижении лимита
                if len(self.telemetry_buffer) >= self.BATCH_SIZE:
                    buffer_copy = self.telemetry_buffer.copy()
                    self.telemetry_buffer.clear()
                    await loop.run_in_executor(self.executor, self._flush_telemetry, buffer_copy)
                    
            self.queue.task_done()

    def _handle_session(self, session_data: ParsedSession):
        """Создание новой сессии в БД при ее отсутствии."""
        with SessionLocal() as db:
            # Упрощенная логика: если сессии нет, создаем. 
            # Для надежности в F1 2020 лучше сверять m_sessionUID из заголовка.
            if self.current_session_id is None:
                new_session = Session(
                    track_id=session_data.track_id,
                    session_type=session_data.session_type
                )
                db.add(new_session)
                db.commit()
                self.current_session_id = new_session.id
                logger.info(f"Создана новая сессия: ID {self.current_session_id}")

    def _handle_lap(self, lap_data: ParsedLap):
        """Обработка смены круга и обновление данных текущего круга."""
        if not self.current_session_id:
            return

        with SessionLocal() as db:
            # Инициализация первого круга или смена круга
            if self.current_lap_id is None or lap_data.lap_number != self.current_lap_num:
                # Принудительный сброс остатков буфера предыдущего круга
                if self.telemetry_buffer:
                    self._flush_telemetry(self.telemetry_buffer.copy())
                    self.telemetry_buffer.clear()

                new_lap = Lap(
                    session_id=self.current_session_id,
                    lap_number=lap_data.lap_number
                )
                db.add(new_lap)
                db.commit()
                self.current_lap_id = new_lap.id
                self.current_lap_num = lap_data.lap_number
                logger.info(f"Начат круг {self.current_lap_num} (ID: {self.current_lap_id})")
            
            # Обновление времен секторов и валидности для текущего круга
            elif self.current_lap_id:
                lap_record = db.query(Lap).filter(Lap.id == self.current_lap_id).first()
                if lap_record:
                    lap_record.lap_time_ms = lap_data.current_lap_time_ms
                    lap_record.sector1_ms = lap_data.sector1_ms
                    lap_record.sector2_ms = lap_data.sector2_ms
                    lap_record.is_valid = lap_data.is_valid
                    db.commit()

    def _handle_telemetry(self, telemetry_data: ParsedTelemetry):
        """Добавление метрик в буфер оперативной памяти."""
        if not self.current_lap_id:
            return
            
        # Формируем словарь для bulk_insert_mappings (значительно быстрее построчного ORM)
        self.telemetry_buffer.append({
            "lap_id": self.current_lap_id,
            "lap_distance": 0.0, # Внимание: lap_distance необходимо передать из ParsedLap. В данном примере для консистентности потребуется небольшая модификация parser.py или кэширование дистанции.
            "speed": telemetry_data.speed,
            "throttle": telemetry_data.throttle,
            "brake": telemetry_data.brake,
            "gear": telemetry_data.gear,
            "steer": telemetry_data.steer
        })

    def _flush_telemetry(self, buffer: list):
        """Синхронная пакетная запись в БД."""
        if not buffer:
            return
        try:
            with SessionLocal() as db:
                db.bulk_insert_mappings(TelemetryData, buffer)
                db.commit()
        except Exception as e:
            logger.error(f"Ошибка при записи телеметрии: {e}")