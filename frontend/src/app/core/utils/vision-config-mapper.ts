import { ProjectConfig } from '../models/project-config.model';
import { ProjectConfigDto } from '../models/project-config.dto';

const snakeToCamel = (str: string): string => str.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
const camelToSnake = (str: string): string => str.replace(/([A-Z])/g, '_$1').toLowerCase();

const deepSnakeToCamel = (value: any): any => {
    if (Array.isArray(value)) {
        return value.map(deepSnakeToCamel);
    }

    if (value !== null && typeof value === 'object') {
        return Object.keys(value).reduce((acc: Record<string, any>, key: string) => {
            acc[snakeToCamel(key)] = deepSnakeToCamel(value[key]);
            return acc;
        }, {});
    }

    return value;
};

const deepCamelToSnake = (value: any): any => {
    if (Array.isArray(value)) {
        return value.map(deepCamelToSnake);
    }

    if (value !== null && typeof value === 'object') {
        return Object.keys(value).reduce((acc: Record<string, any>, key: string) => {
            acc[camelToSnake(key)] = deepCamelToSnake(value[key]);
            return acc;
        }, {});
    }

    return value;
};

export function mapVisionDtoToModel(dtoVision: ProjectConfigDto['vision']): ProjectConfig['vision'] {
    const modules = dtoVision?.vision_modules
        ? Object.keys(dtoVision.vision_modules).reduce((acc: Record<string, any>, providerName: string) => {
            acc[providerName] = deepSnakeToCamel(dtoVision.vision_modules[providerName]);
            return acc;
        }, {})
        : {};

    return {
        enabled: dtoVision?.enabled ?? false,
        activeProvider: dtoVision?.active_provider || 'apple_vision',
        monitorIndex: dtoVision?.monitor_index ?? 0,
        fps: dtoVision?.fps ?? 5,
        bufferSec: dtoVision?.buffer_sec ?? 4,
        downscaleWidth: dtoVision?.downscale_width ?? 1280,
        yoloEnabled: dtoVision?.yolo_enabled ?? false,
        ocrLang: dtoVision?.ocr_lang ?? 'eng',
        ocrMinConf: dtoVision?.ocr_min_conf ?? 70,
        ocrMaxLines: dtoVision?.ocr_max_lines ?? 5,
        region: dtoVision?.region ?? null,
        captureMode: dtoVision?.capture_mode || 'monitor',
        windowTitle: dtoVision?.window_title || '',
        windowProcess: dtoVision?.window_process || '',
        debugSave: dtoVision?.debug_save ?? true,
        debugPath: dtoVision?.debug_path || './temp/vision',
        visionModules: modules,
    };
}

export function mapVisionModelToDto(vision: Partial<ProjectConfig['vision']>): ProjectConfigDto['vision'] {
    const dto: Record<string, any> = {};

    if (vision && 'enabled' in vision) {
        dto.enabled = vision.enabled;
    }
    if (vision && 'activeProvider' in vision) {
        dto.active_provider = vision.activeProvider;
    }
    if (vision && 'monitorIndex' in vision) {
        dto.monitor_index = vision.monitorIndex;
    }
    if (vision && 'fps' in vision) {
        dto.fps = vision.fps;
    }
    if (vision && 'bufferSec' in vision) {
        dto.buffer_sec = vision.bufferSec;
    }
    if (vision && 'downscaleWidth' in vision) {
        dto.downscale_width = vision.downscaleWidth;
    }
    if (vision && 'yoloEnabled' in vision) {
        dto.yolo_enabled = vision.yoloEnabled;
    }
    if (vision && 'ocrLang' in vision) {
        dto.ocr_lang = vision.ocrLang;
    }
    if (vision && 'ocrMinConf' in vision) {
        dto.ocr_min_conf = vision.ocrMinConf;
    }
    if (vision && 'ocrMaxLines' in vision) {
        dto.ocr_max_lines = vision.ocrMaxLines;
    }
    if (vision && 'region' in vision) {
        dto.region = vision.region;
    }
    if (vision && 'captureMode' in vision) {
        dto.capture_mode = vision.captureMode;
    }
    if (vision && 'windowTitle' in vision) {
        dto.window_title = vision.windowTitle;
    }
    if (vision && 'windowProcess' in vision) {
        dto.window_process = vision.windowProcess;
    }
    if (vision && 'debugSave' in vision) {
        dto.debug_save = vision.debugSave;
    }
    if (vision && 'debugPath' in vision) {
        dto.debug_path = vision.debugPath;
    }

    if (vision && 'visionModules' in vision && vision.visionModules) {
        dto.vision_modules = Object.keys(vision.visionModules).reduce((acc: Record<string, any>, providerName: string) => {
            acc[providerName] = deepCamelToSnake(vision.visionModules![providerName]);
            return acc;
        }, {});
    }

    return dto as ProjectConfigDto['vision'];
}
