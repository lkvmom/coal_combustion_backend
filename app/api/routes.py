from fastapi import APIRouter, File, UploadFile, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
import pandas as pd
from io import BytesIO

from app.database import engine
from app.models.db_models import (
    CurrentStockpile,
    ActualFire,
    Temperature,
    FireEvent,
    Weather
)
from app.services.predictor import predict_ignition_risk

router = APIRouter(prefix="/api", tags=["core"])


def get_session():
    with Session(engine) as session:
        yield session


# 1. Приём данных о текущем штабеле (на ноябрь 2025)
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


# 2. Прогноз самовозгорания
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


# 3. Календарь на 21–25 ноября 2025
@router.get("/calendar")
def get_calendar():
    return {
        "period": "2025-11-21 — 2025-11-25",
        "high_risk_days": [
            {"date": "2025-11-22", "warehouse": 4, "pile_id": "39"},
            {"date": "2025-11-24", "warehouse": 3, "pile_id": "12"}
        ]
    }


# 4. Загрузка реальных данных о возгораниях (после прогноза)
@router.post("/upload-actual-fires")
def upload_actual_fires(
    warehouse: int,
    pile_id: str,
    fire_date: str,  # YYYY-MM-DD
    session: Session = Depends(get_session)
):
    try:
        fire_date_parsed = datetime.strptime(fire_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты: ожидается YYYY-MM-DD")

    fire = ActualFire(
        warehouse=warehouse,
        pile_id=pile_id,
        fire_date=fire_date_parsed
    )
    session.add(fire)
    session.commit()
    return {"status": "ok"}


# 5. Метрики качества (заглушка)
@router.get("/metrics")
def get_metrics():
    return {
        "accuracy_2days": 0.0,
        "total_predictions": 0,
        "correct_predictions": 0,
        "note": "После загрузки реальных данных метрики обновятся"
    }


# 6. Загрузка CSV-файлов: temperature, fires, weather
@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Только CSV файлы")

    content = await file.read()
    try:
        df = pd.read_csv(BytesIO(content), on_bad_lines="skip", dtype=str, header=None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения CSV: {str(e)}")

    inserted = 0
    filename = file.filename.lower()

    # === Загрузка temperature.csv ===
    if "temperature" in filename:
        if len(df.columns) < 7:
            raise HTTPException(400, "Недостаточно колонок в temperature.csv")
        df = df.iloc[:, :7]
        df.columns = ["Склад", "Штабель", "Марка", "Макс.темп", "Пикет", "Дата", "Смена"]

        df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")
        df["Макс.темп"] = pd.to_numeric(df["Макс.темп"], errors="coerce")
        df["Склад"] = pd.to_numeric(df["Склад"], errors="coerce").astype("Int64")
        df["Смена"] = pd.to_numeric(df["Смена"], errors="coerce")
        df = df.dropna(subset=["Дата", "Макс.темп", "Склад", "Смена"])

        for _, r in df.iterrows():
            session.add(Temperature(
                warehouse=int(r["Склад"]),
                pile_id=str(r["Штабель"]),
                coal_grade=r["Марка"],
                max_temp=float(r["Макс.темп"]),
                measurement_date=r["Дата"],
                shift=int(r["Смена"])
            ))
            inserted += 1

    # === Загрузка fires.csv ===
    elif "fire" in filename or "fires" in filename:
        if df.shape[0] == 0:
            raise HTTPException(400, "Пустой файл fires.csv")
        header_row = df.iloc[0].astype(str).str.contains("Дата составления").any()
        if header_row:
            df.columns = df.iloc[0]
            df = df[1:]
        else:
            df.columns = [
                "Дата составления", "Груз", "Вес по акту, тн", "Склад",
                "Дата начала", "Дата оконч.", "Нач.форм.штабеля", "Штабель"
            ]

        df["Дата начала"] = pd.to_datetime(df["Дата начала"], errors="coerce")
        df["Нач.форм.штабеля"] = pd.to_datetime(df["Нач.форм.штабеля"], errors="coerce")
        df["Склад"] = pd.to_numeric(df["Склад"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["Дата начала", "Склад", "Штабель"])

        for _, r in df.iterrows():
            session.add(FireEvent(
                warehouse=int(r["Склад"]),
                pile_id=str(r["Штабель"]),
                coal_grade=r["Груз"],
                fire_start=r["Дата начала"],
                pile_formed_at=r["Нач.форм.штабеля"]
            ))
            inserted += 1

    # === Загрузка weather_data_*.csv ===
    elif "weather" in filename:
        if len(df.columns) < 11:
            raise HTTPException(400, "Недостаточно колонок в weather CSV")
        df = df.iloc[:, :11]
        df.columns = [
            "datetime", "temp", "pressure", "humidity", "precipitation",
            "wind_dir", "wind_speed", "v_max", "cloudcover", "visibility", "weather_code"
        ]
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        for col in ["temp", "pressure", "humidity", "precipitation", "wind_speed", "cloudcover"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["datetime", "temp", "humidity"])

        for _, r in df.iterrows():
            session.add(Weather(
                datetime=r["datetime"],
                temp=r["temp"],
                pressure=r["pressure"],
                humidity=int(r["humidity"]),
                precipitation=r["precipitation"],
                wind_dir=r["wind_dir"] if pd.notna(r["wind_dir"]) else None,
                wind_speed=r["wind_speed"],
                cloudcover=r["cloudcover"] if pd.notna(r["cloudcover"]) else None,
                visibility=r["visibility"] if pd.notna(r["visibility"]) else None,
                weather_code=r["weather_code"] if pd.notna(r["weather_code"]) else None
            ))
            inserted += 1

    else:
        raise HTTPException(400, "Неподдерживаемый файл. Ожидается: temperature.csv, fires.csv или weather_data_*.csv")

    session.commit()
    return {"filename": file.filename, "inserted_rows": inserted}


# 7. Получить погоду за период (ежедневная агрегация)
@router.get("/weather")
def get_weather(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    session: Session = Depends(get_session)
):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты: YYYY-MM-DD")

    result = session.query(
        func.date(Weather.datetime).label("date"),
        func.avg(Weather.temp).label("avg_temp"),
        func.avg(Weather.humidity).label("avg_humidity"),
        func.sum(Weather.precipitation).label("total_precip"),
        func.avg(Weather.wind_speed).label("avg_wind_speed")
    ).filter(
        Weather.datetime >= start_dt,
        Weather.datetime <= end_dt
    ).group_by(func.date(Weather.datetime)).all()

    return [
        {
            "date": str(r.date),
            "avg_temp": round(float(r.avg_temp), 1),
            "avg_humidity": int(r.avg_humidity),
            "total_precip": round(float(r.total_precip), 1),
            "avg_wind_speed": round(float(r.avg_wind_speed), 1)
        }
        for r in result
    ]


# 8. Данные по штабелю + погода за период
@router.get("/pile-weather")
def get_pile_weather(
    warehouse: int,
    pile_id: str,
    start: str,
    end: str,
    session: Session = Depends(get_session)
):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты: YYYY-MM-DD")

    temps = session.query(Temperature).filter(
        Temperature.warehouse == warehouse,
        Temperature.pile_id == pile_id,
        Temperature.measurement_date >= start_dt,
        Temperature.measurement_date <= end_dt
    ).all()

    fires = session.query(FireEvent).filter(
        FireEvent.warehouse == warehouse,
        FireEvent.pile_id == pile_id,
        FireEvent.fire_start >= start_dt,
        FireEvent.fire_start <= end_dt
    ).all()

    weather = session.query(
        func.date(Weather.datetime).label("date"),
        func.avg(Weather.temp).label("avg_temp"),
        func.avg(Weather.humidity).label("avg_humidity")
    ).filter(
        Weather.datetime >= start_dt,
        Weather.datetime <= end_dt
    ).group_by(func.date(Weather.datetime)).all()

    return {
        "temperatures": [
            {
                "date": t.measurement_date.date().isoformat(),
                "temp": t.max_temp,
                "shift": t.shift
            }
            for t in temps
        ],
        "weather": [
            {
                "date": str(w.date),
                "avg_temp": float(w.avg_temp),
                "avg_humidity": int(w.avg_humidity)
            }
            for w in weather
        ],
        "fires": [
            {
                "date": f.fire_start.date().isoformat()
            }
            for f in fires
        ]
    }