import { MoralConfigDto, MoralProviderConfigDto } from '../models/project-config.dto';
import { MoralConfig, MoralProviderConfig } from '../models/project-config.model';

const mapProviderDtoToModel = (dto?: MoralProviderConfigDto): MoralProviderConfig | undefined => {
    if (!dto) {
        return undefined;
    }
    return {
        apiKey: dto.api_key,
        model: dto.model,
        temperature: dto.temperature,
        maxTokens: dto.max_tokens,
    };
};

const mapProviderModelToDto = (config?: MoralProviderConfig): MoralProviderConfigDto | undefined => {
    if (!config) {
        return undefined;
    }
    return {
        api_key: config.apiKey,
        model: config.model,
        temperature: config.temperature,
        max_tokens: config.maxTokens,
    };
};

export const mapMoralDtoToModel = (dto?: MoralConfigDto): MoralConfig => ({
    enabled: dto?.enabled ?? true,
    activeProvider: dto?.active_provider ?? 'heuristic',
    fallbackOrder: dto?.fallback_order ?? [],
    providers: {
        heuristic: dto?.providers?.heuristic ?? {},
        ollama: mapProviderDtoToModel(dto?.providers?.ollama),
        openrouter: mapProviderDtoToModel(dto?.providers?.openrouter),
    },
});

export const mapMoralModelToDto = (model?: MoralConfig): MoralConfigDto => ({
    enabled: model?.enabled ?? true,
    active_provider: model?.activeProvider ?? 'heuristic',
    fallback_order: model?.fallbackOrder ?? [],
    providers: {
        heuristic: model?.providers?.heuristic ?? {},
        ollama: mapProviderModelToDto(model?.providers?.ollama),
        openrouter: mapProviderModelToDto(model?.providers?.openrouter),
    },
});

export const mapMoralPartialModelToDto = (
    model?: Partial<MoralConfig>
): Partial<MoralConfigDto> | undefined => {
    if (!model) {
        return undefined;
    }

    const dto: Partial<MoralConfigDto> = {};

    if (model.enabled !== undefined) {
        dto.enabled = model.enabled;
    }

    if (model.activeProvider !== undefined) {
        dto.active_provider = model.activeProvider;
    }

    if (model.fallbackOrder !== undefined) {
        dto.fallback_order = model.fallbackOrder;
    }

    if (model.providers !== undefined) {
        const providersDto: Partial<MoralConfigDto['providers']> = {};
        const providers = model.providers;

        if (providers.heuristic !== undefined) {
            providersDto.heuristic = providers.heuristic;
        }

        if (providers.ollama !== undefined) {
            const ollama = providers.ollama;
            if (ollama) {
                providersDto.ollama = {};
                if (ollama.model !== undefined) {
                    providersDto.ollama.model = ollama.model;
                }
                if (ollama.temperature !== undefined) {
                    providersDto.ollama.temperature = ollama.temperature;
                }
                if (ollama.maxTokens !== undefined) {
                    providersDto.ollama.max_tokens = ollama.maxTokens;
                }
            } else {
                providersDto.ollama = undefined;
            }
        }

        if (providers.openrouter !== undefined) {
            const openrouter = providers.openrouter;
            if (openrouter) {
                providersDto.openrouter = {};
                if (openrouter.apiKey !== undefined) {
                    providersDto.openrouter.api_key = openrouter.apiKey;
                }
                if (openrouter.model !== undefined) {
                    providersDto.openrouter.model = openrouter.model;
                }
                if (openrouter.temperature !== undefined) {
                    providersDto.openrouter.temperature = openrouter.temperature;
                }
                if (openrouter.maxTokens !== undefined) {
                    providersDto.openrouter.max_tokens = openrouter.maxTokens;
                }
            } else {
                providersDto.openrouter = undefined;
            }
        }

        if (Object.keys(providersDto).length > 0) {
            dto.providers = providersDto as MoralConfigDto['providers'];
        }
    }

    return Object.keys(dto).length > 0 ? dto : undefined;
};
