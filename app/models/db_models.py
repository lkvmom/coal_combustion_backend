# app/models/db_models.py
from datetime import datetime, date
from sqlmodel import SQLModel, Field
from typing import Optional


# --- Таблицы для ввода с фронта и метрик ---
class CurrentStockpile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse: int
    pile_id: str
    coal_grade: str
    current_temp: float
    pile_age_days: int
    reported_at: datetime = Field(default_factory=datetime.utcnow)


class ActualFire(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse: int
    pile_id: str
    fire_date: date


# --- Исторические данные (для DS и анализа) ---
class Temperature(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse: int
    pile_id: str
    coal_grade: str
    max_temp: float
    measurement_date: datetime
    shift: int


class FireEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse: int
    pile_id: str
    coal_grade: str
    fire_start: datetime
    pile_formed_at: datetime


# --- Погода ---
class Weather(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    datetime: datetime                    # точное время (почасово)
    temp: float                           # температура, °C
    pressure: float                       # давление, гПа
    humidity: int                         # влажность, %
    precipitation: float                  # осадки, мм
    wind_dir: Optional[int]               # направление ветра, градусы
    wind_speed: float                     # средняя скорость ветра, км/ч
    cloudcover: Optional[int]             # облачность, %
    visibility: Optional[int]             # видимость, м
    weather_code: Optional[int]           # код погоды