export interface BaseConfigDto {
    user_id?: string;
    char_name?: string;
    user_name?: string;
    language?: string;
}

export interface VoiceModuleConfigDto {
    [key: string]: any;
}

export interface VoiceConfigDto {
    enabled: boolean;
    output_id: number;
    windows_output_id: number;
    language: string;
    use_rvc: boolean;
    voice_language: string;
    use_windows_output: boolean;
    streaming_tts: boolean;
    enable_fallback: boolean;
    active_module: string;
    voice_modules: VoiceModuleConfigDto;
}

export interface ModuleConfigDto {
    vtube_studio: boolean;
    whisper: boolean;
    minecraft: boolean;
    gaming: boolean;
    alarm: boolean;
    discord: boolean;
    rag: boolean;
    visual: boolean;
}

export interface AudioConfigDto {
    input_device_id?: number;
    sample_rate?: number;
    channels?: number;
    chunk_size?: number;
    enable_vad?: boolean;
    vad_threshold?: number;
    silence_timeout?: number;
    min_audio_length?: number;
    max_audio_length?: number;
    trigger_words?: string[];
    ignore_trigger_words?: boolean;
}

export interface VisionModuleConfigDto {
    [key: string]: any;
}

export interface VisionConfigDto {
    enabled: boolean;
    active_provider?: string;
    monitor_index: number;
    fps: number;
    buffer_sec: number;
    downscale_width: number;
    yolo_enabled: boolean;
    ocr_lang: string;
    ocr_min_conf: number;
    ocr_max_lines: number;
    region: any;
    capture_mode?: string;
    window_title?: string;
    window_process?: string;
    debug_save?: boolean;
    debug_path?: string;
    vision_modules: VisionModuleConfigDto;
}

export interface RagVectorProfileDto {
    label?: string;
    enabled?: boolean;
    provider?: string;
    model?: string;
    top_k?: number;
    threshold?: number;
    endpoint?: string;
    timeout?: number;
    max_retries?: number;
    retry_backoff?: number;
    device?: string;
}

export interface RagRetrievalDto {
    recent?: { limit?: number };
    session?: { enabled?: boolean; window?: string };
    keyword?: {
        enabled?: boolean;
        max_candidates?: number;
        min_score?: number;
        min_overlap?: number;
        boost_user?: number;
        boost_assistant?: number;
        stopwords?: string[];
    };
    vectors?: {
        primary?: string;
        profiles?: Record<string, RagVectorProfileDto>;
    };
    short_term?: { enabled?: boolean; threshold?: number };
    rerank?: {
        enabled?: boolean;
        top_n?: number;
        use_primary_rerank?: boolean;
        boost_recency?: number;
        weights?: {
            embedding?: number;
            keyword?: number;
            short_term?: number;
        };
    };
}

export interface RagLoreDto {
    top_k?: number;
    similarity_threshold?: number;
}

export interface RagConfigDto {
    enabled: boolean;
    embedding_model?: string;
    vector_db_path?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    top_k?: number;
    similarity_threshold?: number;
    enable_caching?: boolean;
    cache_ttl?: number;
    search_strategy?: any;
    memory?: any;
    retrieval?: RagRetrievalDto;
    lore?: RagLoreDto;
}

export interface AnalyzerProviderConfigDto {
    api_key?: string;
    model?: string;
    temperature?: number;
    max_tokens?: number;
}

export interface AnalyzerConfigDto {
    active_provider: string;
    fallback_order: string[];
    providers: {
        [key: string]: AnalyzerProviderConfigDto;
    };
}

export interface MoralProviderConfigDto {
    api_key?: string;
    model?: string;
    temperature?: number;
    max_tokens?: number;
}

export interface MoralConfigDto {
    enabled: boolean;
    active_provider: string;
    fallback_order: string[];
    providers: {
        heuristic?: Record<string, any>;
        ollama?: MoralProviderConfigDto;
        openrouter?: MoralProviderConfigDto;
    };
}

export interface MemoryConfigDto {
    recent_limit: number;
    similarity_threshold: number;
    session_window: string;
    session_enabled: boolean;
    embedding_provider: string;
    embedding_model: string;
}

export interface GeneratorProviderConfigDto {
    model: string;
    temperature: number;
    max_tokens: number;
    streaming?: boolean;
    api_key?: string;
    base_url?: string;
}

export interface ApiConfigDto {
    type: string;
    streaming: boolean;
    model: string;
    visual_model: string;
    token_limit: number;
    message_pair_limit: number;
    active_provider: string;
    fallback_order: string[];
    providers: {
        [key: string]: GeneratorProviderConfigDto;
    };
}

export interface GenerationConfigDto {
    temperature: number;
    min_p: number;
    top_p: number;
    top_k: number;
    repeat_penalty: number;
    stop: string[] | null;
    num_predict: number;
    name?: string;
    description?: string;
}

export interface SystemConfigDto {
    user_id?: string;
    user_name?: string;
    char_name?: string;
    system_prompt?: string;
    language?: string;
    theme?: string;
}

export interface ProjectConfigDto extends BaseConfigDto {
    voice: VoiceConfigDto;
    modules: ModuleConfigDto;
    audio: AudioConfigDto;
    vision: VisionConfigDto;
    rag: RagConfigDto;
    analyzer: AnalyzerConfigDto;
    moral: MoralConfigDto;
    memory: MemoryConfigDto;
    api: ApiConfigDto;
    generate_settings: GenerationConfigDto;
    system: SystemConfigDto;
}
