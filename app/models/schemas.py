# app/models/schemas.py
from pydantic import BaseModel
from datetime import date
from typing import Optional, List

class PredictionRequest(BaseModel):
    warehouse: int
    pile_id: str
    current_temp: float
    pile_age_days: int
    coal_grade: str
    current_date: str = "2025-11-21"

class PredictionResponse(BaseModel):
    predicted_ignition_date: Optional[str]
    risk_score: float
    warning: str

class CalendarResponse(BaseModel):
    period: str
    high_risk_days: List[dict]

class MetricsResponse(BaseModel):
    accuracy_2days: float
    total_predictions: int
    correct_predictions: int