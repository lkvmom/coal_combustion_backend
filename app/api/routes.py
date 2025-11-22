from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import engine
from app.models.db_models import CurrentStockpile, ActualFire
from app.services.predictor import predict_ignition_risk

router = APIRouter(prefix="/api", tags=["core"])

def get_session():
    with Session(engine) as session:
        yield session

@router.post("/submit-stockpile")
def submit_stockpile(
    warehouse: int,
    pile_id: str,
    coal_grade: str,
    current_temp: float,
    pile_age_days: int,
    session: Session = Depends(get_session)
):
    stockpile = CurrentStockpile(
        warehouse=warehouse,
        pile_id=pile_id,
        coal_grade=coal_grade,
        current_temp=current_temp,
        pile_age_days=pile_age_days
    )
    session.add(stockpile)
    session.commit()
    session.refresh(stockpile)
    return {"id": stockpile.id, "status": "ok"}

@router.post("/predict")
def predict(
    warehouse: int,
    pile_id: str,
    current_temp: float,
    pile_age_days: int,
    coal_grade: str,
    current_date: str = "2025-11-21"
):
    features = {
        "current_temp": current_temp,
        "pile_age_days": pile_age_days,
        "coal_grade": coal_grade,
        "current_date": current_date
    }
    return predict_ignition_risk(features)

@router.get("/calendar")
def get_calendar():
    # Заглушка: прогноз на 21–25 ноября 2025
    return {
        "period": "2025-11-21 — 2025-11-25",
        "high_risk_days": [
            {"date": "2025-11-22", "warehouse": 4, "pile_id": "39"},
            {"date": "2025-11-24", "warehouse": 3, "pile_id": "12"}
        ]
    }

@router.post("/upload-actual-fires")
def upload_actual_fires(
    warehouse: int,
    pile_id: str,
    fire_date: str,  # YYYY-MM-DD
    session: Session = Depends(get_session)
):
    fire = ActualFire(
        warehouse=warehouse,
        pile_id=pile_id,
        fire_date=fire_date
    )
    session.add(fire)
    session.commit()
    return {"status": "ok"}

@router.get("/metrics")
def get_metrics():
    # Заглушка. После загрузки actual_fires — будет реальный подсчёт
    return {
        "accuracy_2days": 0.0,
        "total_predictions": 0,
        "correct_predictions": 0,
        "note": "После загрузки реальных данных метрики обновятся"
    }