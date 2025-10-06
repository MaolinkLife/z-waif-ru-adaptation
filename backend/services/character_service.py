# ==========================================================
# Module: character_service.py
# Purpose: CRUD for Character table
# ==========================================================
import os
import yaml
import uuid
from sqlalchemy.orm import Session
from models.models import Character
from services.db_core import SessionLocal
from services.config_service import get_config_value

CHARACTERS_DIR = "config/characters"


def get_or_create_character(name: str) -> Character:
    session: Session = SessionLocal()
    try:
        char = session.query(Character).filter_by(name=name).first()
        if char:
            return char
        new_char = Character(id=str(uuid.uuid4()), name=name)
        session.add(new_char)
        session.commit()
        session.refresh(new_char)
        return new_char
    finally:
        session.close()


def get_character(name: str) -> Character:
    session: Session = SessionLocal()
    try:
        return session.query(Character).filter_by(name=name).first()
    finally:
        session.close()


def get_character_prompt(char_name: str) -> str:
    file_path = os.path.join(CHARACTERS_DIR, f"{char_name}.yaml")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Character file {file_path} not found")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("prompt", "")


def save_character_prompt(char_name: str, prompt: str):
    # Сохраняем YAML-файл
    file_path = os.path.join(CHARACTERS_DIR, f"{char_name}.yaml")
    data = {"prompt": prompt}
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    # Создаём запись в БД, если ещё нет
    get_or_create_character(char_name)


def create_character_prompt(char_name: str, prompt: str):
    file_path = os.path.join(CHARACTERS_DIR, f"{char_name}.yaml")
    if os.path.exists(file_path):
        raise ValueError(f"Character {char_name} already exists")

    save_character_prompt(char_name, prompt)


def update_character_prompt(char_name: str, prompt: str):
    file_path = os.path.join(CHARACTERS_DIR, f"{char_name}.yaml")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Character file {file_path} not found")

    save_character_prompt(char_name, prompt)


def delete_character_prompt(char_name: str):
    # Удаляем YAML-файл
    file_path = os.path.join(CHARACTERS_DIR, f"{char_name}.yaml")
    if os.path.exists(file_path):
        os.remove(file_path)

    # Удаляем запись из БД
    session: Session = SessionLocal()
    try:
        char = session.query(Character).filter_by(name=char_name).first()
        if char:
            session.delete(char)
            session.commit()
    finally:
        session.close()
