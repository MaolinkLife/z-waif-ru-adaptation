import { ProjectConfig } from '../models/project-config.model';

export const mapVoiceDtoToModel = (dto: any) => {
    const model: any = {
        enabled: dto.enabled,
        outputId: dto.output_id,
        windowsOutputId: dto.windows_output_id,
        language: dto.language,
        useRvc: dto.use_rvc,
        voiceLanguage: dto.voice_language,
        useWindowsOutput: dto.use_windows_output,
        streamingTts: dto.streaming_tts,
        enableFallback: dto.enable_fallback,
        activeModule: dto.active_module,
    };

    if (dto.voice_modules) {
        model.voiceModules = {};

        Object.keys(dto.voice_modules).forEach(moduleName => {
            model.voiceModules[moduleName] = {};
            Object.keys(dto.voice_modules[moduleName] || {}).forEach(fieldName => {
                const camelFieldName = fieldName.replace(/_([a-z])/g, (m) => m[1].toUpperCase());
                model.voiceModules[moduleName][camelFieldName] = dto.voice_modules[moduleName][fieldName];
            });
        });
    }

    return model;
};

export const mapVoiceModelToDto = (voice: ProjectConfig['voice']) => {
    const dto: any = {
        enabled: voice.enabled,
        output_id: voice.outputId,
        windows_output_id: voice.windowsOutputId,
        language: voice.language,
        use_rvc: voice.useRvc,
        voice_language: voice.voiceLanguage,
        use_windows_output: voice.useWindowsOutput,
        streaming_tts: voice.streamingTts,
        enable_fallback: voice.enableFallback,
        active_module: voice.activeModule,
    };

    if (voice.voiceModules) {
        dto.voice_modules = {};

        Object.keys(voice.voiceModules).forEach(moduleName => {
            dto.voice_modules[moduleName] = {};
            Object.keys(voice.voiceModules[moduleName] || {}).forEach(fieldName => {
                const snakeFieldName = fieldName.replace(/([A-Z])/g, '_$1').toLowerCase();
                dto.voice_modules[moduleName][snakeFieldName] = voice.voiceModules[moduleName][fieldName];
            });
        });
    }

    return dto;
};
