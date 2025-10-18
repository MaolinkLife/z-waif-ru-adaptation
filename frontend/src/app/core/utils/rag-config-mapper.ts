import { RagConfig, RagVectorProfile } from '../models/project-config.model';
import {
    RagConfigDto,
    RagRetrievalDto,
    RagVectorProfileDto,
} from '../models/project-config.dto';

const DEFAULT_VECTOR_PROFILES: Record<string, RagVectorProfile> = {
    embed768: {
        label: '768d • nomic-embed-text',
        enabled: true,
        provider: 'ollama',
        model: 'nomic-embed-text',
        topK: 8,
        threshold: 0.9,
        endpoint: 'http://localhost:11434/api/embeddings',
        timeout: 30,
        maxRetries: 2,
        retryBackoff: 0.75,
    },
    embed384: {
        label: '384d • all-MiniLM-L6-v2',
        enabled: true,
        provider: 'st',
        model: 'all-MiniLM-L6-v2',
        topK: 10,
        threshold: 0.9,
        device: 'cpu',
    },
};

const cloneDefaultProfiles = (): Record<string, RagVectorProfile> =>
    Object.entries(DEFAULT_VECTOR_PROFILES).reduce<Record<string, RagVectorProfile>>(
        (acc, [key, profile]) => {
            acc[key] = { ...profile };
            return acc;
        },
        {},
    );

const toOptionalNumber = (value: unknown): number | undefined => {
    if (value === null || value === undefined || value === '') {
        return undefined;
    }
    const num = Number(value);
    return Number.isFinite(num) ? num : undefined;
};

const mapVectorProfilesDtoToModel = (
    profiles: Record<string, RagVectorProfileDto> | undefined,
): Record<string, RagVectorProfile> => {
    if (!profiles) {
        return {};
    }

    return Object.entries(profiles).reduce<Record<string, RagVectorProfile>>(
        (acc, [key, profile]) => {
            const defaults = DEFAULT_VECTOR_PROFILES[key] || {};
            acc[key] = {
                label: profile?.label ?? defaults.label ?? key,
                enabled: profile?.enabled ?? defaults.enabled ?? true,
                provider: profile?.provider ?? defaults.provider ?? 'auto',
                model: profile?.model ?? defaults.model ?? '',
                topK: profile?.top_k ?? defaults.topK ?? 5,
                threshold: profile?.threshold ?? defaults.threshold ?? 0.9,
                endpoint: profile?.endpoint ?? defaults.endpoint,
                timeout: toOptionalNumber(
                    profile?.timeout ?? defaults.timeout,
                ),
                maxRetries: toOptionalNumber(
                    profile?.max_retries ?? defaults.maxRetries,
                ),
                retryBackoff: toOptionalNumber(
                    profile?.retry_backoff ?? defaults.retryBackoff,
                ),
                device: profile?.device ?? defaults.device,
            };
            return acc;
        },
        {},
    );
};

const mapVectorProfilesModelToDto = (
    profiles: Record<string, RagVectorProfile> | undefined,
): Record<string, RagVectorProfileDto> => {
    if (!profiles) {
        return {};
    }

    return Object.entries(profiles).reduce<Record<string, RagVectorProfileDto>>(
        (acc, [key, profile]) => {
            const dto: RagVectorProfileDto = {
                label: profile.label,
                enabled: profile.enabled,
                provider: profile.provider,
                model: profile.model,
                top_k: profile.topK,
                threshold: profile.threshold,
            };
            if (profile.endpoint) {
                dto.endpoint = profile.endpoint;
            }
            const timeout = toOptionalNumber(profile.timeout);
            if (timeout !== undefined) {
                dto.timeout = timeout;
            }
            const maxRetries = toOptionalNumber(profile.maxRetries);
            if (maxRetries !== undefined) {
                dto.max_retries = maxRetries;
            }
            const retryBackoff = toOptionalNumber(profile.retryBackoff);
            if (retryBackoff !== undefined) {
                dto.retry_backoff = retryBackoff;
            }
            if (profile.device) {
                dto.device = profile.device;
            }
            acc[key] = dto;
            return acc;
        },
        {},
    );
};

