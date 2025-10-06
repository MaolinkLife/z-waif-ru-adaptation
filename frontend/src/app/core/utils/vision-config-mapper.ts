import { ProjectConfig } from '../models/project-config.model';
import { ProjectConfigDto } from '../models/project-config.dto';

export function mapVisionDtoToModel(dtoVision: ProjectConfigDto['vision']): ProjectConfig['vision'] {
    return {
        enabled: dtoVision.enabled,
        activeProvider: dtoVision.active_provider || 'apple_vision',
        monitorIndex: dtoVision.monitor_index,
        fps: dtoVision.fps,
        bufferSec: dtoVision.buffer_sec,
        downscaleWidth: dtoVision.downscale_width,
        yoloEnabled: dtoVision.yolo_enabled,
        ocrLang: dtoVision.ocr_lang,
        ocrMinConf: dtoVision.ocr_min_conf,
        ocrMaxLines: dtoVision.ocr_max_lines,
        region: dtoVision.region,
        captureMode: dtoVision.capture_mode || 'monitor',
        windowTitle: dtoVision.window_title || '',
        windowProcess: dtoVision.window_process || '',
        debugSave: dtoVision.debug_save || true,
        debugPath: dtoVision.debug_path || './temp/vision',
        visionModules: dtoVision.vision_modules || [],
    };
}

export function mapVisionModelToDto(vision: ProjectConfig['vision']): ProjectConfigDto['vision'] {
    const dto: any = {
        enabled: vision.enabled,
        active_provider: vision.activeProvider,
        monitor_index: vision.monitorIndex,
        fps: vision.fps,
        buffer_sec: vision.bufferSec,
        downscale_width: vision.downscaleWidth,
        yolo_enabled: vision.yoloEnabled,
        ocr_lang: vision.ocrLang,
        ocr_min_conf: vision.ocrMinConf,
        ocr_max_lines: vision.ocrMaxLines,
        region: vision.region,
        capture_mode: vision.captureMode,
        window_title: vision.windowTitle,
        window_process: vision.windowProcess,
        debug_save: vision.debugSave,
        debug_path: vision.debugPath,
    };

    if (vision.visionModules) {
        dto.vision_modules = {};

        if (vision.visionModules) {
            Object.keys(vision.visionModules || {}).forEach(moduleName => {
                dto.vision_modules[moduleName] = {
                    model_id: vision.visionModules[moduleName].modelId,
                    max_tokens: vision.visionModules[moduleName].maxTokens,
                };
            });
        }
    }

    return dto;
}
