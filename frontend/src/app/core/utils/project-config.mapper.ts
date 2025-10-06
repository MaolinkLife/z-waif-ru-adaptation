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
    mapRagModelToDto
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
import { mapSystemDtoToModel, mapSystemModelToDto } from './system-config-mapper';
import { mapMemoryDtoToModel, mapMemoryModelToDto } from './memory-config-mapper';


export const mapProjectConfigDtoToModel = (dto: ProjectConfigDto): ProjectConfig => ({
    userId: dto.user_id,
    charName: dto.char_name,
    userName: dto.user_name,
    language: dto.language,
    voice: mapVoiceDtoToModel(dto.voice),
    modules: mapModulesDtoToModel(dto.modules),
    vision: mapVisionDtoToModel(dto.vision),
    audio: mapAudioDtoToModel(dto.audio),
    rag: mapRagDtoToModel(dto.rag),
    analyzer: mapAnalyzerDtoToModel(dto.analyzer),
    memory: mapMemoryDtoToModel(dto.memory),
    api: mapApiDtoToModel(dto.api),
    generateSettings: mapGenerationDtoToModel(dto.generate_settings),
    system: mapSystemDtoToModel(dto.system)
});

export const mapProjectConfigModelToDto = (model: ProjectConfig): ProjectConfigDto => ({
    user_id: model.userId,
    char_name: model.charName,
    user_name: model.userName,
    language: model.language,
    voice: mapVoiceModelToDto(model.voice),
    modules: mapModulesModelToDto(model.modules),
    vision: mapVisionModelToDto(model.vision),
    audio: mapAudioModelToDto(model.audio),
    rag: mapRagModelToDto(model.rag),
    analyzer: mapAnalyzerModelToDto(model.analyzer),
    memory: mapMemoryModelToDto(model.memory),
    api: mapApiModelToDto(model.api),
    generate_settings: mapGenerationModelToDto(model.generateSettings),
    system: mapSystemModelToDto(model.system),
});

export const mapPartialModelToDto = (
    model: Partial<ProjectConfig>
): Partial<ProjectConfigDto> => {
    const dto: Partial<ProjectConfigDto> = {};

    Object.keys(model).forEach((key) => {
        switch (key) {
            case 'userId':
                dto.user_id = model.userId;
                break;
            case 'charName':
                dto.char_name = model.charName;
                break;
            case 'userName':
                dto.user_name = model.userName;
                break;
            case 'language':
                dto.language = model.language;
                break;
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
                if (model.rag && Object.keys(model.rag).some((k) => k.includes('.'))) {
                    dto.rag = model.rag as any;
                } else {
                    dto.rag = mapRagModelToDto(model.rag!);
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
            case 'api':
                dto.api = mapApiModelToDto(model.api!);
                break;
            case 'generateSettings':
                dto.generate_settings = mapGenerationModelToDto(model.generateSettings!);
                break;
            case 'system':
                dto.system = mapSystemModelToDto(model.system!);
                break;
        }
    });

    return dto;
};
