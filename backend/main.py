# ==========================================================
# Module: main.py
# Purpose: Entry point to the LIM application. Launches FastAPI, connects routes, activates CORS
# Used: at startup of the entire system
# Features:
# - Connects configuration (config_service)
# - Enables CORS for communication with the front
# - Integrates ollama and config routes
# - Contains the /api/ping endpoint for checking the status
# =======================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.initialize import run_startup_checks

# Запускаем инициализацию ДО импортов маршрутов
run_startup_checks()

# Теперь можно импортировать маршруты, т.к. конфиг уже инициализирован
from routes.ollama_routes import router as ollama_router
from routes.config_routes import router as config_router
from routes.preset_routes import router as preset_router
from routes.logger_routes import router as logger_router
from routes.voice_routes import router as voice_router
from routes.lorebook_routes import router as lorebook_router
from routes.resources_routes import router as resources_router
from routes.ws_routes import ws_router
from routes.embed_routes import router as embed_router
from routes.vector_routes import router as vector_router
from routes.storage_routes import router as storage_router
from routes.memory_routes import router as memory_router

from loops.loop_core import run_loop

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or http://localhost:4200
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ollama_router)
app.include_router(config_router)
app.include_router(preset_router)
app.include_router(logger_router)
app.include_router(voice_router)
app.include_router(resources_router)
app.include_router(ws_router)
app.include_router(lorebook_router)
app.include_router(embed_router)
app.include_router(vector_router)
app.include_router(storage_router)
app.include_router(memory_router)

# Start background loops
run_loop()


@app.get("/api/ping")
def ping():
    return {"message": "pong"}
