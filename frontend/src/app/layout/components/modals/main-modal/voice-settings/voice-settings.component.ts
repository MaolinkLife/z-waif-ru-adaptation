import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { ResourcesService } from '../../../../../core/services/resources.service';
import { BehaviorSubject, Observable, forkJoin, of } from 'rxjs';
import { map, finalize, startWith, take } from 'rxjs/operators';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

interface AudioDevice {
    id: number;
    name: string;
}

interface AudioDevicesData {
    audioOutputs: AudioDevice[];
    windowsOutputs: AudioDevice[];
}

interface TTSProviderStatus {
    available: boolean;
    disabled: boolean;
    cooldown: number;
    lastFailureAt?: number | null;
    lastError?: string | null;
}

interface VoiceModuleOption {
    value: string;
    label: string;
    available: boolean;
    disabled: boolean;
    tooltip?: string;
}

@Component({
    selector: 'app-voice-settings',
    templateUrl: './voice-settings.component.html',
    styleUrls: ['./voice-settings.component.less']
})
export class VoiceSettingsComponent implements OnInit {
    voiceForm: FormGroup;
    originalConfig: any = {};

    devices$: Observable<AudioDevicesData> = new Observable<AudioDevicesData>();
    devicesRefreshing = false;


    isLoading$ = new BehaviorSubject<boolean>(true);

    edgeVoices: { name: string; language: string; gender: string; styles: string[] }[] = [];

    private readonly baseVoiceModules: VoiceModuleOption[] = [
        { value: 'elevenlabs', label: 'ElevenLabs', available: true, disabled: false },
        { value: 'edge', label: 'Edge TTS', available: true, disabled: false },
        { value: 'gtts', label: 'gTTS (Google)', available: true, disabled: false },
        { value: 'offline', label: 'Offline (pyttsx3)', available: true, disabled: false },
    ];

