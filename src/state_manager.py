import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from src.parser import process_packet, ParsedSession, ParsedLap, ParsedTelemetry
from src.database import SessionLocal
from src.models import Session, Lap, TelemetryData

logger = logging.getLogger(__name__)

class TelemetryStateManager:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        self.current_session_id = None
        self.current_session_uid = None
        self.current_lap_id = None
        self.current_lap_num = 0
        self.current_lap_distance = 0.0
        
        self.telemetry_buffer = []
        self.BATCH_SIZE = 50  # <--- СНИЗИЛИ для быстрой проверки

    async def run(self):
        logger.info("Менеджер состояния запущен.")
        while True:
            data = await self.queue.get()
            parsed_data = process_packet(data)
            
            if parsed_data:
                logger.info(f"Получен пакет типа: {type(parsed_data).__name__}") # Раскомментируйте это, если нужно увидеть тип каждого пакета
                if isinstance(parsed_data, ParsedSession):
                    self._handle_session(parsed_data)
                elif isinstance(parsed_data, ParsedLap):
                    self._handle_lap(parsed_data)
                elif isinstance(parsed_data, ParsedTelemetry):
                    self._handle_telemetry(parsed_data)
            
            self.queue.task_done()

    def _handle_session(self, session_data):
        with SessionLocal() as db:
            if self.current_session_uid != session_data.session_uid:
                new_session = Session(track_id=session_data.track_id, session_type=session_data.session_type)
                db.add(new_session)
                db.commit()
                self.current_session_id = new_session.id
                self.current_session_uid = session_data.session_uid
                logger.info(f"Сессия {self.current_session_id} создана.")

    def _handle_lap(self, lap_data: ParsedLap):
        if not self.current_session_id:
            return

        # ИСПРАВЛЕНИЕ: Мы должны брать дистанцию из пакета круга
        self.current_lap_distance = lap_data.lap_distance

        with SessionLocal() as db:
            existing_lap = db.query(Lap).filter(
                Lap.session_id == self.current_session_id,
                Lap.lap_number == lap_data.lap_number
            ).first()

            if existing_lap:
                self.current_lap_id = existing_lap.id
            else:
                new_lap = Lap(session_id=self.current_session_id, lap_number=lap_data.lap_number)
                db.add(new_lap)
                db.commit()
                db.refresh(new_lap)
                self.current_lap_id = new_lap.id
                logger.info(f"--- НОВЫЙ КРУГ {lap_data.lap_number} (ID: {self.current_lap_id}) ---")

            lap_record = db.query(Lap).get(self.current_lap_id)
            if lap_record and lap_data.current_lap_time_ms > 0:
                lap_record.lap_time_ms = lap_data.current_lap_time_ms
                db.commit()
                
            self.current_lap_num = lap_data.lap_number

    def _handle_telemetry(self, telemetry_data: ParsedTelemetry):
        if not self.current_lap_id: return
        
        # Защита: не пишем телеметрию, если машина стоит (скорость 0)
        if telemetry_data.speed == 0 and self.current_lap_distance == 0:
            return
            
        self.telemetry_buffer.append({
            "lap_id": self.current_lap_id,
            "lap_distance": self.current_lap_distance, # Теперь здесь будут реальные данные
            "speed": telemetry_data.speed,
            "throttle": telemetry_data.throttle,
            "brake": telemetry_data.brake,
            "gear": telemetry_data.gear,
            "steer": telemetry_data.steer
        })
        
        if len(self.telemetry_buffer) >= self.BATCH_SIZE:
            self._flush_telemetry()

    def _flush_telemetry(self):
        if not self.telemetry_buffer: 
            return
        try:
            with SessionLocal() as db:
                db.bulk_insert_mappings(TelemetryData, self.telemetry_buffer)
                db.commit()
            logger.info(f"УСПЕХ: В БД записано {len(self.telemetry_buffer)} точек телеметрии для LapID {self.current_lap_id}")
            self.telemetry_buffer.clear()
        except Exception as e:
            logger.error(f"Ошибка записи в БД: {e}")