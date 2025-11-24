from fastapi import APIRouter, File, UploadFile, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO

from app.database import engine
from app.models.db_models import (
    CurrentStockpile,
    ActualFire,
    Temperature,
    FireEvent,
    Weather,
    Supply
)
from app.services.predictor import predict_ignition_risk

from pydantic import BaseModel

class PredictionRequest(BaseModel):
    Склад: int
    Штабель: int
    Марка: str
    Максимальная_температура: float
    Смена: int
    t: float
    p: float
    humidity: int
    precipitation: float
    wind_dir: int
    v_avg: float
    v_max: float
    cloudcover: int
    weather_code: int
    Наим_ЕТСНГ: str
    На_склад_тн: float
    На_судно_тн: float
    Склад_supply: int
    ДниСНачалаФормирования: int

router = APIRouter(prefix="/api", tags=["core"])

def get_session():
    with Session(engine) as session:
        yield session

@router.post("/predict")
def predict(request: PredictionRequest, session: Session = Depends(get_session)):
    # Преобразуйте поля в нужный формат для модели
    features = {
        "warehouse": request.Склад,
        "pile_id": str(request.Штабель),
        "coal_grade": request.Марка,
        "current_temp": request.Максимальная_температура,
        "shift": request.Смена,
        "t": request.t,
        "p": request.p,
        "humidity": request.humidity,
        "precipitation": request.precipitation,
        "wind_dir": request.wind_dir,
        "v_avg": request.v_avg,
        "v_max": request.v_max,
        "cloudcover": request.cloudcover,
        "weather_code": request.weather_code,
        "coal_grade_supply": request.Наим_ЕТСНГ,
        "to_warehouse_tn": request.На_склад_тн,
        "to_ship_tn": request.На_судно_тн,
        "supply_warehouse": request.Склад_supply,
        "pile_age_days": request.ДниСНачалаФормирования
    }

    # Передайте в вашу модель
    return predict_ignition_risk(features, session)

# ... остальные эндпоинты ...


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

    elif "supply" in filename or "supplies" in filename:
        df.columns = ["ВыгрузкаНаСклад", "Наим. ЕТСНГ", "Штабель", "ПогрузкаНаСудно", "На склад, тн", "На судно, тн", "Склад"]

        df["ВыгрузкаНаСклад"] = pd.to_datetime(df["ВыгрузкаНаСклад"], errors="coerce")
        df["ПогрузкаНаСудно"] = pd.to_datetime(df["ПогрузкаНаСудно"], errors="coerce")
        df["Штабель"] = pd.to_numeric(df["Штабель"], errors="coerce").astype("Int64")
        df["Склад"] = pd.to_numeric(df["Склад"], errors="coerce").astype("Int64")
        df["На склад, тн"] = pd.to_numeric(df["На склад, тн"], errors="coerce")
        df["На судно, тн"] = pd.to_numeric(df["На судно, тн"], errors="coerce")

        df = df.dropna(subset=["ВыгрузкаНаСклад", "Штабель", "Склад"])

        for _, row in df.iterrows():
            s = Supply(
                unload_to_warehouse=row["ВыгрузкаНаСклад"],
                coal_grade=row["Наим. ЕТСНГ"],
                pile_id=row["Штабель"],
                load_to_ship=row["ПогрузкаНаСудно"],
                to_warehouse_tn=row["На склад, тн"],
                to_ship_tn=row["На судно, тн"],
                warehouse=row["Склад"]
            )
            session.add(s)
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
    pileId: str,       # ← именно так, как в фронтенде
    start: str,
    end: str,
    session: Session = Depends(get_session)
):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты: YYYY-MM-DD")

    temps = session.query(Temperature).filter(
        Temperature.warehouse == warehouse,
        Temperature.pile_id == pileId,  # ← именно так
        Temperature.measurement_date >= start_dt,
        Temperature.measurement_date <= end_dt
    ).order_by(Temperature.measurement_date).all()  # ← добавь сортировку

    fires = session.query(FireEvent).filter(
        FireEvent.warehouse == warehouse,
        FireEvent.pile_id == pileId,  # ← и здесь
        FireEvent.fire_start >= start_dt,
        FireEvent.fire_start <= end_dt
    ).order_by(FireEvent.fire_start).all()  # ← и здесь

    weather = session.query(
        func.date(Weather.datetime).label("date"),
        func.avg(Weather.temp).label("avg_temp"),
        func.avg(Weather.humidity).label("avg_humidity"),
        func.sum(Weather.precipitation).label("total_precip"),
        func.avg(Weather.wind_speed).label("avg_wind_speed")
    ).filter(
        Weather.datetime >= start_dt,
        Weather.datetime <= end_dt
    ).group_by(func.date(Weather.datetime)).order_by(func.date(Weather.datetime)).all()  # ← и здесь

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
                "avg_humidity": int(w.avg_humidity),
                "total_precip": float(w.total_precip),
                "avg_wind_speed": float(w.avg_wind_speed)
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

