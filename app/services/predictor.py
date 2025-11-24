import joblib
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

MODEL_PATH = os.getenv("MODEL_PATH", "app/models/model.pkl")

# Загрузка модели и энкодеров при старте
model = joblib.load(MODEL_PATH)
le_stack = joblib.load("app/models/label_encoder_stack.pkl")
le_marka = joblib.load("app/models/label_encoder_marka.pkl")
le_naim = joblib.load("app/models/label_encoder_naim.pkl")

def predict_ignition_risk(features: dict, session: Session):
    print("=== DEBUG: Input features ===")
    print(features)
    print("=============================")

    # Кодирование строковых признаков
    try:
        encoded_stack = le_stack.transform([str(features["Штабель"])])[0]
        print(f"DEBUG: encoded_stack = {encoded_stack}")
    except ValueError as e:
        print(f"ERROR: Штабель '{features['Штабель']}' неизвестен в LabelEncoder: {e}")
        encoded_stack = -1  # или вызвать ошибку

    try:
        encoded_marka = le_marka.transform([features["Марка"]])[0]
        print(f"DEBUG: encoded_marka = {encoded_marka}")
    except ValueError as e:
        print(f"ERROR: Марка '{features['Марка']}' неизвестна в LabelEncoder: {e}")
        encoded_marka = -1

    try:
        encoded_naim = le_naim.transform([features["Наим_ЕТСНГ"]])[0]
        print(f"DEBUG: encoded_naim = {encoded_naim}")
    except ValueError as e:
        print(f"ERROR: Наим_ЕТСНГ '{features['Наим_ЕТСНГ']}' неизвестно в LabelEncoder: {e}")
        encoded_naim = -1

    # Подготовка вектора признаков (в том же порядке, что и при обучении)
    X = [
        features["Склад"],
        features["Максимальная_температура"],
        features["Смена"],
        features["t"],
        features["p"],
        features["humidity"],
        features["precipitation"],
        features["wind_dir"],
        features["v_avg"],
        features["v_max"],
        features["cloudcover"],
        features["weather_code"],
        features["На_склад_тн"],
        features["На_судно_тн"],
        features["Склад_supply"],
        features["ДниСНачалаФормирования"],
        encoded_stack,
        encoded_marka,
        encoded_naim
    ]

    print(f"DEBUG: Вектор X для модели: {X}")

    # Предсказание
    try:
        pred_days = model.predict([X])[0]
        print(f"DEBUG: Модель вернула: {pred_days} дней")
    except Exception as e:
        print(f"ERROR: Ошибка при вызове model.predict: {e}")
        raise e

    # Определение даты прогноза
    current_date_str = features.get("current_date", "2025-11-21")
    current_date = datetime.fromisoformat(current_date_str)
    predicted_date = current_date + timedelta(days=int(pred_days))

    # Оценка риска
    risk_level = "Низкий"
    if pred_days <= 2:
        risk_level = "Высокий"
    elif pred_days <= 5:
        risk_level = "Средний"

    print(f"DEBUG: Прогнозируемая дата: {predicted_date.isoformat()}, уровень риска: {risk_level}")

    return {
        "predicted_ignition_date": predicted_date.isoformat(),
        "predicted_days_to_fire": float(pred_days),
        "risk_level": risk_level,
        "message": f"Прогнозируемое время до самовозгорания: {pred_days:.2f} дней (~{int(pred_days)} дней)"
    }