import asyncio
import logging
from src.database import init_db
from src.network import start_udp_server
from src.state_manager import TelemetryStateManager

logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Инициализация БД (создание таблиц)
    init_db()
    
    # 2. Создание очереди
    queue = asyncio.Queue(maxsize=2000)
    
    # 3. Запуск менеджера состояний (потребитель)
    manager = TelemetryStateManager(queue)
    manager_task = asyncio.create_task(manager.run())
    
    # 4. Запуск UDP-сервера (производитель)
    transport = await start_udp_server(queue, port=20777)
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        transport.close()
        manager_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())