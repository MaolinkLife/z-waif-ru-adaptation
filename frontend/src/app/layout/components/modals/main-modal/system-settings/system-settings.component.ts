import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { ThemeService } from '../../../../../core/services/theme.service';
import { combineLatest, BehaviorSubject } from 'rxjs';
import { map, tap, finalize } from 'rxjs/operators';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

@Component({
    selector: 'app-system-settings',
    templateUrl: './system-settings.component.html',
    styleUrls: ['./system-settings.component.less']
})
export class SystemSettingsComponent implements OnInit {
    systemForm: FormGroup;
    originalConfig: any = {};
    isLoading$ = new BehaviorSubject<boolean>(true);

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private themeService: ThemeService,
        private localizationService: LocalizationService
    ) {
        this.systemForm = this.createForm();
    }

    ngOnInit(): void {
        this.initialize();
        this.localizationService.init();
        this.initLanguageChangeListener();
    }

    initLanguageChangeListener() {
        const control = this.systemForm.get('language');
        if (control) {
            control.valueChanges.subscribe(lang => {
                if (lang) {
                    localStorage.setItem('language', lang);
                    this.localizationService.setLanguage(lang);
                }
            });
        }
    }

    private initialize(): void {
        combineLatest([
            this.configService.getConfig$(),
            this.configService.getSystem$()
        ]).pipe(
            tap(() => this.isLoading$.next(true)),
            map(([config, system]: [any, any]) => {
                const currentTheme = this.themeService.getTheme();
                const combinedConfig = {
                    char_name: config?.system?.charName || 'Character Name',
                    system_prompt: system?.system?.prompt || 'You are a helpful assistant...',
                    user_name: config?.system?.userName || 'You',
                    language: config?.system?.language || 'en-US',
                    theme: currentTheme,
                    modules: config?.modules || {}
                };

                return combinedConfig;
            }),
            tap(combinedConfig => {
                this.originalConfig = combinedConfig;
                this.patchFormWithConfig(combinedConfig);
            }),
            finalize(() => this.isLoading$.next(false))
        ).subscribe();
    }

    private createForm(): FormGroup {
        return this.fb.group({
            char_name: ['Character Name'],
            system_prompt: ['You are a helpful assistant. Respond naturally and engage in meaningful conversation.'],
            user_name: ['You'],
            language: ['en-US'],
            theme: ['dark'],
            modules: this.fb.group({
                vtube_studio: [false],
                whisper: [false],
                minecraft: [false],
                gaming: [false],
                alarm: [false],
                discord: [false],
                rag: [false],
                visual: [false]
            })
        });
    }

    private patchFormWithConfig(config: any): void {
        this.systemForm.patchValue({
            char_name: config.char_name ?? 'Character Name',
            system_prompt: config.system_prompt ?? 'You are a helpful assistant. Respond naturally and engage in meaningful conversation.',
            user_name: config.user_name ?? 'You',
            language: config.language ?? 'en-US',
            theme: config.theme ?? 'dark',
            modules: config.modules ?? {}
        });
    }

    private buildConfigFromForm(): any {
        const formValue = this.systemForm.value;

        return {
            char_name: formValue.char_name,
            system_prompt: formValue.system_prompt,
            user_name: formValue.user_name,
            language: formValue.language,
            theme: formValue.theme,
            modules: formValue.modules
        };
    }

    saveChanges(): void {
        const changes = this.getChanges();
        if (Object.keys(changes).length > 0) {
            const updateData: any = {};

            if (changes.char_name !== undefined) {
                updateData.system = updateData.system || {};
                updateData.system.charName = changes.char_name;
            }
            if (changes.system_prompt !== undefined) {
                // Обновляем YAML и системный промпт
                this.configService.updateSystem$(changes.system_prompt, changes.char_name).subscribe();
            }
            if (changes.user_name !== undefined) {
                updateData.system = updateData.system || {};
                updateData.system.userName = changes.user_name;
            }
            if (changes.language !== undefined) {
                updateData.system = updateData.system || {};
                updateData.system.language = changes.language;
                this.localizationService.setLanguage(changes.language);
            }
            if (changes.theme !== undefined) {
                this.themeService.setTheme(changes.theme);
                updateData.system = updateData.system || {};
                updateData.system.theme = changes.theme;
            }
            if (changes.modules !== undefined) {
                updateData.modules = changes.modules;
            }

            console.log({
                updateData
            });


            if (Object.keys(updateData).length > 0) {
                this.configService.updateConfig$(updateData).subscribe({
                    next: (response) => {
                        console.log('System settings updated:', response);
                        this.originalConfig = this.buildConfigFromForm();
                    },
                    error: (error) => {
                        console.error('Error updating system settings:', error);
                    }
                });
            }
        }
    }

    private getChanges(): any {
        const current = this.buildConfigFromForm();
        const changes: any = {};

        for (const key in current) {
            if (JSON.stringify(current[key]) !== JSON.stringify(this.originalConfig[key])) {
                changes[key] = current[key];
            }
        }

        return changes;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }

    onThemeChange(event: any): void {
        const selectedTheme = event.target.value as 'dark' | 'light';
        this.themeService.setTheme(selectedTheme);
        this.systemForm.get('theme')?.setValue(selectedTheme);
    }
}
