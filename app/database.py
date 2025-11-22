from sqlmodel import create_engine
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/coal_hack")
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    from app.models.db_models import CurrentStockpile, ActualFire
    CurrentStockpile.metadata.create_all(engine)
    ActualFire.metadata.create_all(engine)