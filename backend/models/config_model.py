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
    language: str = "en-US"
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
    max_messages: int = Field(32, alias="maxMessages")
    look_back_to_today: bool = Field(True, alias="lookBackToToday")

    class Config:
        allow_population_by_field_name = True


class RAGSearchStrategyDailySummary(BaseModel):
    enabled: bool = True
    look_back_days: int = Field(7, alias="lookBackDays")
    use_tags: bool = Field(True, alias="useTags")

    class Config:
        allow_population_by_field_name = True


class RAGSearchStrategyLongTermMemory(BaseModel):
    enabled: bool = True
    vector_search: bool = Field(True, alias="vectorSearch")
    graph_search: bool = Field(True, alias="graphSearch")
    priority_rules: bool = Field(True, alias="priorityRules")

    class Config:
        allow_population_by_field_name = True


class RAGSearchStrategyFallback(BaseModel):
    ask_user: bool = Field(True, alias="askUser")
    auto_learn: bool = Field(True, alias="autoLearn")

    class Config:
        allow_population_by_field_name = True


class RAGSearchStrategy(BaseModel):
    session_context: RAGSearchStrategySessionContext = Field(
        default_factory=RAGSearchStrategySessionContext, alias="sessionContext"
    )
    daily_summary: RAGSearchStrategyDailySummary = Field(
        default_factory=RAGSearchStrategyDailySummary, alias="dailySummary"
    )
    long_term_memory: RAGSearchStrategyLongTermMemory = Field(
        default_factory=RAGSearchStrategyLongTermMemory, alias="longTermMemory"
    )
    fallback: RAGSearchStrategyFallback = RAGSearchStrategyFallback()

    class Config:
        allow_population_by_field_name = True


class RAGMemoryFacts(BaseModel):
    enabled: bool = True
    priority_rules: List[str] = Field(
        default_factory=lambda: ["user", "name", "person"], alias="priorityRules"
    )
    auto_update: bool = Field(True, alias="autoUpdate")

    class Config:
        allow_population_by_field_name = True


class RAGMemoryGraph(BaseModel):
    enabled: bool = True
    relationships: bool = True
    inference: bool = True


class RAGMemory(BaseModel):
    facts: RAGMemoryFacts = RAGMemoryFacts()
    graph: RAGMemoryGraph = RAGMemoryGraph()


class RAGConfig(BaseModel):
    enabled: bool = True
    embedding_model: str = Field("all-MiniLM-L6-v2", alias="embeddingModel")
    vector_db_path: str = Field("./data/vector_db", alias="vectorDbPath")
    chunk_size: int = Field(500, alias="chunkSize")
    chunk_overlap: int = Field(50, alias="chunkOverlap")
    top_k: int = Field(5, alias="topK")
    similarity_threshold: float = Field(0.7, alias="similarityThreshold")
    enable_caching: bool = Field(True, alias="enableCaching")
    cache_ttl: int = Field(60, alias="cacheTtl")
    search_strategy: RAGSearchStrategy = Field(default_factory=RAGSearchStrategy, alias="searchStrategy")
    memory: RAGMemory = RAGMemory()
    retrieval: Dict[str, Any] = Field(default_factory=dict)
    lore: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        allow_population_by_field_name = True


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


class MoralProviderOllamaConfig(BaseModel):
    model: str = "llama3.2"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = 512


class MoralProviderOpenRouterConfig(BaseModel):
    api_key: str = ""
    model: str = "openai/gpt-4o-mini"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = 512


class MoralProvidersConfig(BaseModel):
    heuristic: Dict[str, Any] = Field(default_factory=dict)
    ollama: MoralProviderOllamaConfig = MoralProviderOllamaConfig()
    openrouter: MoralProviderOpenRouterConfig = MoralProviderOpenRouterConfig()


class MoralMatrixConfig(BaseModel):
    enabled: bool = True
    active_provider: str = "ollama"
    fallback_order: List[str] = Field(default_factory=lambda: ["openrouter", "heuristic"])
    providers: MoralProvidersConfig = MoralProvidersConfig()


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
    voice: "VoiceConfig" = None
    stt: "STTConfig" = None
    modules: "ModulesConfig" = None
    audio: "AudioConfig" = None
    vision: "VisionConfig" = None
    rag: "RAGConfig" = None
    analyzer: "AnalyzerConfig" = None
    moral: "MoralMatrixConfig" = None
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
