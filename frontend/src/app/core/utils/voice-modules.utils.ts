// utils/voice-modules.utils.ts
export const snakeToCamel = (str: string): string => {
    return str.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
};

export const camelToSnake = (str: string): string => {
    return str.replace(/([A-Z])/g, '_$1').toLowerCase();
};

export const mapVoiceModulesDtoToModel = (voiceModulesDto: any): any => {
    if (!voiceModulesDto) return undefined;

    const model: any = {};

    Object.keys(voiceModulesDto).forEach(moduleName => {
        model[moduleName] = {};
        Object.keys(voiceModulesDto[moduleName] || {}).forEach(fieldName => {
            const camelFieldName = snakeToCamel(fieldName);
            model[moduleName][camelFieldName] = voiceModulesDto[moduleName][fieldName];
        });
    });

    return model;
};

export const mapVoiceModulesModelToDto = (voiceModulesModel: any): any => {
    if (!voiceModulesModel) return undefined;

    const dto: any = {};

    Object.keys(voiceModulesModel).forEach(moduleName => {
        dto[moduleName] = {};
        Object.keys(voiceModulesModel[moduleName] || {}).forEach(fieldName => {
            const snakeFieldName = camelToSnake(fieldName);
            dto[moduleName][snakeFieldName] = voiceModulesModel[moduleName][fieldName];
        });
    });

    return dto;
};
