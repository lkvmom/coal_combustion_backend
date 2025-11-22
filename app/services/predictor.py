import os
from typing import Dict, Any

MODEL_PATH = "models/model.pkl"

def predict_ignition_risk(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Заглушка. Вместо модели — простая логика.
    Позже заменится на joblib.load(model).predict(...)
    """
    current_temp = features["current_temp"]
    pile_age = features["pile_age_days"]

    # Простая эвристика
    risk_score = min(1.0, max(0.0, (current_temp - 40) / 40))
    predicted_date = None
    warning = "Низкий риск"

    if risk_score >= 0.5:
        # Прогноз на 22–25 ноября 2025
        from datetime import datetime, timedelta
        base_date = datetime.strptime(features.get("current_date", "2025-11-21"), "%Y-%m-%d")
        predicted_date = (base_date + timedelta(days=2)).strftime("%Y-%m-%d")
        warning = "Высокий риск самовозгорания!"

    return {
        "predicted_ignition_date": predicted_date,
        "risk_score": round(risk_score, 3),
        "warning": warning
    }