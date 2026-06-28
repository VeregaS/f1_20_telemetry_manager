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
        
        self.current_session_id: int | None = None
        self.current_session_uid: int | None = None
        self.current_lap_id: int | None = None
        self.current_lap_num: int = 0
        self.current_lap_distance: float = 0.0
        
        self.telemetry_buffer: list[dict] = []
        self.BATCH_SIZE: int = 600

    async def run(self):
        logger.info("Менеджер состояния запущен.")
        loop = asyncio.get_running_loop()
        
        while True:
            data = await self.queue.get()
            parsed_data = process_packet(data)
            
            if parsed_data is None:
                self.queue.task_done()
                continue
                
            if isinstance(parsed_data, ParsedSession):
                await loop.run_in_executor(self.executor, self._handle_session, parsed_data)
            elif isinstance(parsed_data, ParsedLap):
                await loop.run_in_executor(self.executor, self._handle_lap, parsed_data)
            elif isinstance(parsed_data, ParsedTelemetry):
                self._handle_telemetry(parsed_data)
                
                if len(self.telemetry_buffer) >= self.BATCH_SIZE:
                    buffer_copy = self.telemetry_buffer.copy()
                    self.telemetry_buffer.clear()
                    await loop.run_in_executor(self.executor, self._flush_telemetry, buffer_copy)
                    
            self.queue.task_done()

    def _handle_session(self, session_data: ParsedSession):
        with SessionLocal() as db:
            if self.current_session_uid != session_data.session_uid:
                new_session = Session(
                    track_id=session_data.track_id,
                    session_type=session_data.session_type
                )
                db.add(new_session)
                db.commit()
                self.current_session_id = new_session.id
                self.current_session_uid = session_data.session_uid
                
                self.current_lap_id = None
                self.current_lap_num = 0
                self.current_lap_distance = 0.0
                
                logger.info(f"Создана новая сессия: ID {self.current_session_id}, UID {self.current_session_uid}")

    def _handle_lap(self, lap_data: ParsedLap):
        if not self.current_session_id:
            return

        self.current_lap_distance = lap_data.lap_distance

        with SessionLocal() as db:
            if self.current_lap_id is None or lap_data.lap_number != self.current_lap_num:
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
            
            elif self.current_lap_id:
                lap_record = db.query(Lap).filter(Lap.id == self.current_lap_id).first()
                if lap_record:
                    lap_record.lap_time_ms = lap_data.current_lap_time_ms
                    lap_record.sector1_ms = lap_data.sector1_ms
                    lap_record.sector2_ms = lap_data.sector2_ms
                    lap_record.is_valid = lap_data.is_valid
                    db.commit()

    def _handle_telemetry(self, telemetry_data: ParsedTelemetry):
        if not self.current_lap_id:
            return
            
        self.telemetry_buffer.append({
            "lap_id": self.current_lap_id,
            "lap_distance": self.current_lap_distance,
            "speed": telemetry_data.speed,
            "throttle": telemetry_data.throttle,
            "brake": telemetry_data.brake,
            "gear": telemetry_data.gear,
            "steer": telemetry_data.steer
        })

    def _flush_telemetry(self, buffer: list):
        if not buffer:
            return
        try:
            with SessionLocal() as db:
                db.bulk_insert_mappings(TelemetryData, buffer)
                db.commit()
        except Exception as e:
            logger.error(f"Ошибка при записи телеметрии: {e}")