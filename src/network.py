import asyncio
import logging

from requests_cache import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class F1TelemetryProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.transport = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        logger.info("UDP-сервер запущен. Ожидание телеметрии F1 2020 на порту 20777...")

    def datagram_received(self, data: bytes, addr: tuple):
        # Неблокирующая передача байт-строки в очередь
        try:
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("Очередь переполнена. Пакет отброшен.")

    def error_received(self, exc: Exception):
        logger.error(f"Ошибка получения UDP пакета: {exc}")

    def connection_lost(self, exc: Optional[Exception]):
        logger.info("UDP соединение закрыто.")


async def start_udp_server(queue: asyncio.Queue, host: str = '0.0.0.0', port: int = 20777) -> asyncio.DatagramTransport:
    """Инициализация и запуск прослушивания порта."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: F1TelemetryProtocol(queue),
        local_addr=(host, port)
    )
    return transport