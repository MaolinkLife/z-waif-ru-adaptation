import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { ResourcesService } from '../../../../../core/services/resources.service';
import { BehaviorSubject, Observable, combineLatest, of } from 'rxjs';
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

    voiceModules = [
        { value: 'elevenlabs', label: 'ElevenLabs' },
        { value: 'edge', label: 'Edge TTS' },
        { value: 'openai', label: 'OpenAI TTS' }
    ];

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
        const config$ = this.configService.getConfig$().pipe(take(1));
        const devices$ = this.resourcesService.getAudioDevices$().pipe(take(1));
        const voices$ = this.resourcesService.getEdgeVoices$().pipe(take(1));

        combineLatest([config$, devices$, voices$]).pipe(
            finalize(() => {
                this.isLoading$.next(false);
            })
        ).subscribe({
            next: ([config, devices, voices]) => {
                console.log({
                    config
                });

                this.loadConfig(config);
                this.loadDevices(devices);
                this.loadEdgeVoices(voices);
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
}
