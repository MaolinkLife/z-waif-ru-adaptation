# ===========================================================
# Module: config_model.py
# Purpose: Configuration data models and default values
# Used in: config_service.py, API routes, validation
# ===========================================================

from constants.settings import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, OPENROUTER_BASE_URL
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ---------------------------
# New: System + Core configs
# ---------------------------
class SystemConfig(BaseModel):
    user_id: Optional[str] = None
    user_name: str = "You"
    char_name: str = "Character Name"
    system_prompt: str = ""  # будет подтягиваться из characters/{char_name}.yaml
    theme: str = "default"


class CoreConfig(BaseModel):
    version: str = "1.0.0"
    env: str = "dev"
    debug: bool = False


class VoiceModulesElevenLabsConfig(BaseModel):
    api_key: str = ""
    voice_id: str = ""
    model_id: str = ""
    stability: float = 0.5
    similarity: float = 0.75


class VoiceModulesEdgeConfig(BaseModel):
    voice_language: str = "en-US-JennyNeural"


class VoiceConfig(BaseModel):
    enabled: bool = True
    output_id: int = 0
    windows_output_id: int = 0
    language: str = "en-US"
    use_rvc: bool = False
    use_windows_output: bool = False
    streaming_tts: bool = False
    enable_fallback: bool = True
    active_module: str = "edge"
    voice_modules: Dict[str, Any] = {
        "elevenlabs": {
            "api_key": "",
            "voice_id": "",
            "model_id": "",
            "stability": 0.5,
            "similarity": 0.75,
        },
        "edge": {"voice_language": "en-US-JennyNeural"},
    }
    voice_language: str = "en-US-JennyNeural"


class STTConfig(BaseModel):
    language: str = "en-US"
    auto_detect: bool = False


class ModulesConfig(BaseModel):
    vtube_studio: bool = False
    whisper: bool = True
    minecraft: bool = False
    gaming: bool = False
    alarm: bool = False
    discord: bool = False
    rag: bool = True
    visual: bool = True


class AudioConfig(BaseModel):
    input_device_id: int = 0
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    enable_vad: bool = True
    vad_threshold: float = 0.5
    silence_timeout: float = 3.0
    min_audio_length: float = 0.5
    max_audio_length: float = 120.0
    trigger_words: List[str] = []
    ignore_trigger_words: bool = True


class VisionModulesAppleVisionConfig(BaseModel):
    model_id: str = "apple/FastVLM-1.5B"
    max_tokens: int = 128


class VisionModulesLlavaConfig(BaseModel):
    model_id: str = "llava-hf/llava-1.5-7b-hf"
    max_tokens: int = 128


class VisionConfig(BaseModel):
    enabled: bool = True
    active_provider: str = "apple_vision"
    monitor_index: int = 0
    fps: int = 5
    buffer_sec: int = 4
    downscale_width: int = 1280
    yolo_enabled: bool = False
    ocr_lang: str = "eng"
    ocr_min_conf: int = 70
    ocr_max_lines: int = 5
    region: Optional[Any] = None
    capture_mode: str = "monitor"
    window_title: str = ""
    window_process: str = ""
    debug_save: bool = False
    debug_path: str = "./temp/vision"
    vision_modules: Dict[str, Any] = {
        "apple_vision": {"model_id": "apple/FastVLM-1.5B", "max_tokens": 128},
        "llava": {"model_id": "llava-hf/llava-1.5-7b-hf", "max_tokens": 128},
    }


class RAGSearchStrategySessionContext(BaseModel):
    enabled: bool = True
    maxMessages: int = 32
    lookBackToToday: bool = True


class RAGSearchStrategyDailySummary(BaseModel):
    enabled: bool = True
    lookBackDays: int = 7
    useTags: bool = True


class RAGSearchStrategyLongTermMemory(BaseModel):
    enabled: bool = True
    vectorSearch: bool = True
    graphSearch: bool = True
    priorityRules: bool = True


class RAGSearchStrategyFallback(BaseModel):
    askUser: bool = True
    autoLearn: bool = True


class RAGSearchStrategy(BaseModel):
    sessionContext: RAGSearchStrategySessionContext = RAGSearchStrategySessionContext()
    dailySummary: RAGSearchStrategyDailySummary = RAGSearchStrategyDailySummary()
    longTermMemory: RAGSearchStrategyLongTermMemory = RAGSearchStrategyLongTermMemory()
    fallback: RAGSearchStrategyFallback = RAGSearchStrategyFallback()


