# init_db.py
from app.database import engine
from app.models.db_models import (
    CurrentStockpile,
    ActualFire,
    Temperature,
    FireEvent,
    Weather
)

def create_tables():
    # Создаём все таблицы
    CurrentStockpile.metadata.create_all(engine)
    ActualFire.metadata.create_all(engine)
    Temperature.metadata.create_all(engine)
    FireEvent.metadata.create_all(engine)
    Weather.metadata.create_all(engine)
    print("✅ Все таблицы созданы успешно.")

if __name__ == "__main__":
    create_tables()