    voiceModules: VoiceModuleOption[] = this.baseVoiceModules.map((module) => ({ ...module }));
    providerStatuses: Record<string, TTSProviderStatus> = {};

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private resourcesService: ResourcesService,
        private notificationService: NotificationService,
        private localizationService: LocalizationService,
    ) {
        this.voiceForm = this.createForm();
    }

    ngOnInit(): void {
        this.loadAllData();
        this.localizationService.init();
    }

    loadAllData(): void {
        this.isLoading$.next(true);
        const config$ = this.configService.getConfig$().pipe(take(1));
        const devices$ = this.resourcesService.getAudioDevices$().pipe(take(1));
        const voices$ = this.resourcesService.getEdgeVoices$().pipe(take(1));
        const providers$ = this.resourcesService.getVoiceProviders$().pipe(take(1));

        forkJoin({
            config: config$,
            devices: devices$,
            voices: voices$,
            providers: providers$,
        })
            .pipe(
                finalize(() => {
                    this.isLoading$.next(false);
                })
            )
            .subscribe({
                next: ({ config, devices, voices, providers }) => {
                    try {
                        console.log({ config });
                        this.loadConfig(config);
                        this.applyProviderStatuses(providers);
                        this.loadDevices(devices);
                        this.loadEdgeVoices(voices);
                    } catch (error) {
                        console.error('Error processing voice settings payload:', error);
                        this.isLoading$.next(false);
                    }
                },
                error: (error) => {
                    console.error('Error loading data:', error);
                    this.isLoading$.next(false);
                }
            });
    }

    loadConfig(config: any): void {
        if (config && config.voice) {
            this.originalConfig = { ...config.voice };
            const formValue: any = {
                enabled: config.voice.enabled !== undefined ? config.voice.enabled : false,
                activeModule: config.voice.activeModule || 'elevenlabs',
                streamingTts: config.voice.streamingTts !== undefined ? config.voice.streamingTts : false,
                enableFallback: config.voice.enableFallback !== undefined ? config.voice.enableFallback : true,
                useWindowsOutput: config.voice.useWindowsOutput !== undefined ? config.voice.useWindowsOutput : true,
                useRvc: config.voice.useRvc !== undefined ? config.voice.useRvc : true,
                outputId: config.voice.outputId !== undefined ? config.voice.outputId : 25,
                windowsOutputId: config.voice.windowsOutputId !== undefined ? config.voice.windowsOutputId : 12,
                voiceLanguage: config.voice.voiceLanguage || 'ru-RU-SvetlanaNeural',
            };

            if (config.voice.voiceModules) {
                const voiceModulesValue: any = {};

                if (config.voice.voiceModules.elevenlabs) {
                    // camelCase -> camelCase (уже смаплено)
                    voiceModulesValue.elevenlabs = {
                        apiKey: config.voice.voiceModules.elevenlabs.apiKey || '',
                        voiceId: config.voice.voiceModules.elevenlabs.voiceId || '',
                        modelId: config.voice.voiceModules.elevenlabs.modelId || '',
                        stability: config.voice.voiceModules.elevenlabs.stability || 0.5,
                        similarity: config.voice.voiceModules.elevenlabs.similarity || 0.75
                    };
                }

                if (config.voice.voiceModules.edge) {
                    // camelCase -> camelCase (уже смаплено)
                    voiceModulesValue.edge = {
                        voiceLanguage: config.voice.voiceModules.edge.voiceLanguage || ''
                    };
                } else {
                    voiceModulesValue.edge = voiceModulesValue.edge || { voiceLanguage: '' };
                }

                if (config.voice.voiceModules.gtts) {
                    voiceModulesValue.gtts = {
                        language: config.voice.voiceModules.gtts.language || 'ru',
                        tld: config.voice.voiceModules.gtts.tld || 'com',
                        slow: config.voice.voiceModules.gtts.slow ?? false,
                        fallbackVoice: config.voice.voiceModules.gtts.fallbackVoice || ''
                    };
                } else {
                    voiceModulesValue.gtts = voiceModulesValue.gtts || {
                        language: 'ru',
                        tld: 'com',
                        slow: false,
                        fallbackVoice: ''
                    };
                }

                if (config.voice.voiceModules.offline) {
                    voiceModulesValue.offline = {
                        voice: config.voice.voiceModules.offline.voice || ''
                    };
                } else {
                    voiceModulesValue.offline = voiceModulesValue.offline || {
                        voice: ''
                    };
                }

                formValue.voiceModules = voiceModulesValue;
            }

            this.voiceForm.patchValue(formValue);
            console.log('Voice config loaded:', formValue);
        }
    }

    loadDevices(devices: any): void {
        const audioOutputs: AudioDevice[] = [
            { id: 0, name: 'Default Device' }
        ];

        if (devices.all_devices && devices.all_devices.length > 0) {
            for (let i = 0; i < devices.all_devices.length; i++) {
                const device = devices.all_devices[i];
                if (device && device.length >= 2) {
                    audioOutputs.push({ id: device[0], name: device[1] });
                }
            }
        }

        const windowsOutputs: AudioDevice[] = [
            { id: 0, name: 'Default Device' }
        ];

        if (devices.get_windows_output && devices.get_windows_output.length > 0) {
            for (let i = 0; i < devices.get_windows_output.length; i++) {
                const device = devices.get_windows_output[i];
                if (device && device.length >= 2) {
                    windowsOutputs.push({ id: device[0], name: device[1] });
                }
            }
        }

        this.devices$ = of({ audioOutputs, windowsOutputs });
    }

    loadEdgeVoices(voices: any): void {
        if (voices && voices.status === 'success' && Array.isArray(voices.voices)) {
            this.edgeVoices = voices.voices;
        } else {
            console.warn('No voices received or error in response:', voices);
        }
    }

    refreshDevices(): void {
        this.devicesRefreshing = true;
        this.resourcesService.getAudioDevices$().pipe(
            finalize(() => {
                this.devicesRefreshing = false;
            })
        ).subscribe(devices => {
            this.loadDevices(devices);
        });
    }

    private createForm(): FormGroup {
        return this.fb.group({
            enabled: [false],
            activeModule: ['elevenlabs'],
            streamingTts: [false],
            enableFallback: [true],
            useWindowsOutput: [true],
            useRvc: [true],
            outputId: [25],
            windowsOutputId: [12],
            voiceLanguage: ['ru-RU-SvetlanaNeural'],
            voiceModules: this.fb.group({
                elevenlabs: this.fb.group({
                    apiKey: [''],
                    voiceId: [''],
                    modelId: [''],
                    stability: [0.5],
                    similarity: [0.75]
                }),
                edge: this.fb.group({
                    voiceLanguage: ['']
                }),
                gtts: this.fb.group({
                    language: ['ru'],
                    tld: ['com'],
                    slow: [false],
                    fallbackVoice: ['']
                }),
                offline: this.fb.group({
                    voice: ['']
                })
            })
        });
    }

    saveChanges(): void {
        const changes = this.getChanges();
        if (Object.keys(changes).length > 0) {
            const voiceModel: any = {};

            for (const key of ['enabled', 'activeModule', 'streamingTts', 'enableFallback', 'useWindowsOutput', 'useRvc', 'outputId', 'windowsOutputId', 'voiceLanguage']) {
                if (changes.hasOwnProperty(key)) {
                    voiceModel[key] = changes[key];
                }
            }

            if (this.voiceForm.get('voiceModules')) {
                voiceModel.voiceModules = this.voiceForm.get('voiceModules')?.value;
            }

            const updateData = { voice: voiceModel };
            console.log('Sending voice config update (model format):', updateData);

            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    this.notificationService.open({
                        title: 'Voice settings updated',
                        type: 'success',
                        message: JSON.stringify(response),
                        autoClose: true
                    });
                    console.log('Voice settings updated:', response);
                    this.originalConfig = { ...this.voiceForm.value };
                },
                error: (error) => {
                    this.notificationService.open({
                        title: 'Error updating voice settings',
                        type: 'error',
                        message: JSON.stringify(error),
                        autoClose: true
                    });
                    console.error('Error updating voice settings:', error);
                }
            });
        }
    }

    private getChanges(): any {
        const current = this.voiceForm.value;
        const changes: any = {};

        for (const key in current) {
            if (current.hasOwnProperty(key)) {
                const currentValue = current[key];
                const originalValue = this.originalConfig ? this.originalConfig[key] : undefined;

                let valuesDiffer = false;
                if (originalValue === undefined) {
                    valuesDiffer = currentValue !== undefined && currentValue !== null && currentValue !== '';
                } else {
                    valuesDiffer = JSON.stringify(currentValue) !== JSON.stringify(originalValue);
                }

                if (valuesDiffer) {
                    changes[key] = currentValue;
                }
            }
        }

        return changes;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }

    resetToDefaults(): void {
        this.voiceForm.reset({
            enabled: false,
            activeModule: 'elevenlabs',
            streamingTts: false,
            enableFallback: true,
            useWindowsOutput: true,
            useRvc: true,
            outputId: 25,
            windowsOutputId: 12,
            voiceLanguage: 'ru-RU-SvetlanaNeural',
        });

        this.voiceForm.get('voiceModules')?.reset({
            elevenlabs: {
                apiKey: '',
                voiceId: '',
                modelId: '',
                stability: 0.5,
                similarity: 0.75
            },
            edge: {
                voiceLanguage: ''
            },
            gtts: {
                language: 'ru',
                tld: 'com',
                slow: false,
                fallbackVoice: ''
            },
            offline: {
                voice: ''
            }
        });
    }

    getActiveModule(): string {
        return this.voiceForm.get('activeModule')?.value || 'elevenlabs';
    }

    showWindowsOutput(): boolean {
        return this.voiceForm.get('useWindowsOutput')?.value === true;
    }

    showVoiceLanguage(): boolean {
        return this.getActiveModule() === 'edge';
    }

    showGttsFields(): boolean {
        return this.getActiveModule() === 'gtts';
    }

    showElevenLabsFields(): boolean {
        return this.getActiveModule() === 'elevenlabs';
    }

    showOpenAIFields(): boolean {
        return this.getActiveModule() === 'openai';
    }

    getElevenLabsField(field: string) {
        return this.voiceForm.get(`voiceModules.elevenlabs.${field}`);
    }

    getEdgeField(field: string) {
        return this.voiceForm.get(`voiceModules.edge.${field}`);
    }

    getGttsField(field: string) {
        return this.voiceForm.get(`voiceModules.gtts.${field}`);
    }

    isModuleAvailable(value: string): boolean {
        return this.voiceModules.find((module) => module.value === value)?.available ?? false;
    }

    getModuleLabel(module: VoiceModuleOption): string {
        if (module.available) {
            return module.label;
        }
        const unavailableText = this.t('settings.voiceProviderUnavailable', 'Unavailable');
        return `${module.label} (${unavailableText})`;
    }

    getModuleTooltip(module: VoiceModuleOption): string | null {
        return module.tooltip ?? null;
    }

    private applyProviderStatuses(payload: any): void {
        const providers = (payload && payload.providers) || {};
        const statuses: Record<string, TTSProviderStatus> = {};

        Object.keys(providers).forEach((key) => {
            const item = providers[key] || {};
            statuses[key] = {
                available: !!item.available,
                disabled: !!item.disabled,
                cooldown: typeof item.cooldown === 'number' ? item.cooldown : 0,
                lastFailureAt: item.last_failure_at ?? null,
                lastError: item.last_error ?? null,
            };
        });

        this.providerStatuses = statuses;
        this.voiceModules = this.baseVoiceModules.map((module) => {
            const status = statuses[module.value];
            if (!status) {
                return { ...module };
            }

            const providerAvailable = status.available;
            const providerDisabled = status.disabled;
            const displayAvailable = providerAvailable && !providerDisabled;
            const tooltipLines: string[] = [];
            if (!status.available) {
                tooltipLines.push(this.t('settings.voiceProviderUnavailable', 'Provider unavailable'));
            }
            if (status.disabled) {
                const cooldownText = this.t(
                    'settings.voiceProviderCooldown',
                    'Provider disabled (cooldown {seconds}s)'
                );
                const formattedCooldown = cooldownText.includes('{seconds}')
                    ? cooldownText.replace('{seconds}', status.cooldown.toFixed(1))
                    : `${cooldownText} (${status.cooldown.toFixed(1)}s)`;
                tooltipLines.push(formattedCooldown);
            }
            if (status.lastError) {
                tooltipLines.push(status.lastError);
            }

            return {
                ...module,
                available: displayAvailable,
                disabled: providerDisabled,
                tooltip: tooltipLines.length > 0 ? tooltipLines.join('\n') : undefined,
            };
        });

        const active = this.getActiveModule();
        if (active && !this.isModuleAvailable(active)) {
            const fallback = this.voiceModules.find((module) => module.available);
            if (fallback) {
                this.voiceForm.patchValue({ activeModule: fallback.value }, { emitEvent: true });
            }
        }
    }

    private t(key: string, fallback: string): string {
        const value = this.localizationService.t(key);
        return value === key ? fallback : value;
    }
}