class RAGMemoryFacts(BaseModel):
    enabled: bool = True
    priorityRules: List[str] = ["user", "name", "person"]
    autoUpdate: bool = True


class RAGMemoryGraph(BaseModel):
    enabled: bool = True
    relationships: bool = True
    inference: bool = True


class RAGMemory(BaseModel):
    facts: RAGMemoryFacts = RAGMemoryFacts()
    graph: RAGMemoryGraph = RAGMemoryGraph()


class RAGConfig(BaseModel):
    enabled: bool = True
    embeddingModel: str = "all-MiniLM-L6-v2"
    vectorDbPath: str = "./data/vector_db"
    chunkSize: int = 500
    chunkOverlap: int = 50
    topK: int = 5
    similarityThreshold: float = 0.7
    enableCaching: bool = True
    cacheTtl: int = 60
    searchStrategy: RAGSearchStrategy = RAGSearchStrategy()
    memory: RAGMemory = RAGMemory()


class AnalyzerProviderOpenRouterConfig(BaseModel):
    api_key: str = ""
    model: str = "openai/gpt-4o-mini"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS


class AnalyzerProviderOllamaConfig(BaseModel):
    model: str = "llama3.2"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS


class AnalyzerProvidersConfig(BaseModel):
    openrouter: AnalyzerProviderOpenRouterConfig = AnalyzerProviderOpenRouterConfig()
    ollama: AnalyzerProviderOllamaConfig = AnalyzerProviderOllamaConfig()


class AnalyzerConfig(BaseModel):
    active_provider: str = "openrouter"
    fallback_order: List[str] = ["ollama"]
    providers: AnalyzerProvidersConfig = AnalyzerProvidersConfig()


class MemoryConfig(BaseModel):
    recent_limit: int = 32
    similarity_threshold: float = 0.7
    session_window: str = "day"
    session_enabled: bool = True
    embedding_provider: str = "auto"
    embedding_model: str = "nomic-embed-text"


class GeneratorProviderBaseConfig(BaseModel):
    model: str = "llama3.2"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS


class GeneratorProviderOllamaConfig(GeneratorProviderBaseConfig):
    streaming: bool = True


class GeneratorProviderOpenRouterConfig(GeneratorProviderBaseConfig):
    api_key: str = ""
    base_url: str = OPENROUTER_BASE_URL


class APIProvidersConfig(BaseModel):
    ollama: GeneratorProviderOllamaConfig = GeneratorProviderOllamaConfig()
    openrouter: GeneratorProviderOpenRouterConfig = GeneratorProviderOpenRouterConfig()


class APIConfig(BaseModel):
    type: str = "Ollama"
    streaming: bool = True
    model: str = "llama3.2"
    visual_model: str = "apple/FastVLM-1.5B"
    token_limit: int = 4096
    message_pair_limit: int = 10
    active_provider: str = "ollama"
    fallback_order: List[str] = Field(default_factory=list)
    providers: APIProvidersConfig = APIProvidersConfig()


class GenerateSettingsConfig(BaseModel):
    temperature: float = 0.85
    min_p: float = 0.05
    top_p: float = 0.9
    top_k: int = 50
    repeat_penalty: float = 1.2
    stop: Optional[Any] = None
    num_predict: int = 2048
    name: str = "Default"
    description: str = "Basic generation parameters"


# ---------------------------
# AppConfig
# ---------------------------
class AppConfig(BaseModel):
    system: SystemConfig = SystemConfig()
    core: CoreConfig = CoreConfig()
    user_id: Optional[str] = None
    char_name: str = "Character Name"
    user_name: str = "You"

    language: str = "en-US"
    voice: "VoiceConfig" = None
    stt: "STTConfig" = None
    modules: "ModulesConfig" = None
    audio: "AudioConfig" = None
    vision: "VisionConfig" = None
    rag: "RAGConfig" = None
    analyzer: "AnalyzerConfig" = None
    memory: "MemoryConfig" = None
    api: "APIConfig" = None
    generate_settings: "GenerateSettingsConfig" = None

    class Config:
        arbitrary_types_allowed = True


# Configuration paths for easy access
CONFIG_PATHS = {
    "config": "config/config.json",
    "presets": "config/generation_presets.json",
}
