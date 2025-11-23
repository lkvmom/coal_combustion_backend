# app/database.py
from sqlmodel import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Строка подключения (используй свои значения)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/coal_hack"
)

# Синхронный движок (для загрузки данных и инициализации)
engine = create_engine(DATABASE_URL, echo=False)

# Сессия для использования в сервисах
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_session():
    with SessionLocal() as session:
        yield session