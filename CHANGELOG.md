# 📦 Z-Waif RU Adaptation

### 🔖 Version 0.1.0 — "Первый шаг"

##### 📅 [Дата релиза: 2025-03-28]

---

#### 🔊 Аудио
- Добавлен выбор аудиовыхода в UI
- Поддержка стандартного Windows-вывода и виртуальных драйверов (VB Cable / VoiceMeeter)
- Конфигурация аудиовыхода через `config.json`
- Поддержка режима без RVC (экономия ресурсов для слабых машин)
- Настроена новая логика с поддержкой русского языка через `edge-tts`, `pydub` и `sounddevice`.

---

#### 🧠 Персонаж
- `char_name`, `character_card` перенесены в `config.json`
- Имя вайфу теперь можно менять прямо из UI
- Гибкая подгрузка `Lorebook` и `CharacterCard` по имени персонажа
- Удалён `.env`-зависимый `character_card.py`, логика централизована в `character_controller.py`

---

#### ⚙️ UI / Web
- Упрощена логика управления конфигами через UI
- Добавлен `refresh_character_name()`
- Чистка переменных, вынос значений в `config.json`
- Возможность отключения RVC mode из UI с помощью `Use RVC (VB-Cable Output)`

---

#### 📂 Файлы и структура
- Добавлен `.gitignore` для конфиденциальных и кэширующих файлов
- Создан `CHANGELOG.md`
- `README.md` адаптирован под новую структуру

---

This marks the beginning of a cleaner, modular and scalable Z-Waif experience. Stay tuned, мы только начали.
