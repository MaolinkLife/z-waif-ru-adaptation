import os
import json
from datetime import datetime, timezone
from services import database_service

HISTORY_DIR = os.path.join("storage", "history")  # путь к папке с .json

REQUIRED_KEYS = {"role", "content", "timestamp"}


def is_valid_message(msg):
    return isinstance(msg, dict) and REQUIRED_KEYS.issubset(msg.keys())


def migrate_history_file(filepath, character_name: str):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            messages = json.load(f)

        if not isinstance(messages, list):
            print(f"[❌] {filepath} — не список сообщений.")
            return

        print(
            f"[📥] Импорт: {filepath} ({len(messages)} шт.) → персонаж: {character_name}"
        )

        for idx, msg in enumerate(messages):
            if not is_valid_message(msg):
                print(f"[❌] Строка {idx+1} — неверный формат, пропущена.")
                continue

            try:
                timestamp = datetime.fromisoformat(
                    msg["timestamp"].replace("Z", "+00:00")
                )
            except Exception as e:
                print(f"[⚠️] Ошибка timestamp в строке {idx+1}, берём now(): {e}")
                timestamp = datetime.now(timezone.utc)

            database_service.add_message_to_history(
                character_name=character_name,
                role=msg["role"],
                content=msg["content"],
                timestamp=timestamp,
                tags=msg.get("tags", []),
            )

        print(f"[✅] {filepath} → успешно импортировано.\n")

    except Exception as e:
        print(f"[🔥] Ошибка при импорте {filepath}: {e}")


def run_migration():
    if not os.path.exists(HISTORY_DIR):
        print(f"[❌] Папка истории не найдена: {HISTORY_DIR}")
        return

    files = [
        f
        for f in os.listdir(HISTORY_DIR)
        if f.endswith(".out.json") or f.endswith(".json")
    ]
    if not files:
        print("[ℹ️] Нет файлов для миграции.")
        return

    for filename in files:
        # имя персонажа = имя файла без расширения
        char_name = (
            os.path.splitext(filename)[0].replace("_history", "").replace(".out", "")
        )
        filepath = os.path.join(HISTORY_DIR, filename)
        migrate_history_file(filepath, char_name)


if __name__ == "__main__":
    run_migration()
