import ctypes
from src.parser import PacketHeader, PacketSessionData, parse_session

def test_parse_session_valid_data():
    """Проверка корректного парсинга пакета сессии."""
    # Создаем фейковый заголовок
    header = PacketHeader(
        m_packetFormat=2020,
        m_packetId=1,
        m_sessionUID=987654321,
        m_playerCarIndex=0
    )
    # Создаем фейковый пакет сессии (Track ID 10, Type 1)
    packet = PacketSessionData(
        m_header=header,
        m_trackId=10,
        m_sessionType=1
    )
    
    # Конвертируем C-структуру в байты
    raw_bytes = bytes(packet)
    
    # Парсим через нашу функцию
    parsed = parse_session(raw_bytes)
    
    assert parsed is not None
    assert parsed.session_uid == 987654321
    assert parsed.track_id == 10
    assert parsed.session_type == 1

def test_parse_session_invalid_data():
    """Проверка отбрасывания битых или неполных пакетов."""
    bad_bytes = b'\x00\x01\x02' # Слишком короткий пакет
    parsed = parse_session(bad_bytes)
    assert parsed is None