import { ProjectConfigDto } from '../models/project-config.dto';
import { ProjectConfig } from '../models/project-config.model';
import {
    mapVisionDtoToModel,
    mapVisionModelToDto
} from './vision-config-mapper';
import {
    mapVoiceDtoToModel,
    mapVoiceModelToDto
} from './voice-config-mapper';
import {
    mapModulesDtoToModel,
    mapModulesModelToDto
} from './modules-config-mapper';
import {
    mapAudioDtoToModel,
    mapAudioModelToDto
} from './audio-config-mapper';
import {
    mapRagDtoToModel,
    mapRagModelToDto,
    mapPartialRagModelToDto
} from './rag-config-mapper';
import {
    mapAnalyzerDtoToModel,
    mapAnalyzerModelToDto
} from './analyzer-config-mapper';
import {
    mapApiDtoToModel,
    mapApiModelToDto
} from './api-config-mapper';
import {
    mapGenerationDtoToModel,
    mapGenerationModelToDto
} from './generation-config-mapper';
import {
    mapMoralDtoToModel,
    mapMoralModelToDto,
    mapMoralPartialModelToDto
} from './moral-config-mapper';
import { mapSystemDtoToModel, mapSystemModelToDto } from './system-config-mapper';
import { mapMemoryDtoToModel, mapMemoryModelToDto } from './memory-config-mapper';


export const mapProjectConfigDtoToModel = (dto: ProjectConfigDto): ProjectConfig => ({
    voice: mapVoiceDtoToModel(dto.voice),
    modules: mapModulesDtoToModel(dto.modules),
    vision: mapVisionDtoToModel(dto.vision),
    audio: mapAudioDtoToModel(dto.audio),
    rag: mapRagDtoToModel(dto.rag),
    analyzer: mapAnalyzerDtoToModel(dto.analyzer),
    moral: mapMoralDtoToModel(dto.moral),
    memory: mapMemoryDtoToModel(dto.memory),
    api: mapApiDtoToModel(dto.api),
    generateSettings: mapGenerationDtoToModel(dto.generate_settings),
    system: mapSystemDtoToModel(dto.system, dto.language)
});

export const mapProjectConfigModelToDto = (model: ProjectConfig): ProjectConfigDto => ({
    voice: mapVoiceModelToDto(model.voice),
    modules: mapModulesModelToDto(model.modules),
    vision: mapVisionModelToDto(model.vision),
    audio: mapAudioModelToDto(model.audio),
    rag: mapRagModelToDto(model.rag),
    analyzer: mapAnalyzerModelToDto(model.analyzer),
    moral: mapMoralModelToDto(model.moral),
    memory: mapMemoryModelToDto(model.memory),
    api: mapApiModelToDto(model.api),
    generate_settings: mapGenerationModelToDto(model.generateSettings),
    system: mapSystemModelToDto(model.system) as ProjectConfigDto['system'],
});

export const mapPartialModelToDto = (
    model: Partial<ProjectConfig>
): Partial<ProjectConfigDto> => {
    const dto: Partial<ProjectConfigDto> = {};

    const isFullRagConfig = (value: any): boolean => {
        if (!value || typeof value !== 'object') {
            return false;
        }
        const requiredKeys = [
            'enabled',
            'embeddingModel',
            'vectorDbPath',
            'chunkSize',
            'chunkOverlap',
            'topK',
            'similarityThreshold',
            'enableCaching',
            'cacheTtl',
            'retrieval',
            'lore',
            'searchStrategy',
            'memory',
        ];
        return requiredKeys.every((key) => key in value);
    };

    Object.keys(model).forEach((key) => {
        switch (key) {
            case 'voice':
                dto.voice = mapVoiceModelToDto(model.voice!);
                break;
            case 'modules':
                dto.modules = mapModulesModelToDto(model.modules!);
                break;
            case 'vision':
                dto.vision = mapVisionModelToDto(model.vision!);
                break;
            case 'audio':
                dto.audio = mapAudioModelToDto(model.audio!);
                break;
            case 'rag':
                if (model.rag) {
                    dto.rag = isFullRagConfig(model.rag)
                        ? mapRagModelToDto(model.rag as any)
                        : mapPartialRagModelToDto(model.rag);
                }
                break;
            case 'analyzer':
                if (model.analyzer && Object.keys(model.analyzer).some((k) => k.includes('.'))) {
                    dto.analyzer = model.analyzer as any;
                } else {
                    dto.analyzer = mapAnalyzerModelToDto(model.analyzer!);
                }
                break;
            case 'memory':
                dto.memory = mapMemoryModelToDto(model.memory);
                break;
            case 'moral':
                const moralDto = mapMoralPartialModelToDto(model.moral);
                if (moralDto && Object.keys(moralDto).length > 0) {
                    dto.moral = moralDto as any;
                }
                break;
            case 'api':
                dto.api = mapApiModelToDto(model.api!);
                break;
            case 'generateSettings':
                dto.generate_settings = mapGenerationModelToDto(model.generateSettings!);
                break;
            case 'system':
                dto.system = mapSystemModelToDto(model.system!) as ProjectConfigDto['system'];
                break;
        }
    });

    return dto;
};
