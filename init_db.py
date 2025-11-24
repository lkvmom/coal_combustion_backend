# init_db.py
from app.database import engine
from app.models.db_models import CurrentStockpile, ActualFire, Temperature, FireEvent, Weather, Supply

def create_tables():
    CurrentStockpile.metadata.create_all(engine)
    ActualFire.metadata.create_all(engine)
    Temperature.metadata.create_all(engine)
    FireEvent.metadata.create_all(engine)
    Weather.metadata.create_all(engine)
    Supply.metadata.create_all(engine)  # ← добавь эту строку
    print("✅ Все таблицы созданы.")

if __name__ == "__main__":
    create_tables()