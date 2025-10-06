import { ChangeDetectionStrategy, Component, ElementRef, NgZone, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../core/services/config.service';
import { ProjectConfig } from '../../core/models/project-config.model';
import { ApiService } from '../../core/services/api.service';
import { GenerationPreset } from '../../core/models/generation-preset.model';
import { ResourcesService } from '../../core/services/resources.service';
import { BehaviorSubject, combineLatest } from 'rxjs';
import { map } from 'rxjs/operators';
import { LocalizationService } from '../../shared/pipes/translation/localization.service';

@Component({
    selector: 'app-settings',
    templateUrl: './settings.component.html',
    styleUrls: ['./settings.component.less'],
    // changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent implements OnInit {

    @ViewChild('tokenSlider') tokenSliderRef!: ElementRef<HTMLInputElement>;
    @ViewChild('tokenInput') tokenInputRef!: ElementRef<HTMLInputElement>;

    settingsForm: FormGroup = new FormGroup({});
    generationSettingsForm: FormGroup = new FormGroup({});;
    presets: GenerationPreset[] = [];
    selectedPresetName: string = 'default';

    originalConfig!: ProjectConfig;

    audioOutputs: { id: number; name: string }[] = [];
    windowsOutputs: { id: number; name: string }[] = [];

    languages: { code: string, label: string }[] = [
        { code: 'ru-RU', label: 'Русский' },
        { code: 'en-US', label: 'English' }
    ];

    selectedAudioOutput: { id: number; name: string } | null = null;
    selectedWindowsOutput: { id: number; name: string } | null = null;

    availableModels: string[] = [];

    // dropdownOpen$: BehaviorSubject<boolean> = new BehaviorSubject<boolean>(false);
    dropdownOpen: boolean = false;
    selectedModel = '';

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private apiService: ApiService,
        private resourcesService: ResourcesService,
        private zone: NgZone,
        private localizationService: LocalizationService
    ) {
        this.initializeFormGroups();

    }

    initializeFormGroups(): void {
        this.settingsForm = this.fb.group({
            charName: [''],
            userName: [''],
            language: [''],
            voice: this.fb.group({
                enabled: [false],
                outputId: [0],
                windowsOutputId: [0],
                language: [''],
                useRvc: [false],
                voiceLanguage: ['']
            }),
            modules: this.fb.group({
                vtube_studio: [false],
                whisper: [false],
                minecraft: [false],
                gaming: [false],
                alarm: [false],
                discord: [false],
                rag: [false],
                visual: [false]
            }),
            api: this.fb.group({
                type: [''],
                streaming: [false],
                model: [''],
                visualModel: [''],
                tokenLimit: [0],
                messagePairLimit: [0],
                activeProvider: [''],
                fallbackOrder: this.fb.control([]),
                providers: this.fb.control({})
            })
        });

        this.generationSettingsForm = this.fb.group({
            name: [''],
            description: [''],
            temperature: [1.0],
            min_p: [0.05],
            top_p: [0.9],
            top_k: [40],
            repeat_penalty: [1.1],
            num_predict: [2048],
            stop: [[]]
        });
    }

    toggleDropdown() {
        this.dropdownOpen = !this.dropdownOpen;
    }

    selectModel(model: string) {
        this.selectedModel = model;
        this.dropdownOpen = false;
        this.settingsForm.get('api.model')?.setValue(model);

        const activeProvider = this.settingsForm.get('api.activeProvider')?.value;
        const providersControl = this.settingsForm.get('api.providers');
        const providers = providersControl?.value ?? {};

        if (activeProvider && providers[activeProvider]) {
            providersControl?.setValue({
                ...providers,
                [activeProvider]: {
                    ...providers[activeProvider],
                    model,
                }
            });
        }

        this.zone.run(() => {
            this.dropdownOpen = false;
        });
    }

    ngOnInit(): void {
        this.localizationService.init();
        this.initLanguageChangeListener();

        combineLatest([
            this.configService.getConfig$(),
            this.configService.getGenerationPresets$(),
            this.apiService.getOllamaModels$(),
        ]).pipe(
            map(([config, presets, models]: [ProjectConfig | null, GenerationPreset[], string[]]) => {
                if (config) {
                    this.originalConfig = JSON.parse(JSON.stringify(config)); // глубокая копия
                    this.settingsForm.patchValue(config);
                }

                console.log({
                    config
                });


                // Получение всех пресетов
                this.presets = presets;
                const active = presets.find(p => p.name === this.selectedPresetName) || presets[0];
                if (active) {
                    this.generationSettingsForm.patchValue(active);
                    this.selectedPresetName = active.name;
                }

                this.availableModels = models;
            })).subscribe();


        const tokenLimitControl = this.settingsForm.get('api.tokenLimit');

        // Обновляем range, если изменилось число
        tokenLimitControl?.valueChanges.subscribe(value => {
            if (!value) {
                return;
            }

            if (
                this.tokenSliderRef &&
                this.tokenSliderRef.nativeElement &&
                this.tokenSliderRef.nativeElement.value !== value.toString()
            ) {
                this.tokenSliderRef.nativeElement.value = value.toString();
            }

            if (
                this.tokenInputRef &&
                this.tokenInputRef.nativeElement &&
                this.tokenInputRef.nativeElement.value !== value.toString()
            ) {
                this.tokenInputRef.nativeElement.value = value.toString();
            }
        });


        this.getAudioDevices();
    }



    initLanguageChangeListener() {
        const control = this.settingsForm.get('language');
        if (control) {
            control.valueChanges.subscribe(lang => {
                if (lang) {
                    localStorage.setItem('language', lang);
                    this.localizationService.setLanguage(lang);
                }
            });
        }
    }

    getAudioDevices(): void {
        this.resourcesService.getAudioDevices$().subscribe(r => {
            this.audioOutputs = (r.all_devices || []).map(
                ([id, name]: [number, string]) => ({ id, name })
            );
            this.windowsOutputs = (r.get_windows_output || []).map(
                ([id, name]: [number, string]) => ({ id, name })
            );

            const voiceForm = this.settingsForm.get('voice')?.value;
            this.selectedAudioOutput = this.audioOutputs.find(d => d.id === voiceForm?.outputId) || null;
            this.selectedWindowsOutput = this.windowsOutputs.find(d => d.id === voiceForm?.windowsOutputId) || null;
        });
    }

    getModifiedConfig(): any {
        const current = this.settingsForm.value;

        const getDiff = (orig: any, curr: any): any => {
            let result: any = {};
            for (const key in curr) {
                if (typeof curr[key] === 'object' && curr[key] !== null && !Array.isArray(curr[key])) {
                    const nested = getDiff(orig[key] || {}, curr[key]);
                    if (Object.keys(nested).length > 0) {
                        result[key] = nested;
                    }
                } else if (curr[key] !== orig[key]) {
                    result[key] = curr[key];
                }
            }
            return result;
        };

        return getDiff(this.originalConfig, current);
    }

    onAudioOutputChange(event: Event) {
        const target = event.target as HTMLSelectElement;
        const id = parseInt(target.value, 10);
        const selected = this.audioOutputs.find(d => d.id === id) || null;

        this.selectedAudioOutput = selected;
        this.settingsForm.get('voice.outputId')?.setValue(id);
    }

    onWindowsOutputChange(event: Event) {
        const target = event.target as HTMLSelectElement;
        const id = parseInt(target.value, 10);
        const selected = this.windowsOutputs.find(d => d.id === id) || null;

        this.selectedWindowsOutput = selected;
        this.settingsForm.get('voice.windowsOutputId')?.setValue(id);
    }

    clickUpdateConfig() {
        const changes = this.getModifiedConfig();

        if (Object.keys(changes).length === 0) {
            console.log("Нет изменений");
            return;
        }

        console.log({
            changes
        });


        this.configService.updateConfig$(changes).subscribe(result => {
            console.log({ result });
            this.originalConfig = JSON.parse(JSON.stringify(this.settingsForm.value)); // обновляем базу
        });
    }

    applyPreset(presetName: string) {
        const preset = this.presets.find(p => p.name === presetName);
        if (preset) {
            this.generationSettingsForm.patchValue(preset);
            // this.apiService.applyPreset(presetName).subscribe(() => {
            //     this.selectedPresetName = presetName;
            // });
        }
    }

    saveOrUpdatePreset() {
        const current = this.generationSettingsForm.value;
        this.configService.saveGenerationPreset$(current).subscribe()
    }

    hasChanges(): boolean {
        const current = this.settingsForm.getRawValue();
        return JSON.stringify(current) !== JSON.stringify(this.originalConfig);
    }

}