const mapRetrievalDtoToModel = (dto: RagRetrievalDto | undefined) => {
    if (!dto) {
        return undefined;
    }

    const keywordDto = dto.keyword ?? {};
    const vectorsDto = dto.vectors ?? {};
    const shortTermDto = dto.short_term ?? {};
    const rerankDto = dto.rerank ?? {};
    const weightsDto = rerankDto.weights ?? {};

    const retrieval = {
        recent: {
            limit: dto.recent?.limit ?? 32,
        },
        session: {
            enabled: dto.session?.enabled ?? true,
            window: dto.session?.window ?? 'day',
        },
        keyword: {
            enabled: keywordDto.enabled ?? true,
            maxCandidates: keywordDto.max_candidates ?? 8,
            minScore: keywordDto.min_score ?? 0.2,
            minOverlap: keywordDto.min_overlap ?? 0.25,
            boostUser: keywordDto.boost_user ?? 1.0,
            boostAssistant: keywordDto.boost_assistant ?? 1.0,
            stopwords: keywordDto.stopwords ?? [],
        },
        vectors: {
            primary: vectorsDto.primary ?? '',
            profiles: mapVectorProfilesDtoToModel(vectorsDto.profiles),
        },
        shortTerm: {
            enabled: shortTermDto.enabled ?? true,
            threshold: shortTermDto.threshold ?? 0.6,
        },
        rerank: {
            enabled: rerankDto.enabled ?? true,
            topN: rerankDto.top_n ?? 5,
            usePrimaryRerank: rerankDto.use_primary_rerank ?? true,
            boostRecency: rerankDto.boost_recency ?? 0,
            weights: {
                embedding: weightsDto.embedding ?? 0.7,
                keyword: weightsDto.keyword ?? 0.2,
                shortTerm: weightsDto.short_term ?? 0.1,
            },
        },
    };

    const profiles = retrieval.vectors.profiles;
    if (!profiles || Object.keys(profiles).length === 0) {
        retrieval.vectors.profiles = cloneDefaultProfiles();
    }
    if (
        !retrieval.vectors.primary ||
        !retrieval.vectors.profiles[retrieval.vectors.primary]
    ) {
        const firstProfileKey = Object.keys(retrieval.vectors.profiles)[0];
        retrieval.vectors.primary = firstProfileKey;
    }

    return retrieval;
};

const mapRetrievalModelToDto = (retrieval: RagConfig['retrieval'] | undefined): RagRetrievalDto | undefined => {
    if (!retrieval) {
        return undefined;
    }

    return {
        recent: { limit: retrieval.recent.limit },
        session: {
            enabled: retrieval.session.enabled,
            window: retrieval.session.window,
        },
        keyword: {
            enabled: retrieval.keyword.enabled,
            max_candidates: retrieval.keyword.maxCandidates,
            min_score: retrieval.keyword.minScore,
            min_overlap: retrieval.keyword.minOverlap,
            boost_user: retrieval.keyword.boostUser,
            boost_assistant: retrieval.keyword.boostAssistant,
            stopwords: retrieval.keyword.stopwords,
        },
        vectors: {
            primary: retrieval.vectors.primary,
            profiles: mapVectorProfilesModelToDto(retrieval.vectors.profiles),
        },
        short_term: {
            enabled: retrieval.shortTerm.enabled,
            threshold: retrieval.shortTerm.threshold,
        },
        rerank: {
            enabled: retrieval.rerank.enabled,
            top_n: retrieval.rerank.topN,
            use_primary_rerank: retrieval.rerank.usePrimaryRerank,
            boost_recency: retrieval.rerank.boostRecency,
            weights: {
                embedding: retrieval.rerank.weights.embedding,
                keyword: retrieval.rerank.weights.keyword,
                short_term: retrieval.rerank.weights.shortTerm,
            },
        },
    };
};

export const mapRagDtoToModel = (dto: RagConfigDto | null | undefined): RagConfig => {
    const retrieval = mapRetrievalDtoToModel(dto?.retrieval);

    return {
        enabled: dto?.enabled ?? false,
        embeddingModel: dto?.embedding_model,
        vectorDbPath: dto?.vector_db_path,
        chunkSize: dto?.chunk_size,
        chunkOverlap: dto?.chunk_overlap,
        topK: dto?.top_k,
        similarityThreshold: dto?.similarity_threshold,
        enableCaching: dto?.enable_caching,
        cacheTtl: dto?.cache_ttl,
        retrieval,
        lore: dto?.lore
            ? {
                  topK: dto.lore.top_k ?? 3,
                  similarityThreshold: dto.lore.similarity_threshold ?? 0.7,
              }
            : undefined,
    };
};

export const mapRagModelToDto = (rag: RagConfig): RagConfigDto => {
    const retrieval = mapRetrievalModelToDto(rag.retrieval);

    return {
        enabled: rag.enabled,
        embedding_model: rag.embeddingModel,
        vector_db_path: rag.vectorDbPath,
        chunk_size: rag.chunkSize,
        chunk_overlap: rag.chunkOverlap,
        top_k: rag.topK,
        similarity_threshold: rag.similarityThreshold,
        enable_caching: rag.enableCaching,
        cache_ttl: rag.cacheTtl,
        retrieval,
        lore: rag.lore
            ? {
                  top_k: rag.lore.topK,
                  similarity_threshold: rag.lore.similarityThreshold,
              }
            : undefined,
    };
};
