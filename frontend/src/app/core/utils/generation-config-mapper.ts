import { ProjectConfig } from '../models/project-config.model';

export const mapGenerationDtoToModel = (dto: any) => ({
    temperature: dto.temperature,
    minP: dto.min_p,
    topP: dto.top_p,
    topK: dto.top_k,
    repeatPenalty: dto.repeat_penalty,
    stop: dto.stop,
    numPredict: dto.num_predict,
    name: dto.name,
    description: dto.description,
});

export const mapGenerationModelToDto = (generation: ProjectConfig['generateSettings']) => ({
    temperature: generation.temperature,
    min_p: generation.minP,
    top_p: generation.topP,
    top_k: generation.topK,
    repeat_penalty: generation.repeatPenalty,
    stop: generation.stop,
    num_predict: generation.numPredict,
    name: generation.name,
    description: generation.description,
});
