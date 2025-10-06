# ==========================================================
# Module: db_core.py
# Purpose: Low-level DB core for SQLAlchemy
# - Defines engine, Base, SessionLocal
# - Responsible for schema creation
# - Works as foundation for higher-level services
# ==========================================================

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# =======================
# Config
# =======================
DB_PATH = os.path.join("storage", "database", "core.db")
DB_URL = f"sqlite:///{DB_PATH}"

# In the future you can switch to Postgres via ENV:
# DB_URL = os.getenv("DB_URL", f"sqlite:///{DB_PATH}")

# =======================
# Engine & Session
# =======================
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

# =======================
# Init schema
# =======================
def create_database():
    """Ensure DB directory exists and create schema if needed"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)
