import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { ResourcesService } from '../../../../../core/services/resources.service';
import { ModalService } from '../../../../../shared/components/modal/modal.service';
import { MonitorSelectionModalComponent } from '../../monitor-selection-modal/monitor-selection-modal.component';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

@Component({
    selector: 'app-vision-settings',
    templateUrl: './vision-settings.component.html',
    styleUrls: ['./vision-settings.component.less']
})
export class VisionSettingsComponent implements OnInit {
    visionForm: FormGroup;
    originalConfig: any = {};

    // Доступные провайдеры
    visionProviders = [
        { value: 'apple_vision', label: 'Apple Vision' },
        { value: 'llava', label: 'LLaVA' },
        // Можно добавить другие: openai_vision, etc.
    ];

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private resourcesService: ResourcesService,
        private modalService: ModalService,
        private notificationService: NotificationService,
        private localizationService: LocalizationService,
    ) {
        this.visionForm = this.createForm();
    }

    ngOnInit(): void {
        this.loadConfig();
        this.localizationService.init();
    }

    private createForm(): FormGroup {
        return this.fb.group({
            enabled: [false],
            active_provider: ['apple_vision'],
            monitorIndex: [0],
            fps: [5],
            bufferSec: [4],
            downscaleWidth: [1280],
            yoloEnabled: [false],
            ocrLang: ['rus+eng'],
            ocrMinConf: [70],
            ocrMaxLines: [5],
            region: [null],
            capture_mode: ['monitor'], // 'monitor', 'window', 'region'
            window_title: [''],
            window_process: [''],
            debug_save: [true],
            debug_path: ['./temp/vision'],
            // visionModules: this.fb.group({ ... }) — если хочешь вложенные настройки
        });
    }

    private loadConfig(): void {
        this.configService.getConfig$().subscribe(config => {
            if (config && config.vision) {
                this.originalConfig = { ...config.vision };

                // Маппим поля из конфига в форму
                const formValue: any = {
                    enabled: config.vision.enabled,
                    active_provider: config.vision.activeProvider || 'apple_vision',
                    monitorIndex: config.vision.monitorIndex,
                    fps: config.vision.fps,
                    bufferSec: config.vision.bufferSec,
                    downscaleWidth: config.vision.downscaleWidth,
                    yoloEnabled: config.vision.yoloEnabled,
                    ocrLang: config.vision.ocrLang,
                    ocrMinConf: config.vision.ocrMinConf,
                    ocrMaxLines: config.vision.ocrMaxLines,
                    region: config.vision.region,
                    capture_mode: config.vision.captureMode || 'monitor',
                    window_title: config.vision.windowTitle,
                    window_process: config.vision.windowProcess,
                    debug_save: config.vision.debugSave,
                    debug_path: config.vision.debugPath,
                };

                this.visionForm.patchValue(formValue);
            } else {
                this.originalConfig = { ...this.visionForm.value };
            }
        });
    }

    openMonitorSelection(): void {
        this.resourcesService.getMonitorScreens$().subscribe(response => {
            if (response && response.monitors) {
                const modalRef = this.modalService.open(MonitorSelectionModalComponent, {
                    data: {
                        monitors: response.monitors,
                        selectedMonitor: this.visionForm.get('monitorIndex')?.value,
                        onSelect: (result: any) => {
                            if (result && result.selectedMonitor !== undefined) {
                                console.log('Monitor selected in modal:', result.selectedMonitor);
                                this.visionForm.get('monitorIndex')?.setValue(result.selectedMonitor);
                            }
                        }
                    }
                });

                modalRef.afterClosed$.subscribe((response) => {
                    const selectedMonitor = response?.selectedMonitor;
                    if (selectedMonitor !== undefined) {
                        console.log('Monitor selected on modal close:', selectedMonitor);
                        this.visionForm.get('monitorIndex')?.setValue(selectedMonitor);
                    }
                });
            }
        });
    }

    saveChanges(): void {
        const changes = this.getChanges();
        if (Object.keys(changes).length > 0) {
            // Маппим обратно в camelCase
            const visionModel: any = {};

            // Общие поля
            if (changes.hasOwnProperty('enabled')) visionModel.enabled = changes.enabled;
            if (changes.hasOwnProperty('active_provider')) visionModel.active_provider = changes.active_provider;
            if (changes.hasOwnProperty('monitorIndex')) visionModel.monitor_index = changes.monitorIndex;
            if (changes.hasOwnProperty('fps')) visionModel.fps = changes.fps;
            if (changes.hasOwnProperty('bufferSec')) visionModel.buffer_sec = changes.bufferSec;
            if (changes.hasOwnProperty('downscaleWidth')) visionModel.downscale_width = changes.downscaleWidth;
            if (changes.hasOwnProperty('yoloEnabled')) visionModel.yolo_enabled = changes.yoloEnabled;
            if (changes.hasOwnProperty('ocrLang')) visionModel.ocr_lang = changes.ocrLang;
            if (changes.hasOwnProperty('ocrMinConf')) visionModel.ocr_min_conf = changes.ocrMinConf;
            if (changes.hasOwnProperty('ocrMaxLines')) visionModel.ocr_max_lines = changes.ocrMaxLines;
            if (changes.hasOwnProperty('region')) visionModel.region = changes.region;
            if (changes.hasOwnProperty('capture_mode')) visionModel.capture_mode = changes.capture_mode;
            if (changes.hasOwnProperty('window_title')) visionModel.window_title = changes.window_title;
            if (changes.hasOwnProperty('window_process')) visionModel.window_process = changes.window_process;
            if (changes.hasOwnProperty('debug_save')) visionModel.debug_save = changes.debug_save;
            if (changes.hasOwnProperty('debug_path')) visionModel.debug_path = changes.debug_path;

            const updateData = { vision: visionModel };
            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    console.log('Vision settings updated:', response);
                    this.notificationService.open({
                        message: JSON.stringify(response),
                        title: 'Vision settings updated',
                        type: 'success',
                        autoClose: true
                    });
                    this.originalConfig = { ...this.visionForm.value };
                },
                error: (error) => {
                    this.notificationService.open({
                        message: JSON.stringify(error),
                        title: 'Error updating vision settings',
                        type: 'error',
                        autoClose: false
                    });
                    console.error('Error updating vision settings:', error);
                }
            });
        }
    }

    private getChanges(): any {
        const current = this.visionForm.value;
        const changes: any = {};

        Object.keys(current).forEach(key => {
            const originalValue = this.originalConfig ? this.originalConfig[key] : undefined;
            if (JSON.stringify(current[key]) !== JSON.stringify(originalValue)) {
                changes[key] = current[key];
            }
        });

        return changes;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }
}
