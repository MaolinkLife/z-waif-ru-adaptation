import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormBuilder, FormControl, FormGroup } from '@angular/forms';
import { BehaviorSubject, Subject } from 'rxjs';
import { finalize, take, takeUntil } from 'rxjs/operators';
import { ConfigService } from '../../../../../core/services/config.service';
import { ResourcesService } from '../../../../../core/services/resources.service';
import { ModalService } from '../../../../../shared/components/modal/modal.service';
import { MonitorSelectionModalComponent } from '../../monitor-selection-modal/monitor-selection-modal.component';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

type ProviderFieldType = 'text' | 'number' | 'boolean';

interface ProviderFieldMeta {
    key: string;
    label: string;
    type: ProviderFieldType;
}

@Component({
    selector: 'app-vision-settings',
    templateUrl: './vision-settings.component.html',
    styleUrls: ['./vision-settings.component.less']
})
export class VisionSettingsComponent implements OnInit, OnDestroy {
    visionForm: FormGroup;
    originalConfig: any = {};

    visionProviders: { value: string; label: string }[] = [];
    isLoading$ = new BehaviorSubject<boolean>(true);

    private providerFieldMeta: Record<string, ProviderFieldMeta[]> = {};
    private providerFieldTypes: Record<string, Record<string, ProviderFieldType>> = {};
    private pendingChanges: any = {};
    private destroy$ = new Subject<void>();
    private isInitializing = true;

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
        this.localizationService.init();
        this.setupListeners();
        this.loadConfig();
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }

    private createForm(): FormGroup {
        return this.fb.group({
            enabled: [false],
            activeProvider: [''],
            monitorIndex: [0],
            fps: [5],
            bufferSec: [4],
            downscaleWidth: [1280],
            yoloEnabled: [false],
            ocrLang: ['rus+eng'],
            ocrMinConf: [70],
            ocrMaxLines: [5],
            region: [null],
            captureMode: ['monitor'],
            windowTitle: [''],
            windowProcess: [''],
            debugSave: [true],
            debugPath: ['./temp/vision'],
            visionModules: this.fb.group({})
        });
    }

    private setupListeners(): void {
        this.visionForm.valueChanges
            .pipe(takeUntil(this.destroy$))
            .subscribe(() => {
                if (this.isInitializing) {
                    return;
                }
                this.pendingChanges = this.calculateChanges();
            });

        this.visionForm.get('activeProvider')?.valueChanges
            .pipe(takeUntil(this.destroy$))
            .subscribe((providerName: string) => {
                if (!providerName) {
                    return;
                }
                this.ensureProviderGroup(providerName);
            });
    }

    private loadConfig(): void {
        this.isLoading$.next(true);
        this.configService.getConfig$()
            .pipe(
                take(1),
                takeUntil(this.destroy$),
                finalize(() => this.isLoading$.next(false))
            )
            .subscribe({
                next: (config) => {
                    const vision = config?.vision;
                    this.isInitializing = true;
                    this.resetProviderControls();

                    if (vision) {
                        this.populateProviders(vision.visionModules || {});

                        const activeProvider = vision.activeProvider || this.visionProviders[0]?.value || '';

                        this.visionForm.patchValue({
                            enabled: vision.enabled ?? false,
                            activeProvider,
                            monitorIndex: vision.monitorIndex ?? 0,
                            fps: vision.fps ?? 5,
                            bufferSec: vision.bufferSec ?? 4,
                            downscaleWidth: vision.downscaleWidth ?? 1280,
                            yoloEnabled: vision.yoloEnabled ?? false,
                            ocrLang: vision.ocrLang ?? 'eng',
                            ocrMinConf: vision.ocrMinConf ?? 70,
                            ocrMaxLines: vision.ocrMaxLines ?? 5,
                            region: vision.region ?? null,
                            captureMode: vision.captureMode ?? 'monitor',
                            windowTitle: vision.windowTitle ?? '',
                            windowProcess: vision.windowProcess ?? '',
                            debugSave: vision.debugSave ?? true,
                            debugPath: vision.debugPath ?? './temp/vision',
                        }, { emitEvent: false });

                        this.ensureProviderGroup(activeProvider);
                    } else {
                        this.populateProviders({});
                    }

                    this.originalConfig = this.buildVisionConfigFromForm();
                    this.pendingChanges = {};
                    this.visionForm.markAsPristine();
                    this.isInitializing = false;
                },
                error: (error) => {
                    console.error('Failed to load vision config', error);
                    this.notificationService.open({
                        title: 'Error',
                        type: 'error',
                        message: 'Failed to load vision configuration',
                        autoClose: true,
                    });
                    this.isInitializing = false;
                }
            });
    }

    openMonitorSelection(): void {
        this.resourcesService.getMonitorScreens$()
            .pipe(take(1), takeUntil(this.destroy$))
            .subscribe(response => {
            if (response && response.monitors) {
                const modalRef = this.modalService.open(MonitorSelectionModalComponent, {
                    data: {
                        monitors: response.monitors,
                        selectedMonitor: this.visionForm.get('monitorIndex')?.value,
                        onSelect: (result: any) => {
                            if (result && result.selectedMonitor !== undefined) {
                                const value = Number(result.selectedMonitor);
                                if (!Number.isNaN(value)) {
                                    this.visionForm.get('monitorIndex')?.setValue(value);
                                }
                            }
                        }
                    }
                });

                modalRef.afterClosed$.pipe(take(1)).subscribe((response) => {
                    const selectedMonitor = response?.selectedMonitor;
                    if (selectedMonitor !== undefined) {
                        const value = Number(selectedMonitor);
                        if (!Number.isNaN(value)) {
                            this.visionForm.get('monitorIndex')?.setValue(value);
                        }
                    }
                });
            }
        });
    }

    saveChanges(): void {
        const changes = this.pendingChanges;
        if (!changes || Object.keys(changes).length === 0) {
            return;
        }

        const payload = JSON.parse(JSON.stringify(changes));
        this.configService.updateConfig$({ vision: payload })
            .pipe(take(1), takeUntil(this.destroy$))
            .subscribe({
                next: () => {
                    this.notificationService.open({
                        message: 'Vision settings updated',
                        title: 'Success',
                        type: 'success',
                        autoClose: true
                    });
                    this.isInitializing = true;
                    this.originalConfig = this.buildVisionConfigFromForm();
                    this.pendingChanges = {};
                    this.visionForm.markAsPristine();
                    this.isInitializing = false;
                },
                error: (error) => {
                    console.error('Error updating vision settings:', error);
                    this.notificationService.open({
                        message: 'Failed to update vision settings',
                        title: 'Error',
                        type: 'error',
                        autoClose: false
                    });
                }
            });
    }

    hasChanges(): boolean {
        return !!this.pendingChanges && Object.keys(this.pendingChanges).length > 0;
    }

    get activeProvider(): string {
        return this.visionForm.get('activeProvider')?.value;
    }

    get currentProviderGroup(): FormGroup | null {
        const provider = this.activeProvider;
        if (!provider) {
            return null;
        }
        return (this.visionForm.get('visionModules') as FormGroup)?.get(provider) as FormGroup;
    }

    getProviderFields(providerName: string): ProviderFieldMeta[] {
        return this.providerFieldMeta[providerName] ?? [];
    }

    getProviderLabel(providerName: string): string {
        return this.visionProviders.find(provider => provider.value === providerName)?.label || this.formatLabel(providerName);
    }

    private resetProviderControls(): void {
        this.providerFieldMeta = {};
        this.providerFieldTypes = {};
        this.visionProviders = [];
        this.visionForm.setControl('visionModules', this.fb.group({}));
    }

    private populateProviders(modules: Record<string, any>): void {
        const providers = Object.keys(modules);
        const modulesGroup = this.fb.group({});

        providers.forEach((providerName) => {
            const providerConfig = modules[providerName] || {};
            modulesGroup.addControl(providerName, this.createProviderGroup(providerName, providerConfig));
        });

        this.visionForm.setControl('visionModules', modulesGroup);
        this.visionProviders = providers.map(providerName => ({
            value: providerName,
            label: this.formatLabel(providerName)
        }));
    }

    private ensureProviderGroup(providerName: string): void {
        const modulesGroup = this.visionForm.get('visionModules') as FormGroup;
        if (!modulesGroup) {
            return;
        }

        if (!modulesGroup.get(providerName)) {
            modulesGroup.addControl(providerName, this.createProviderGroup(providerName, {}));
        }
    }

    private createProviderGroup(providerName: string, providerConfig: Record<string, any>): FormGroup {
        const group = this.fb.group({});
        Object.keys(providerConfig || {}).forEach((fieldName) => {
            group.addControl(fieldName, new FormControl(providerConfig[fieldName]));
        });

        this.setProviderMetadata(providerName, providerConfig || {});

        return group;
    }

    private setProviderMetadata(providerName: string, providerConfig: Record<string, any>): void {
        const meta: ProviderFieldMeta[] = [];
        const typeMap: Record<string, ProviderFieldType> = {};

        Object.keys(providerConfig || {}).forEach((fieldName) => {
            const value = providerConfig[fieldName];
            const type = this.detectFieldType(value);
            const fieldMeta: ProviderFieldMeta = {
                key: fieldName,
                label: this.formatLabel(fieldName),
                type
            };

            meta.push(fieldMeta);
            typeMap[fieldName] = type;
        });

        this.providerFieldMeta[providerName] = meta;
        this.providerFieldTypes[providerName] = typeMap;
    }

    private detectFieldType(value: any): ProviderFieldType {
        if (typeof value === 'boolean') {
            return 'boolean';
        }
        if (typeof value === 'number') {
            return 'number';
        }
        return 'text';
    }

    private formatLabel(fieldName: string): string {
        return fieldName
            .replace(/_/g, ' ')
            .replace(/([A-Z])/g, ' $1')
            .replace(/\s+/g, ' ')
            .trim()
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    private buildVisionConfigFromForm(): any {
        const raw = this.visionForm.getRawValue();
        const modulesGroup = raw.visionModules || {};
        const modules: Record<string, any> = {};

        Object.keys(modulesGroup).forEach((providerName) => {
            const providerValues = modulesGroup[providerName] || {};
            modules[providerName] = Object.keys(providerValues).reduce((acc: Record<string, any>, fieldName: string) => {
                let value = providerValues[fieldName];

                const fieldType = this.providerFieldTypes[providerName]?.[fieldName];
                if (fieldType === 'number' && value !== null && value !== '') {
                    value = Number(value);
                }

                acc[fieldName] = value;
                return acc;
            }, {});
        });

        return {
            enabled: raw.enabled,
            activeProvider: raw.activeProvider,
            monitorIndex: raw.monitorIndex,
            fps: raw.fps,
            bufferSec: raw.bufferSec,
            downscaleWidth: raw.downscaleWidth,
            yoloEnabled: raw.yoloEnabled,
            ocrLang: raw.ocrLang,
            ocrMinConf: raw.ocrMinConf,
            ocrMaxLines: raw.ocrMaxLines,
            region: raw.region,
            captureMode: raw.captureMode,
            windowTitle: raw.windowTitle,
            windowProcess: raw.windowProcess,
            debugSave: raw.debugSave,
            debugPath: raw.debugPath,
            visionModules: modules,
        };
    }

    private calculateChanges(): any {
        const current = this.buildVisionConfigFromForm();
        const diff = this.deepDiff(this.originalConfig || {}, current);
        return diff && typeof diff === 'object' ? diff : {};
    }

    private deepDiff(original: any, current: any): any {
        if (Array.isArray(current)) {
            if (!Array.isArray(original) || JSON.stringify(current) !== JSON.stringify(original)) {
                return current;
            }
            return undefined;
        }

        if (this.isPlainObject(current)) {
            const diff: Record<string, any> = {};

            Object.keys(current).forEach((key) => {
                const result = this.deepDiff(original ? original[key] : undefined, current[key]);
                if (this.hasValue(result)) {
                    diff[key] = result;
                }
            });

            return Object.keys(diff).length > 0 ? diff : undefined;
        }

        if (!this.isEqual(current, original)) {
            return current;
        }

        return undefined;
    }

    private hasValue(value: any): boolean {
        if (value === undefined) {
            return false;
        }

        if (Array.isArray(value)) {
            return value.length > 0;
        }

        if (this.isPlainObject(value)) {
            return Object.keys(value).length > 0;
        }

        return true;
    }

    private isPlainObject(value: any): value is Record<string, any> {
        return value !== null && typeof value === 'object' && !Array.isArray(value);
    }

    private isEqual(a: any, b: any): boolean {
        if (a === b) {
            return true;
        }
        return typeof a === 'number' && typeof b === 'number' && Number.isNaN(a) && Number.isNaN(b);
    }
}
