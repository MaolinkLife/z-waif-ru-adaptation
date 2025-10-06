import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { ApiService } from '../../../../../core/services/api.service';
import { GenerationPreset } from '../../../../../core/models/generation-preset.model';
import { combineLatest, BehaviorSubject, Subject } from 'rxjs';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';
import { tap, finalize, takeUntil, distinctUntilChanged } from 'rxjs/operators';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';

@Component({
    selector: 'app-generation-settings',
    templateUrl: './generation-settings.component.html',
    styleUrls: ['./generation-settings.component.less']
})
export class GenerationSettingsComponent implements OnInit, OnDestroy {
    @ViewChild('tokenSlider') tokenSliderRef!: ElementRef<HTMLInputElement>;
    @ViewChild('tokenInput') tokenInputRef!: ElementRef<HTMLInputElement>;

    generationForm: FormGroup;
    generationSettingsForm: FormGroup;
    originalConfig: any;
    presets: GenerationPreset[] = [];
    selectedPresetName: string = 'default';
    availableModels: string[] = [];
    dropdownOpen: boolean = false;
    selectedModel = '';
    isLoading$ = new BehaviorSubject<boolean>(true);
    providerKeys: string[] = [];
    apiTypeOptions: string[] = [];
    private ollamaModels: string[] = [];
    private destroy$ = new Subject<void>();

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private apiService: ApiService,
        private localizationService: LocalizationService,
        private notificationService: NotificationService,
    ) {
        this.generationForm = this.createMainForm();
        this.generationSettingsForm = this.createGenerationSettingsForm();
    }

    ngOnInit(): void {
        this.setupActiveProviderListener();
        this.loadConfigAndPresets();
        this.setupTokenLimitSync();
        this.localizationService.init();
    }

    private createMainForm(): FormGroup {
        return this.fb.group({
            apiType: ['Ollama'],
            activeProvider: ['ollama'],
            fallbackOrder: [''],
            visualModel: ['apple/FastVLM-1.5B'],
            tokenLimit: [2048],
            messagePairLimit: [10],
            streaming: [true],
            providers: this.fb.group({})
        });
    }

    private createGenerationSettingsForm(): FormGroup {
        return this.fb.group({
            name: [''],
            description: [''],
            temperature: [1.2],
            topP: [0.9],
            topK: [70],
            minP: [0.05],
            repeatPenalty: [1.2],
            numPredict: [2048],
            stop: [[]]
        });
    }

    private loadConfigAndPresets(): void {
        combineLatest([
            this.configService.getConfig$(),
            this.configService.getGenerationPresets$(),
            this.apiService.getOllamaModels$()
        ]).pipe(
            tap(() => this.isLoading$.next(true)),
            finalize(() => this.isLoading$.next(false))
        ).pipe(takeUntil(this.destroy$)).subscribe(([config, presets, models]) => {
            // Load config
            if (config) {
                this.originalConfig = JSON.parse(JSON.stringify(config));

                this.initializeProviders(config.api?.providers || {});

                this.generationForm.patchValue({
                    apiType: config.api.type,
                    activeProvider: config.api.activeProvider,
                    fallbackOrder: this.stringifyFallbackOrder(
                        config.api.fallbackOrder || []
                    ),
                    visualModel: config.api.visualModel,
                    tokenLimit: config.api.tokenLimit,
                    messagePairLimit: config.api.messagePairLimit,
                    streaming: config.api.streaming,
                }, { emitEvent: false });

                this.apiTypeOptions = Array.from(
                    new Set([
                        ...(this.apiTypeOptions || []),
                        config.api.type,
                        ...this.providerKeys.map(key => this.capitalize(key)),
                    ].filter(Boolean))
                );

                this.generationSettingsForm.patchValue(config.generateSettings);

                const activeProvider = config.api.activeProvider;
                this.selectedModel = this.getProviderModel(activeProvider);
                this.updateAvailableModels(activeProvider);
            }

            // Load presets
            this.presets = presets;
            const activePreset = presets.find(p => p.name === this.selectedPresetName) || presets[0];
            if (activePreset) {
                this.generationSettingsForm.patchValue(activePreset);
                this.selectedPresetName = activePreset.name;
            }

            // Load models
            this.ollamaModels = models;
            const activeProvider = this.generationForm.get('activeProvider')?.value;
            this.updateAvailableModels(activeProvider);
        });
    }

    private initializeProviders(providers: Record<string, any>): void {
        const providersGroup = this.generationForm.get('providers') as FormGroup;
        if (!providersGroup) {
            return;
        }

        // Очистим предыдущие контролы
        Object.keys(providersGroup.controls).forEach(key => {
            providersGroup.removeControl(key);
        });

        this.providerKeys = Object.keys(providers || {});
        this.apiTypeOptions = Array.from(
            new Set(
                [this.generationForm.get('apiType')?.value, ...this.providerKeys.map(key => this.capitalize(key))]
                    .filter(Boolean)
            )
        );

        this.providerKeys.forEach(key => {
            providersGroup.addControl(key, this.buildProviderGroup(providers[key] || {}));
        });
    }

    private buildProviderGroup(config: Record<string, any>): FormGroup {
        const controls: Record<string, any> = {};
        Object.keys(config || {}).forEach(field => {
            controls[field] = [config[field]];
        });
        return this.fb.group(controls);
    }

    private setupActiveProviderListener(): void {
        this.generationForm.get('activeProvider')?.valueChanges
            .pipe(takeUntil(this.destroy$), distinctUntilChanged())
            .subscribe(provider => {
                this.handleActiveProviderChange(provider);
            });
    }

    private handleActiveProviderChange(provider: string): void {
        this.selectedModel = this.getProviderModel(provider);
        this.updateAvailableModels(provider);
        this.dropdownOpen = false;
    }

    private updateAvailableModels(provider: string): void {
        if (provider === 'ollama') {
            this.availableModels = this.ollamaModels;
        } else {
            this.availableModels = [];
        }
    }

    private getProviderModel(provider: string): string {
        const providerGroup = this.getProviderForm(provider);
        return (providerGroup?.get('model')?.value as string) || '';
    }

    private getProviderForm(provider: string): FormGroup | null {
        const providersGroup = this.generationForm.get('providers') as FormGroup;
        if (!providersGroup || !provider) {
            return null;
        }
        return providersGroup.get(provider) as FormGroup;
    }

    private setupTokenLimitSync(): void {
        const tokenLimitControl = this.generationForm.get('tokenLimit');

        tokenLimitControl?.valueChanges.subscribe(value => {
            if (!value) return;

            if (this.tokenSliderRef?.nativeElement) {
                this.tokenSliderRef.nativeElement.value = value.toString();
            }

            if (this.tokenInputRef?.nativeElement) {
                this.tokenInputRef.nativeElement.value = value.toString();
            }
        });
    }

    toggleDropdown() {
        if (this.generationForm.get('activeProvider')?.value !== 'ollama') {
            return;
        }
        if (!this.availableModels || this.availableModels.length === 0) {
            return;
        }
        this.dropdownOpen = !this.dropdownOpen;
    }

    selectModel(model: string) {
        this.selectedModel = model;
        this.dropdownOpen = false;
        const activeProvider = this.generationForm.get('activeProvider')?.value;
        const providerForm = this.getProviderForm(activeProvider);
        providerForm?.get('model')?.setValue(model);
    }

    applyPreset(presetName: string) {
        const preset = this.presets.find(p => p.name === presetName);
        if (preset) {
            this.generationSettingsForm.patchValue(preset);
            this.selectedPresetName = presetName;
        }
    }

    saveOrUpdatePreset() {
        const current = this.generationSettingsForm.value;
        this.configService.saveGenerationPreset$(current).subscribe();
    }

    saveChanges(): void {
        if (!this.originalConfig) {
            return;
        }
        const updateData: any = {};
        const currentApi = this.buildCurrentApiConfig();
        const currentGenerateSettings = this.generationSettingsForm.value;

        if (!this.deepEqual(currentApi, this.originalConfig?.api)) {
            updateData.api = currentApi;
        }

        if (!this.deepEqual(currentGenerateSettings, this.originalConfig?.generateSettings)) {
            updateData.generateSettings = currentGenerateSettings;
        }

        if (Object.keys(updateData).length > 0) {
            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    this.notificationService.open({
                        title: 'Generation settings updated',
                        type: 'success',
                        autoClose: false
                    });
                    console.log('Generation settings updated:', response);
                    this.originalConfig = JSON.parse(JSON.stringify({
                        api: currentApi,
                        generateSettings: currentGenerateSettings,
                    }));
                },
                error: (error) => {
                    this.notificationService.open({
                        title: 'Error updating generation settings',
                        type: 'error',
                        autoClose: false,
                        
                    });
                    console.error('Error updating generation settings:', error);
                }
            });
        }
    }

    onPresetChange(event: Event): void {
        const target = event.target as HTMLSelectElement;
        this.applyPreset(target.value);
    }
    hasChanges(): boolean {
        if (!this.originalConfig) {
            return false;
        }
        const currentApi = this.buildCurrentApiConfig();
        const currentGenerateSettings = this.generationSettingsForm.value;
        return (
            !this.deepEqual(currentApi, this.originalConfig?.api) ||
            !this.deepEqual(currentGenerateSettings, this.originalConfig?.generateSettings)
        );
    }

    private buildCurrentApiConfig(): any {
        const values = this.generationForm.value;
        const providersGroup = this.generationForm.get('providers') as FormGroup;
        const providerValues: Record<string, any> = {};

        Object.keys(providersGroup?.controls || {}).forEach(key => {
            providerValues[key] = providersGroup.get(key)?.value;
        });

        const activeProvider = values.activeProvider;
        const fallbackOrder = this.parseFallbackOrder(values.fallbackOrder);
        const activeModel = providerValues?.[activeProvider]?.model || '';

        return {
            type: values.apiType,
            streaming: values.streaming,
            visualModel: values.visualModel,
            tokenLimit: values.tokenLimit,
            messagePairLimit: values.messagePairLimit,
            activeProvider,
            fallbackOrder,
            providers: providerValues,
            model: activeModel,
        };
    }

    private parseFallbackOrder(value: string): string[] {
        if (!value) {
            return [];
        }
        return value
            .split(',')
            .map(item => item.trim())
            .filter(Boolean);
    }

    private stringifyFallbackOrder(order: string[]): string {
        return (order || []).join(', ');
    }

    private deepEqual(a: any, b: any): boolean {
        return JSON.stringify(a) === JSON.stringify(b);
    }

    get currentProviderForm(): FormGroup | null {
        const activeProvider = this.generationForm.get('activeProvider')?.value;
        return this.getProviderForm(activeProvider);
    }

    get currentProviderFields(): Array<{ key: string; type: 'text' | 'number' | 'checkbox' }> {
        const group = this.currentProviderForm;
        if (!group) {
            return [];
        }
        return Object.keys(group.controls).map(field => {
            const value = group.get(field)?.value;
            let type: 'text' | 'number' | 'checkbox' = 'text';
            if (typeof value === 'number') {
                type = 'number';
            } else if (typeof value === 'boolean') {
                type = 'checkbox';
            }
            return { key: field, type };
        });
    }

    formatFieldLabel(field: string): string {
        return field
            .replace(/_/g, ' ')
            .replace(/\b\w/g, letter => letter.toUpperCase());
    }

    private capitalize(value: string): string {
        if (!value) {
            return value;
        }
        return value.charAt(0).toUpperCase() + value.slice(1);
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }
}
