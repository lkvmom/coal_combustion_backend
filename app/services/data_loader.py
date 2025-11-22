# app/services/data_loader.py
import pandas as pd
from sqlalchemy.orm import Session
from app.models.db_models import Temperature, FireEvent
from app.database import engine

def load_csv_to_db():
    # === Загрузка temperature.csv ===
    temp_df = pd.read_csv("app/data/temperature.csv", on_bad_lines="skip", dtype=str, header=None)
    temp_df = temp_df[temp_df.apply(lambda x: len(x) == 7, axis=1)]
    temp_df.columns = ["Склад", "Штабель", "Марка", "Максимальная температура", "Пикет", "Дата акта", "Смена"]

    # Преобразование даты
    temp_df["Дата акта"] = pd.to_datetime(temp_df["Дата акта"], format="%Y-%m-%d", errors="coerce")
    temp_df["Максимальная температура"] = pd.to_numeric(temp_df["Максимальная температура"], errors="coerce")
    temp_df["Склад"] = pd.to_numeric(temp_df["Склад"], errors="coerce").astype("Int64")
    temp_df["Смена"] = pd.to_numeric(temp_df["Смена"], errors="coerce")

    # УДАЛЯЕМ строки, где хотя бы одно из ключевых полей — NaN
    temp_df = temp_df.dropna(subset=["Дата акта", "Максимальная температура", "Склад", "Смена"])

    # === Загрузка fires.csv ===
    fires_df = pd.read_csv("app/data/fires.csv", on_bad_lines="skip")
    fires_df.columns = [
        "Дата составления", "Груз", "Вес", "Склад",
        "Дата начала", "Дата оконч.", "Нач.форм.штабеля", "Штабель"
    ]
    fires_df["Дата начала"] = pd.to_datetime(fires_df["Дата начала"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    fires_df["Нач.форм.штабеля"] = pd.to_datetime(fires_df["Нач.форм.штабеля"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    fires_df["Склад"] = pd.to_numeric(fires_df["Склад"], errors="coerce").astype("Int64")
    fires_df = fires_df.dropna(subset=["Дата начала", "Склад", "Штабель"])

    # === Сохранение в БД ===
    with Session(engine) as session:
        for _, row in temp_df.iterrows():
            temp = Temperature(
                warehouse=int(row["Склад"]),
                pile_id=str(row["Штабель"]),
                coal_grade=row["Марка"],
                max_temp=float(row["Максимальная температура"]),
                measurement_date=row["Дата акта"],
                shift=int(row["Смена"])  # ← Теперь гарантированно не NaN
            )
            session.add(temp)
        session.commit()

        for _, row in fires_df.iterrows():
            fire = FireEvent(
                warehouse=int(row["Склад"]),
                pile_id=str(row["Штабель"]),
                coal_grade=row["Груз"],
                fire_start=row["Дата начала"],
                pile_formed_at=row["Нач.форм.штабеля"]
            )
            session.add(fire)
        session.commit()

    print("✅ Данные загружены в PostgreSQL")