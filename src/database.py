import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from src.models import Base

# Определение абсолютного пути к БД в директории data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'f1_telemetry.db')
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Убедимся, что директория data существует
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# check_same_thread=False необходим для передачи сессии между потоками (в ThreadPoolExecutor)
engine = create_engine(
    DATABASE_URL, 
    connect_args={'check_same_thread': False},
    echo=False
)

# Инъекция PRAGMA при каждом новом подключении к SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA cache_size=-64000;") # Кеш 64MB
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Создание таблиц, если они не существуют."""
    Base.metadata.create_all(bind=engine)