@router.get("/warehouses")
def get_warehouses(session: Session = Depends(get_session)):
    result = session.query(Temperature.warehouse).distinct().all()
    return {"warehouses": [r[0] for r in result]}

@router.get("/stacks/{warehouse}")
def get_stacks(warehouse: int, session: Session = Depends(get_session)):
    result = session.query(Temperature.pile_id).filter(Temperature.warehouse == warehouse).distinct().all()
    return {"stacks": [r[0] for r in result]}   


@router.get("/pile-age")
def get_pile_age(warehouse: int, pileId: str, session: Session = Depends(get_session)):
    from datetime import datetime
    # Получаем дату формирования штабеля из fires
    fire_record = session.query(FireEvent).filter(
        FireEvent.warehouse == warehouse,
        FireEvent.pile_id == pileId
    ).first()

    if fire_record and fire_record.pile_formed_at:
        pile_age = (datetime.now() - fire_record.pile_formed_at).days
        return {"pile_age_days": pile_age}
    else:
        return {"pile_age_days": 30}  # заглушка
    

@router.get("/dashboard-summary")
def get_dashboard_summary(
    forecast_days: int = Query(5, description="Количество дней для прогноза"),
    session: Session = Depends(get_session)
):
    # ❗️Найти последнюю дату в БД (температура или погода)
    last_temp_date_result = session.query(
        func.max(Temperature.measurement_date)
    ).scalar()

    last_weather_date_result = session.query(
        func.max(Weather.datetime)
    ).scalar()

    # Выбираем более позднюю дату
    last_date = None
    if last_temp_date_result and last_weather_date_result:
        last_date = max(last_temp_date_result.date(), last_weather_date_result.date())
    elif last_temp_date_result:
        last_date = last_temp_date_result.date()
    elif last_weather_date_result:
        last_date = last_weather_date_result.date()
    else:
        raise HTTPException(status_code=404, detail="Нет данных температуры или погоды в БД")

    # ❗️Дата начала прогноза — следующий день после последней даты
    start_date = last_date + timedelta(days=1)
    end_date = start_date + timedelta(days=forecast_days - 1)

    # ❗️Получить все уникальные штабели
    unique_piles = session.query(Temperature.warehouse, Temperature.pile_id).distinct().all()

    incidents = []

    for wp in unique_piles:
        warehouse = wp[0]
        pile_id = wp[1]

        # ❗️Получить последнюю температуру
        last_temp = session.query(Temperature).filter(
            Temperature.warehouse == warehouse,
            Temperature.pile_id == pile_id
        ).order_by(Temperature.measurement_date.desc()).first()

        if not last_temp:
            continue

        # ❗️Получить дату формирования штабеля
        fire_record = session.query(FireEvent).filter(
            FireEvent.warehouse == warehouse,
            FireEvent.pile_id == pile_id
        ).first()

        if fire_record and fire_record.pile_formed_at:
            pile_age_days = (last_date - fire_record.pile_formed_at.date()).days
        else:
            pile_age_days = 30  # дефолт

        # ❗️Получить погоду за последний день температуры
        weather_record = session.query(Weather).filter(
            func.date(Weather.datetime) == last_temp.measurement_date.date()
        ).first()

        if weather_record:
            t = weather_record.temp
            p = weather_record.pressure
            humidity = weather_record.humidity
            precipitation = weather_record.precipitation
            wind_dir = weather_record.wind_dir
            v_avg = weather_record.wind_speed
            v_max = v_avg * 1.5
            cloudcover = weather_record.cloudcover
            weather_code = weather_record.weather_code
        else:
            # дефолт
            t = 20.0
            p = 1013.25
            humidity = 65
            precipitation = 0.0
            wind_dir = 0
            v_avg = 5.0
            v_max = 7.5
            cloudcover = 50
            weather_code = 0

        # ❗️Подготовить признаки
        predict_data = {
            "Склад": warehouse,
            "Штабель": int(pile_id),
            "Марка": last_temp.coal_grade,
            "Максимальная_температура": last_temp.max_temp,
            "Смена": last_temp.shift,
            "t": t,
            "p": p,
            "humidity": humidity,
            "precipitation": precipitation,
            "wind_dir": wind_dir,
            "v_avg": v_avg,
            "v_max": v_max,
            "cloudcover": cloudcover,
            "weather_code": weather_code,
            "Наим_ЕТСНГ": last_temp.coal_grade,
            "На_склад_тн": 0.0,
            "На_судно_тн": 0.0,
            "Склад_supply": warehouse,
            "ДниСНачалаФормирования": pile_age_days
        }

        # ❗️Вызвать predict (передаём session)
        try:
            prediction = predict_ignition_risk(predict_data, session)
            predicted_date_str = prediction.get("predicted_ignition_date")

            if predicted_date_str:
                predicted_date = datetime.fromisoformat(predicted_date_str).date()

                if start_date <= predicted_date <= end_date:
                    incidents.append({
                        "date": predicted_date.isoformat(),
                        "warehouse": warehouse,
                        "pile_id": pile_id,
                        "predicted_ignition_date": predicted_date_str,
                        "message": prediction.get("message", "")
                    })
        except Exception as e:
            # Логировать, если нужно
            continue

    # ❗️Агрегировать по дням
    from collections import defaultdict
    summary_by_day = defaultdict(int)
    for inc in incidents:
        summary_by_day[inc["date"]] += 1

    # ❗️Заполнить пропущенные дни
    date_list = [(start_date + timedelta(days=i)).isoformat() for i in range(forecast_days)]
    final_summary = []
    for d in date_list:
        final_summary.append({
            "date": d,
            "count": summary_by_day[d]
        })

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} — {end_date.strftime('%Y-%m-%d')}",
        "summary_by_day": final_summary,
        "high_risk_incidents": incidents
    }


