from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Прогноз самовозгорания угля (Хакатон 2025)")
app.include_router(router)