import { MemoryConfigDto } from '../models/project-config.dto';
import { MemoryConfig } from '../models/project-config.model';

export const mapMemoryDtoToModel = (dto: MemoryConfigDto | undefined): MemoryConfig => ({
    recentLimit: dto?.recent_limit ?? 32,
    similarityThreshold: dto?.similarity_threshold ?? 0.7,
    sessionWindow: dto?.session_window ?? 'day',
    sessionEnabled: dto?.session_enabled ?? true,
    embeddingProvider: dto?.embedding_provider ?? 'auto',
    embeddingModel: dto?.embedding_model ?? 'nomic-embed-text',
});

export const mapMemoryModelToDto = (model: MemoryConfig | undefined): MemoryConfigDto => ({
    recent_limit: model?.recentLimit ?? 32,
    similarity_threshold: model?.similarityThreshold ?? 0.7,
    session_window: model?.sessionWindow ?? 'day',
    session_enabled: model?.sessionEnabled ?? true,
    embedding_provider: model?.embeddingProvider ?? 'auto',
    embedding_model: model?.embeddingModel ?? 'nomic-embed-text',
});
