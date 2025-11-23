# app/services/weather_loader.py

import pandas as pd
from sqlalchemy.orm import Session
from app.models.db_models import Weather
from app.database import engine

def load_weather_csv(file_path: str):
    # Читаем CSV (без заголовка)
    df = pd.read_csv(file_path, header=None, on_bad_lines="skip", dtype=str)
    
    # Ожидаем 11 колонок (как в weather_data_2015.csv)
    if len(df.columns) < 11:
        raise ValueError(f"Недостаточно колонок в {file_path}")
    
    df = df.iloc[:, :11]
    df.columns = ["datetime", "temp", "pressure", "humidity", "precipitation",
                  "wind_dir", "wind_speed", "v_max", "cloudcover", "visibility", "weather_code"]

    # Очистка
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    numeric_cols = ["temp", "pressure", "humidity", "precipitation", "wind_speed", "cloudcover"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["datetime", "temp"])

    # Сохранение в БД
    with Session(engine) as session:
        for _, row in df.iterrows():
            w = Weather(
                datetime=row["datetime"],
                temp=row["temp"],
                pressure=row["pressure"],
                humidity=int(row["humidity"]),
                precipitation=row["precipitation"],
                wind_dir=row["wind_dir"] if pd.notna(row["wind_dir"]) else None,
                wind_speed=row["wind_speed"],
                cloudcover=row["cloudcover"] if pd.notna(row["cloudcover"]) else None,
                visibility=row["visibility"] if pd.notna(row["visibility"]) else None,
                weather_code=row["weather_code"] if pd.notna(row["weather_code"]) else None
            )
            session.add(w)
        session.commit()
    print(f"✅ Загружено {len(df)} записей из {file_path}")