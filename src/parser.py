import ctypes
from dataclasses import dataclass
from typing import Optional, Union

# --- CTYPES СТРУКТУРЫ (F1 2020 UDP Specification) ---

class PacketHeader(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_packetFormat", ctypes.c_uint16),
        ("m_gameMajorVersion", ctypes.c_uint8),
        ("m_gameMinorVersion", ctypes.c_uint8),
        ("m_packetVersion", ctypes.c_uint8),
        ("m_packetId", ctypes.c_uint8),
        ("m_sessionUID", ctypes.c_uint64),
        ("m_sessionTime", ctypes.c_float),
        ("m_frameIdentifier", ctypes.c_uint32),
        ("m_playerCarIndex", ctypes.c_uint8),
        ("m_secondaryPlayerCarIndex", ctypes.c_uint8),
    ]

class PacketSessionData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_weather", ctypes.c_uint8),
        ("m_trackTemperature", ctypes.c_int8),
        ("m_trackTemperatureChange", ctypes.c_int8),
        ("m_airTemperature", ctypes.c_int8),
        ("m_airTemperatureChange", ctypes.c_int8),
        ("m_totalLaps", ctypes.c_uint8),
        ("m_trackLength", ctypes.c_uint16),
        ("m_sessionType", ctypes.c_uint8),
        ("m_trackId", ctypes.c_int8),
        # Остальные поля опущены для экономии памяти, так как они не требуются в БД
    ]

class LapData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_lastLapTime", ctypes.c_float),
        ("m_currentLapTime", ctypes.c_float),
        ("m_sector1TimeInMS", ctypes.c_uint16),
        ("m_sector2TimeInMS", ctypes.c_uint16),
        ("m_bestLapTime", ctypes.c_float),
        ("m_bestLapNum", ctypes.c_uint8),
        ("m_bestSector1TimeInMS", ctypes.c_uint16),
        ("m_bestSector2TimeInMS", ctypes.c_uint16),
        ("m_bestSector3TimeInMS", ctypes.c_uint16),
        ("m_bestLapSector1TimeInMS", ctypes.c_uint16),
        ("m_bestLapSector2TimeInMS", ctypes.c_uint16),
        ("m_bestLapSector3TimeInMS", ctypes.c_uint16),
        ("m_lapDistance", ctypes.c_float),
        ("m_totalDistance", ctypes.c_float),
        ("m_safetyCarDelta", ctypes.c_float),
        ("m_carPosition", ctypes.c_uint8),
        ("m_currentLapNum", ctypes.c_uint8),
        ("m_pitStatus", ctypes.c_uint8),
        ("m_sector", ctypes.c_uint8),
        ("m_currentLapInvalid", ctypes.c_uint8),
        ("m_penalties", ctypes.c_uint8),
        ("m_gridPosition", ctypes.c_uint8),
        ("m_driverStatus", ctypes.c_uint8),
        ("m_resultStatus", ctypes.c_uint8),
    ]

class PacketLapData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_lapData", LapData * 22),
    ]

class CarTelemetryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_speed", ctypes.c_uint16),
        ("m_throttle", ctypes.c_float),
        ("m_steer", ctypes.c_float),
        ("m_brake", ctypes.c_float),
        ("m_clutch", ctypes.c_uint8),
        ("m_gear", ctypes.c_int8),
        ("m_engineRPM", ctypes.c_uint16),
        ("m_drs", ctypes.c_uint8),
        ("m_revLightsPercent", ctypes.c_uint8),
        ("m_brakesTemperature", ctypes.c_uint16 * 4),
        ("m_tyresSurfaceTemperature", ctypes.c_uint8 * 4),
        ("m_tyresInnerTemperature", ctypes.c_uint8 * 4),
        ("m_engineTemperature", ctypes.c_uint16),
        ("m_tyresPressure", ctypes.c_float * 4),
        ("m_surfaceType", ctypes.c_uint8 * 4),
    ]

class PacketCarTelemetryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carTelemetryData", CarTelemetryData * 22),
        ("m_buttonStatus", ctypes.c_uint32),
        ("m_mfdPanelIndex", ctypes.c_uint8),
        ("m_mfdPanelIndexSecondaryPlayer", ctypes.c_uint8),
        ("m_suggestedGear", ctypes.c_int8),
    ]


# --- ИММУТАБЕЛЬНЫЕ СТРУКТУРЫ ДАННЫХ (Для передачи в БД) ---

@dataclass(frozen=True)
class ParsedSession:
    track_id: int
    session_type: int

@dataclass(frozen=True)
class ParsedLap:
    lap_number: int
    lap_distance: float
    current_lap_time_ms: int
    sector1_ms: int
    sector2_ms: int
    is_valid: bool

@dataclass(frozen=True)
class ParsedTelemetry:
    speed: int
    throttle: float
    brake: float
    gear: int
    steer: float


# --- ЧИСТЫЕ ФУНКЦИИ ПАРСИНГА ---

def get_header(data: bytes) -> Optional[PacketHeader]:
    if len(data) < ctypes.sizeof(PacketHeader):
        return None
    return PacketHeader.from_buffer_copy(data)

def parse_session(data: bytes) -> Optional[ParsedSession]:
    if len(data) < ctypes.sizeof(PacketSessionData):
        return None
    packet = PacketSessionData.from_buffer_copy(data)
    return ParsedSession(
        track_id=packet.m_trackId,
        session_type=packet.m_sessionType
    )

def parse_lap(data: bytes, player_index: int) -> Optional[ParsedLap]:
    if len(data) < ctypes.sizeof(PacketLapData):
        return None
    packet = PacketLapData.from_buffer_copy(data)
    player_lap = packet.m_lapData[player_index]
    
    return ParsedLap(
        lap_number=player_lap.m_currentLapNum,
        lap_distance=player_lap.m_lapDistance,
        current_lap_time_ms=int(player_lap.m_currentLapTime * 1000),
        sector1_ms=player_lap.m_sector1TimeInMS,
        sector2_ms=player_lap.m_sector2TimeInMS,
        is_valid=not bool(player_lap.m_currentLapInvalid)
    )

def parse_telemetry(data: bytes, player_index: int) -> Optional[ParsedTelemetry]:
    if len(data) < ctypes.sizeof(PacketCarTelemetryData):
        return None
    packet = PacketCarTelemetryData.from_buffer_copy(data)
    player_telemetry = packet.m_carTelemetryData[player_index]
    
    return ParsedTelemetry(
        speed=player_telemetry.m_speed,
        throttle=player_telemetry.m_throttle,
        brake=player_telemetry.m_brake,
        gear=player_telemetry.m_gear,
        steer=player_telemetry.m_steer
    )

def process_packet(data: bytes) -> Union[ParsedSession, ParsedLap, ParsedTelemetry, None]:
    """Единая точка входа для обработки пакета."""
    header = get_header(data)
    if not header:
        return None

    packet_id = header.m_packetId
    player_index = header.m_playerCarIndex

    if packet_id == 1:
        return parse_session(data)
    elif packet_id == 2:
        return parse_lap(data, player_index)
    elif packet_id == 6:
        return parse_telemetry(data, player_index)
    
    return None
