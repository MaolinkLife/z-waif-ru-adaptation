# 💫 Z-Waif / AI Companion System

### 🇷🇺 RU Adaptation — localized fork

**System Version:** 0.5
**Document Version:** 1.1  
**Status:** Beta  
**Last Updated:** October 18, 2025  
**License:** Maolink Noncommercial License 1.0.0 (based on PolyForm NC)
**Support & Developers:** see [Contacts / Credits](#8-contacts--credits) section

---

## 🧠 1. Introduction

**Z-Waif** is an open-source platform for locally deploying an AI companion. It integrates dialogue, voice synthesis, visualization, behavioral logic, and deep customization.

### Components:

- **Ollama** — primary local LLM engine for dialogues
- **OpenRouter & external APIs** — cloud providers for extended capabilities
- **Z-Waif** — interface and logic: TTS, STT, RVC, VTube Studio, Lorebook, memory, etc.
- **RVC / Voice Changer** — voice synthesis and personalization
- **VTube Studio** — visual avatar
- **Whisper / STT** — speech recognition

_Goal: integrate everything in one place for convenient development and use._

---

## 🛣️ 2. Development Roadmap

_From simple chatbot to Jarvis-level AI companion_

| Stage | Content |
|-------|---------|
| **✅ 1. Basic Functions** | Installation, dialogue, TTS/STT, memory, modular architecture |
| **✅ 2. Personalization** | Logging, voice control, styles, configuration system |
| **✅ 3. Enhanced Assistance** | Full UI control, diagnostics, editors, multilingual support |
| **🔄 4. Semi-Autonomy** | Self-initiative, offline mode, creativity, internet access |
| **⏳ 5. Full Autonomy** | Self-learning, privacy, environment control |

---

## 🔧 3. What's Implemented (v0.1-v0.4)

### ✅ 3.1. Complete UI Management
- **Completely redesigned interface** — all settings accessible from UI
- **Visual editors** for memory, lorebook, system prompts
- **Theme support** — light/dark themes with preference saving
- **Advanced diagnostics panel** with visual debug log

### ✅ 3.2. Multilingual & Russian Localization
- **EN/RU interface switching**
- **Whisper adapted for Russian language**
- **STT improvements for Russian speech**
- **Full UTF-8 support** across all modules
- **JSON translation files** for system messages (partial)

### ✅ 3.3. Voice Interface
- **Voice selection** (Male/Female) from UI when RVC is disabled
- **VAD (Voice Activity Detection)** with wake words
- **Multi-provider TTS:** ElevenLabs → gTTS → pyttsx3 (offline)
- **Voice state control** (listening/waiting/speaking)

### ✅ 3.4. Memory & Intelligence
- **Lorebook in database** — auto-load deprecated, now part of DB
- **Hybrid search** — embeddings + vector + keywords
- **MemoryModule** with RAG search and metadata
- **LLM initiative** and provider chain

### ✅ 3.5. Platform & Architecture
- **Modular architecture** (voice, vision, memory, LLM)
- **SQLite database** with reasoning and media attachments
- **Unified configuration system** with UI↔backend sync

### ✅ 3.6. LLM Providers
- **Ollama** — primary local engine (replaces Oobabooga)
- **OpenRouter & external APIs** — cloud providers
- **Automatic failover** between providers
- **Unified API** for all sources

---

## 🔜 4. Upcoming Plans

### 🤖 4.1. Autonomy & Behavior
- Activity timers and reminder dialogues
- Behavioral patterns and emotional memory
- Extended initiative system

### 📡 4.2. Internet Access
- Online search and parsing (Wikipedia, news)
- Modes: Offline / Online / Auto

### 🎨 4.3. Content Generation
- Stable Diffusion integration (AUTOMATIC1111 API)
- "Draw..." commands with image generation

### 🧏‍♂️ 4.4. Documentation & Training
- Video tutorial for Z-Waif usage
- Real capabilities demonstration

---

## ❓ 5. FAQ

**Q1:** Do I need to edit configs manually?  
**A1:** **NO!** All settings available through intuitive UI.

**Q2:** Which LLMs are supported?  
**A2:** **Ollama (local)** + **OpenRouter & external APIs** (cloud)

**Q3:** Russian language support?  
**A3:** **Full support** — interface, STT, TTS, memory.

**Q4:** Can it work without internet?  
**A4:** **Yes.** Ollama works completely offline.

**Q5:** What's the minimum PC requirement?  
**A5:** Depends on Ollama model. 8 GB RAM minimum, 16+ GB recommended.

---

## ⚙️ 6. Technical Features

- **Zero-Code management** — everything through UI, no file editing needed
- **Hybrid memory** — vector search + keywords + RAG
- **Modular architecture** — voice/vision/memory work independently
- **Theme support** — light/dark themes with auto-saving
- **Ollama-centric** — optimized for modern local models

---

## 🚀 7. Conclusion

**Z-Waif 0.4 is a fully self-sufficient AI companion management system.**

No more editing configs, understanding code, or searching for settings in files. Everything — from voice selection to memory configuration — is available in a beautiful, intuitive interface.

**Key changes:**
- **Complete transition to Ollama** instead of Oobabooga
- **OpenRouter integration** and external APIs
- **Simplified installation** — fewer dependencies

The system sees, hears, remembers, and speaks in Russian, while the modular architecture allows easy functionality expansion. **Jarvis-mode is becoming reality!**

---

## 🤝 8. Contacts / Credits

**Original Z-Waif author:** [GitHub Link](https://github.com/SugarcaneDefender/z-waif)

**This fork and adaptation:** [Z-Waif-RU-Adaptation](https://github.com/MaolinkLife/z-waif-ru-adaptation/tree/main)

**Feedback:**  
Telegram with **Z-Waif** tag — @MaolinkLife or email maolink686@gmail.com

**Third-party projects:**
- Ollama: https://github.com/ollama/ollama
- OpenRouter: https://openrouter.ai
- RVC: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion  
- VTube Studio: https://store.steampowered.com/app/1325860/VTube_Studio/  
- Whisper: https://github.com/openai/whisper
