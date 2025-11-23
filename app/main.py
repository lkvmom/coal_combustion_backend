from fastapi import FastAPI
from app.api.routes import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Прогноз самовозгорания угля (Хакатон)")
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ["http://localhost:3000"] для React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)