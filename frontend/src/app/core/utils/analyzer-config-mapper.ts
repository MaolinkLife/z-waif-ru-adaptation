import { AnalyzerConfig, AnalyzerProviderConfig } from '../models/project-config.model';
import { AnalyzerConfigDto, AnalyzerProviderConfigDto } from '../models/project-config.dto';

// Вспомогательная функция для рекурсивного преобразования snake_case в camelCase
const snakeToCamel = (str: string): string => {
    return str.replace(/_([a-z])/g, (match) => match[1].toUpperCase());
};

// Вспомогательная функция для рекурсивного преобразования camelCase в snake_case
const camelToSnake = (str: string): string => {
    return str.replace(/([A-Z])/g, '_$1').toLowerCase();
};

// Рекурсивно преобразует snake_case в camelCase
const deepSnakeToCamel = (obj: any): any => {
    if (Array.isArray(obj)) {
        return obj.map(deepSnakeToCamel);
    } else if (obj !== null && typeof obj === 'object') {
        const converted: any = {};
        Object.keys(obj).forEach((key) => {
            const camelKey = snakeToCamel(key);
            converted[camelKey] = deepSnakeToCamel(obj[key]);
        });
        return converted;
    }
    return obj;
};

// Рекурсивно преобразует camelCase в snake_case
const deepCamelToSnake = (obj: any): any => {
    if (Array.isArray(obj)) {
        return obj.map(deepCamelToSnake);
    } else if (obj !== null && typeof obj === 'object') {
        const converted: any = {};
        Object.keys(obj).forEach((key) => {
            const snakeKey = camelToSnake(key);
            converted[snakeKey] = deepCamelToSnake(obj[key]);
        });
        return converted;
    }
    return obj;
};

export const mapAnalyzerDtoToModel = (dto?: any): AnalyzerConfig => {
    const model: Partial<AnalyzerConfig> = {};

    if (dto?.active_provider !== undefined) {
        model.activeProvider = dto.active_provider;
    }

    if (dto?.fallback_order !== undefined) {
        model.fallbackOrder = Array.isArray(dto.fallback_order)
            ? dto.fallback_order.filter((name: string): name is string => typeof name === 'string')
            : ['ollama'];
    }

    if (dto?.providers) {
        const providers: { [key: string]: AnalyzerProviderConfig } = {};

        Object.keys(dto.providers).forEach((providerName) => {
            const providerDto = dto.providers[providerName];

            // Преобразуем поля провайдера из snake_case в camelCase
            const mappedProvider = deepSnakeToCamel(providerDto);

            providers[providerName] = mappedProvider;
        });

        model.providers = providers;
    }

    return model as AnalyzerConfig;
};

export const mapAnalyzerModelToDto = (model: Partial<AnalyzerConfig>): AnalyzerConfigDto => {
    const dto: Partial<AnalyzerConfigDto> = {};

    if (model.activeProvider !== undefined) {
        dto.active_provider = model.activeProvider;
    }

    if (model.fallbackOrder !== undefined) {
        dto.fallback_order = model.fallbackOrder;
    }

    if (model.providers) {
        const providersDto: { [key: string]: AnalyzerProviderConfigDto } = {};

        Object.keys(model.providers).forEach((providerName) => {
            const providerModel = model.providers![providerName];

            // Преобразуем поля провайдера из camelCase в snake_case
            const mappedProvider = deepCamelToSnake(providerModel);

            providersDto[providerName] = mappedProvider;
        });

        dto.providers = providersDto;
    }

    return dto as AnalyzerConfigDto;
};
