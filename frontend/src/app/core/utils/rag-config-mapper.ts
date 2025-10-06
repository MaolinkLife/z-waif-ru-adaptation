import { ProjectConfig } from '../models/project-config.model';

export const mapRagDtoToModel = (dto: any) => ({
    enabled: dto.enabled ?? false,
    embeddingModel: dto.embedding_model,
    vectorDbPath: dto.vector_db_path,
    chunkSize: dto.chunk_size,
    chunkOverlap: dto.chunk_overlap,
    topK: dto.top_k,
    similarityThreshold: dto.similarity_threshold,
    enableCaching: dto.enable_caching,
    cacheTtl: dto.cache_ttl,
});

export const mapRagModelToDto = (rag: ProjectConfig['rag']) => ({
    enabled: rag.enabled,
    embedding_model: rag.embeddingModel,
    vector_db_path: rag.vectorDbPath,
    chunk_size: rag.chunkSize,
    chunk_overlap: rag.chunkOverlap,
    top_k: rag.topK,
    similarity_threshold: rag.similarityThreshold,
    enable_caching: rag.enableCaching,
    cache_ttl: rag.cacheTtl,
});
