export interface ProjectConfig {
    voice: VoiceConfig;
    modules: ModuleConfig;
    vision: VisionConfig;
    audio: AudioConfig;
    rag: RagConfig;
    api: ApiConfig;
    analyzer: AnalyzerConfig;
    moral: MoralConfig;
    memory: MemoryConfig;
    generateSettings: GenerationConfig;
    system: SystemConfig;
}

export interface VoiceConfig {
    enabled: boolean;
    outputId: number;
    windowsOutputId: number;
    language: string;
    useRvc: boolean;
    voiceLanguage: string;
    useWindowsOutput: boolean;
    streamingTts: boolean;
    enableFallback: boolean;
    activeModule: string;
    voiceModules: Record<string, any>
}

export interface ModuleConfig {
    vtubeStudio: boolean;
    whisper: boolean;
    minecraft: boolean;
    gaming: boolean;
    alarm: boolean;
    discord: boolean;
    rag: boolean;
    visual: boolean;
}

export type VisionModuleConfig = Record<string, any>;

export interface SystemConfig {
    userId: string;
    charName: string;
    userName: string;
    systemPrompt: string;
    language: string;
    theme: string;
}

export interface VisionConfig {
    enabled: boolean;
    activeProvider: string;
    monitorIndex: number;
    fps: number;
    bufferSec: number;
    downscaleWidth: number;
    yoloEnabled: boolean;
    ocrLang: string;
    ocrMinConf: number;
    ocrMaxLines: number;
    region: any;
    captureMode: string;
    windowTitle: string;
    windowProcess: string;
    debugSave: boolean;
    debugPath: string;
    visionModules: Record<string, VisionModuleConfig>;
}

export interface AnalyzerProviderConfig {
    apiKey?: string;
    model?: string;
    temperature?: number;
    maxTokens?: number;
}

export interface AnalyzerConfig {
    activeProvider: string;
    fallbackOrder: string[];
    providers: {
        [key: string]: AnalyzerProviderConfig;
    };
}

export interface MoralProviderConfig {
    model?: string;
    temperature?: number;
    maxTokens?: number;
    apiKey?: string;
}

export interface MoralProvidersConfig {
    heuristic?: Record<string, any>;
    ollama?: MoralProviderConfig;
    openrouter?: MoralProviderConfig;
}

export interface MoralConfig {
    enabled: boolean;
    activeProvider: string;
    fallbackOrder: string[];
    providers: MoralProvidersConfig;
}

export interface MemoryConfig {
    recentLimit: number;
    similarityThreshold: number;
    sessionWindow: string;
    sessionEnabled: boolean;
    embeddingProvider: string;
    embeddingModel: string;
}

export interface AudioConfig {
    inputDeviceId?: number;
    sampleRate?: number;
    channels?: number;
    chunkSize?: number;
    enableVad?: boolean;
    vadThreshold?: number;
    silenceTimeout?: number;
    minAudioLength?: number;
    maxAudioLength?: number;
    triggerWords?: string[];
    ignoreTriggerWords?: boolean;
}

export interface RagKeywordConfig {
    enabled: boolean;
    maxCandidates: number;
    minScore: number;
    minOverlap: number;
    boostUser: number;
    boostAssistant: number;
    stopwords: string[];
}

export interface RagVectorProfile {
    label?: string;
    enabled: boolean;
    provider: string;
    model: string;
    topK: number;
    threshold: number;
    endpoint?: string;
    timeout?: number;
    maxRetries?: number;
    retryBackoff?: number;
    device?: string;
}

export interface RagVectorsConfig {
    primary: string;
    profiles: Record<string, RagVectorProfile>;
}

export interface RagShortTermConfig {
    enabled: boolean;
    threshold: number;
}

export interface RagRerankWeights {
    embedding: number;
    keyword: number;
    shortTerm: number;
}

export interface RagRerankConfig {
    enabled: boolean;
    topN: number;
    usePrimaryRerank: boolean;
    boostRecency: number;
    weights: RagRerankWeights;
}

export interface RagRetrievalConfig {
    recent: { limit: number };
    session: { enabled: boolean; window: string };
    keyword: RagKeywordConfig;
    vectors: RagVectorsConfig;
    shortTerm: RagShortTermConfig;
    rerank: RagRerankConfig;
}

export interface RagLoreConfig {
    topK: number;
    similarityThreshold: number;
}

export interface RagConfig {
    enabled: boolean;
    embeddingModel?: string;
    vectorDbPath?: string;
    chunkSize?: number;
    chunkOverlap?: number;
    topK?: number;
    similarityThreshold?: number;
    enableCaching?: boolean;
    cacheTtl?: number;
    retrieval?: RagRetrievalConfig;
    lore?: RagLoreConfig;
    searchStrategy?: any;
    memory?: any;
}

export interface ApiConfig {
    type: string;
    streaming: boolean;
    model: string;
    visualModel: string;
    tokenLimit: number;
    messagePairLimit: number;
    activeProvider: string;
    fallbackOrder: string[];
    providers: Record<string, GeneratorProviderConfig>;
}

export interface GenerationConfig {
    temperature: number;
    minP: number;
    topP: number;
    topK: number;
    repeatPenalty: number;
    stop: string[] | null;
    numPredict: number;
    name?: string;
    description?: string;
}

export interface GeneratorProviderConfig {
    model: string;
    temperature: number;
    maxTokens: number;
    streaming?: boolean;
    apiKey?: string;
    baseUrl?: string;
}
