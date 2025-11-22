from datetime import date, datetime
from sqlmodel import SQLModel, Field
from typing import Optional

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
    fire_date: date  # например: 2025-11-23