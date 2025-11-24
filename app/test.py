# test_predictor.py

import sys
import os

# Добавим путь до app/
sys.path.insert(0, os.path.abspath('.'))

from app.services.predictor import predict_ignition_risk
from sqlalchemy.orm import sessionmaker
from app.database import engine
from datetime import datetime

# Создаём сессию
SessionLocal = sessionmaker(bind=engine)

def test_prediction():
    print("🧪 Тестируем predict_ignition_risk...")

    # Пример признаков (реалистичные данные из CSV)
    features = {
        "Склад": 4,
        "Штабель": "46",
        "Марка": "A1",
        "Максимальная_температура": 65.0,
        "Смена": 219,
        "t": 20.0,  # температура воздуха
        "p": 1013.25,  # давление
        "humidity": 70,
        "precipitation": 0.0,
        "wind_dir": 0,
        "v_avg": 5.0,
        "v_max": 7.5,
        "cloudcover": 50,
        "weather_code": 0,
        "Наим_ЕТСНГ": "A1",
        "На_склад_тн": 0.0,
        "На_судно_тн": 0.0,
        "Склад_supply": 4,
        "ДниСНачалаФормирования": 120,  # возраст штабеля
        "current_date": "2025-11-21"  # дата, от которой считаем прогноз
    }

    print("📋 Признаки:")
    for k, v in features.items():
        print(f"  {k}: {v}")

    # Создаём сессию
    session = SessionLocal()

    try:
        result = predict_ignition_risk(features, session)
        print("\n✅ Прогноз получен:")
        print(f"  Дата самовозгорания: {result.get('predicted_ignition_date')}")
        print(f"  Дней до самовозгорания: {result.get('predicted_days_to_fire')}")
        print(f"  Уровень риска: {result.get('risk_level')}")
        print(f"  Сообщение: {result.get('message')}")
    except Exception as e:
        print(f"\n❌ Ошибка при вызове predict_ignition_risk: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_prediction()