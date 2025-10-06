import os
import json
from datetime import datetime, timezone
from services import database_service

# 📁 Directory with exported history files
HISTORY_DIR = os.path.join("storage", "history")

# 🔍 Keys that must be present in every message
REQUIRED_KEYS = {"role", "content", "timestamp"}


def is_valid_message(msg):
    if not isinstance(msg, dict):
        return False
    return REQUIRED_KEYS.issubset(msg.keys())


def migrate_history_file(filepath, char_name):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            messages = json.load(f)

        if not isinstance(messages, list):
            print(f"[❌] Файл {filepath} не содержит список сообщений")
            return

        for idx, msg in enumerate(messages):
            if not is_valid_message(msg):
                print(f"[❌] Неверный формат в файле {filepath}, строка {idx + 1}")
                return

        print(f"[📥] Импорт: {filepath} → персонаж: {char_name} ({len(messages)} сообщений)")

        for msg in messages:
            try:
                timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
            except Exception as e:
                print(f"  [⚠️] Ошибка timestamp, использую текущую дату: {e}")
                timestamp = datetime.now(timezone.utc)

            database_service.add_message_to_history(
                character_name=char_name,
                role=msg["role"],
                content=msg["content"],
                timestamp=timestamp
            )

        print(f"[✅] Успешно импортировано: {filepath}\n")

    except Exception as e:
        print(f"[🔥] Ошибка при обработке {filepath}: {e}\n")


def run_migration():
    if not os.path.exists(HISTORY_DIR):
        print(f"[❌] Директория истории не найдена: {HISTORY_DIR}")
        return

    files = [f for f in os.listdir(HISTORY_DIR) if f.endswith("_history.json")]

    if not files:
        print("[ℹ️] Нет подходящих файлов для миграции.")
        return

    for filename in files:
        char_name = filename.split("_history.json")[0]
        filepath = os.path.join(HISTORY_DIR, filename)
        migrate_history_file(filepath, char_name)


if __name__ == "__main__":
    run_migration()