@router.get("/dashboard-summary-test")
def get_dashboard_summary_test(
    start_date: str = Query(..., description="Дата начала прогноза (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Дата окончания прогноза (YYYY-MM-DD)"),
    session: Session = Depends(get_session)
):
    print(f"DEBUG: start_date = {start_date}, end_date = {end_date}")
    print("DEBUG: Запрос на /dashboard-summary-test получен")

    try:
        start_dt = datetime.fromisoformat(start_date).date()
        end_dt = datetime.fromisoformat(end_date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Ожидается YYYY-MM-DD")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="Дата начала не может быть позже даты окончания")

    unique_piles = session.query(Temperature.warehouse, Temperature.pile_id).distinct().all()

    incidents = []

    for idx, wp in enumerate(unique_piles):
        warehouse = wp[0]
        pile_id = wp[1]

        print(f"DEBUG [{idx}]: Обрабатываю штабель {warehouse}, {pile_id}")

        # ❗️Получить **последнюю температуру до start_date**
        last_temp = session.query(Temperature).filter(
            Temperature.warehouse == warehouse,
            Temperature.pile_id == pile_id,
            Temperature.measurement_date < start_dt  # ❗️Не включая start_date
        ).order_by(Temperature.measurement_date.desc()).first()

        if not last_temp:
            print(f"❌ Нет температуры для {warehouse}, {pile_id} до {start_dt}")
            continue
        else:
            print(f"✅ Найдена температура: {last_temp.max_temp}°C на дату {last_temp.measurement_date}")

        # ❗️Получить возраст штабеля
        fire_record = session.query(FireEvent).filter(
            FireEvent.warehouse == warehouse,
            FireEvent.pile_id == pile_id
        ).first()

        if fire_record and fire_record.pile_formed_at:
            pile_age_days = (start_dt - fire_record.pile_formed_at.date()).days
        else:
            pile_age_days = 30  # дефолт

        # ❗️ПОЛУЧАЕМ ПОГОДУ ЗА ДЕНЬ ДО start_date — или БЛИЖАЙШУЮ, ЕСЛИ НЕТ
        weather_date = start_dt - timedelta(days=1)

        # ❗️Ищем **ближайшую погоду <= weather_date**
        weather_record = session.query(Weather).filter(
            func.date(Weather.datetime) <= weather_date
        ).order_by(Weather.datetime.desc()).first()

        if weather_record:
            print(f"✅ Найдена погода за {weather_record.datetime.date()}")
            t = weather_record.temp
            p = weather_record.pressure
            humidity = int(weather_record.humidity)
            precipitation = weather_record.precipitation
            wind_dir = weather_record.wind_dir or 0
            v_avg = weather_record.wind_speed
            v_max = weather_record.v_max or (v_avg * 1.5)
            cloudcover = weather_record.cloudcover or 50
            weather_code = weather_record.weather_code or 0
        else:
            print(f"❌ Нет погоды до {weather_date}, используем дефолтные значения")
            # ❗️Не пропускаем штабель — используем дефолтные значения
            t = 5.0
            p = 1013.25
            humidity = 70
            precipitation = 0.0
            wind_dir = 0
            v_avg = 5.0
            v_max = 7.5
            cloudcover = 50
            weather_code = 0

        # ❗️Подготовить признаки
        predict_data = {
            "Склад": warehouse,
            "Штабель": int(pile_id),
            "Марка": last_temp.coal_grade,
            "Максимальная_температура": last_temp.max_temp,
            "Смена": last_temp.shift,
            "t": t,
            "p": p,
            "humidity": humidity,
            "precipitation": precipitation,
            "wind_dir": wind_dir,
            "v_avg": v_avg,
            "v_max": v_max,
            "cloudcover": cloudcover,
            "weather_code": weather_code,
            "Наим_ЕТСНГ": last_temp.coal_grade,
            "На_склад_тн": 0.0,
            "На_судно_тн": 0.0,
            "Склад_supply": warehouse,
            "ДниСНачалаФормирования": pile_age_days
        }

        # ❗️Вызвать predict
        try:
            print(f"DEBUG: Вызов predict_ignition_risk для склада {warehouse}, штабель {pile_id}")
            prediction = predict_ignition_risk(predict_data, session)
            print(f"DEBUG: Прогноз: {prediction}")

            predicted_date_str = prediction.get("predicted_ignition_date")

            if predicted_date_str:
                predicted_date = datetime.fromisoformat(predicted_date_str).date()

                if start_dt <= predicted_date <= end_dt:  # ❗️Проверка попадания в диапазон
                    incidents.append({
                        "date": predicted_date.isoformat(),
                        "warehouse": warehouse,
                        "pile_id": pile_id,
                        "predicted_ignition_date": predicted_date_str,
                        "message": prediction.get("message", "")
                    })
        except Exception as e:
            print(f"ERROR: Прогноз не удался для {warehouse}, {pile_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # ❗️Агрегировать по дням
    from collections import defaultdict
    summary_by_day = defaultdict(int)
    for inc in incidents:
        summary_by_day[inc["date"]] += 1

    # ❗️Заполнить все дни в диапазоне
    date_list = [(start_dt + timedelta(days=i)).isoformat() for i in range((end_dt - start_dt).days + 1)]
    final_summary = []
    for d in date_list:
        final_summary.append({
            "date": d,
            "count": summary_by_day[d]
        })

    print(f"DEBUG: Возвращаем {len(incidents)} инцидентов и {len(final_summary)} дней")

    return {
        "period": f"{start_date} — {end_date}",
        "summary_by_day": final_summary,
        "high_risk_incidents": incidents
    }