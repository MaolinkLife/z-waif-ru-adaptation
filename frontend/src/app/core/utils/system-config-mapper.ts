import { ProjectConfig } from '../models/project-config.model';

export const mapSystemDtoToModel = (dto: any, language?: string) => {
    if (!dto || typeof dto !== 'object') {
        return {
            userId: "",
            charName: "",
            userName: "",
            systemPrompt: "",
            language: language || "en-US",
            theme: "Dark",
        };
    }

    return {
        userId: dto.user_id || "",
        charName: dto.char_name || "",
        userName: dto.user_name || "",
        systemPrompt: dto.system_prompt || "",
        language: dto.language || language || "en-US",
        theme: dto.theme || "Dark",
    };
};

export const mapSystemModelToDto = (system: ProjectConfig['system']) => ({
    user_id: system.userId,
    char_name: system.charName,
    user_name: system.userName,
    system_prompt: system.systemPrompt,
    language: system.language,
    theme: system.theme,
});
