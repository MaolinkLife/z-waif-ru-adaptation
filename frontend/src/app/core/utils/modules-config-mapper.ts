import { ProjectConfig } from '../models/project-config.model';

export const mapModulesDtoToModel = (dto: any) => ({
    vtubeStudio: dto.vtube_studio,
    whisper: dto.whisper,
    minecraft: dto.minecraft,
    gaming: dto.gaming,
    alarm: dto.alarm,
    discord: dto.discord,
    rag: dto.rag,
    visual: dto.visual,
});

export const mapModulesModelToDto = (modules: ProjectConfig['modules']) => ({
    vtube_studio: modules.vtubeStudio,
    whisper: modules.whisper,
    minecraft: modules.minecraft,
    gaming: modules.gaming,
    alarm: modules.alarm,
    discord: modules.discord,
    rag: modules.rag,
    visual: modules.visual,
});
