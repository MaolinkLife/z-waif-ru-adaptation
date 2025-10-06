# LIM – Project Architecture

## 📁 Directory Structure

| Folder / File        | Purpose |
|---------------------|---------|
| `main.py`           | Entry point: starts FastAPI, registers routes, enables CORS |
| `config/`           | Configuration data and parameter loaders |
| `routes/`           | API endpoints for interacting with the AI and configuration |
| `services/`         | Business logic layer between models/DB and the API |
| `core/`             | Core LIM mechanics: memory, emotions, routing, behaviour |
| `utils/`            | Stateless helper utilities |
| `storage_history/`  | Conversation history (when using the file-based implementation) |
| `temp/`             | Temporary files, caches, work-in-progress logic |

---

## 🧠 Key Modules and Responsibilities

### 📂 `core/`
- `memory_engine.py` – memory database access (CRUD, filtering, search)
- `router.py` – decision routing: behaviors and reaction selection
- `logger.py` – central logging facility
- `emotion_engine.py` – determine current emotional state
- `decision_router.py` – decision layer (respond, stay silent, clarify, etc.)

### 📂 `services/`
- `memory_service.py` – coordination layer over `memory_engine`
- `modules/ollama/client.py` – interaction with the local Ollama server
- `voice_service.py` – TTS and STT handling
- `history_service.py` – conversation history management
- `api_service.py` – prompt shaping and data aggregation

### 📂 `utils/`
- `prompt_builder.py` – assemble structured LLM prompts
- `character_loader.py` – load YAML persona profiles

---

## 📜 Architecture Rules

- Every file should begin with a short description of its responsibility.
- Each new module must be listed here with a concise summary.
- Comments should answer **“why is this needed?”** rather than just “what does it do?”.

---

## 🚧 Roadmap / MVP

- Add PostgreSQL support
- Split visible vs. hidden memory
- External API pipelines (Discord, Twitch, etc.) — **planned separately**
