import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { BehaviorSubject } from 'rxjs';
import { finalize, take } from 'rxjs/operators';
import { ConfigService } from '../../../../../core/services/config.service';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';

@Component({
    selector: 'app-moral-settings',
    templateUrl: './moral-settings.component.html',
    styleUrls: ['./moral-settings.component.less']
})
export class MoralSettingsComponent implements OnInit {
    moralForm: FormGroup;
    isLoading$ = new BehaviorSubject<boolean>(true);
    originalConfig: any = {};

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private notificationService: NotificationService
    ) {
        this.moralForm = this.createForm();
    }

    ngOnInit(): void {
        this.loadConfig();
        this.moralForm.get('activeProvider')?.valueChanges.subscribe((provider: string) => {
            this.toggleFallbackControls(provider);
        });
    }

    private createForm(): FormGroup {
        return this.fb.group({
            enabled: [true],
            activeProvider: ['ollama', Validators.required],
            fallbackHeuristic: [true],
            fallbackOllama: [true],
            fallbackOpenrouter: [false],
            providers: this.fb.group({
                ollama: this.fb.group({
                    model: ['', Validators.required],
                    temperature: [0.6, [Validators.min(0), Validators.max(2)]],
                    maxTokens: [512, [Validators.min(1), Validators.max(4096)]],
                }),
                openrouter: this.fb.group({
                    apiKey: [''],
                    model: ['', Validators.required],
                    temperature: [0.6, [Validators.min(0), Validators.max(2)]],
                    maxTokens: [512, [Validators.min(1), Validators.max(4096)]],
                }),
            }),
        });
    }

    private loadConfig(): void {
        this.isLoading$.next(true);

        this.configService
            .getConfig$()
            .pipe(
                take(1),
                finalize(() => this.isLoading$.next(false))
            )
            .subscribe({
                next: (config: any) => {
                    const moral = config?.moral || {};
                    const providers = moral.providers || {};

                    this.moralForm.patchValue({
                        enabled: moral.enabled ?? true,
                        activeProvider: moral.activeProvider || 'ollama',
                        fallbackHeuristic: (moral.fallbackOrder || []).includes('heuristic'),
                        fallbackOllama: (moral.fallbackOrder || []).includes('ollama'),
                        fallbackOpenrouter: (moral.fallbackOrder || []).includes('openrouter'),
                    });

                    const providersGroup = this.moralForm.get('providers') as FormGroup;
                    const ollamaGroup = providersGroup.get('ollama') as FormGroup;
                    const openrouterGroup = providersGroup.get('openrouter') as FormGroup;

                    if (providers.ollama) {
                        ollamaGroup.patchValue({
                            model: providers.ollama.model || '',
                            temperature: providers.ollama.temperature ?? 0.6,
                            maxTokens: providers.ollama.maxTokens ?? providers.ollama.max_tokens ?? 512,
                        });
                    }

                    if (providers.openrouter) {
                        openrouterGroup.patchValue({
                            apiKey: providers.openrouter.apiKey || providers.openrouter.api_key || '',
                            model: providers.openrouter.model || '',
                            temperature: providers.openrouter.temperature ?? 0.6,
                            maxTokens: providers.openrouter.maxTokens ?? providers.openrouter.max_tokens ?? 512,
                        });
                    }

                    this.originalConfig = this.buildMoralConfigFromForm();
                    this.toggleFallbackControls(this.moralForm.get('activeProvider')?.value);
                },
                error: (error) => {
                    console.error('Error loading moral config:', error);
                    this.notificationService.open({
                        title: 'Error',
                        type: 'error',
                        message: 'Failed to load Moral Matrix configuration',
                        autoClose: true,
                    });
                },
            });
    }

    private toggleFallbackControls(activeProvider: string): void {
        const fallbackHeuristicCtrl = this.moralForm.get('fallbackHeuristic');
        const fallbackOllamaCtrl = this.moralForm.get('fallbackOllama');
        const fallbackOpenrouterCtrl = this.moralForm.get('fallbackOpenrouter');

        if (activeProvider === 'heuristic') {
            fallbackHeuristicCtrl?.disable({ emitEvent: false });
            fallbackHeuristicCtrl?.setValue(false, { emitEvent: false });
            fallbackOllamaCtrl?.enable({ emitEvent: false });
            fallbackOpenrouterCtrl?.enable({ emitEvent: false });
        } else if (activeProvider === 'ollama') {
            fallbackOllamaCtrl?.disable({ emitEvent: false });
            fallbackOllamaCtrl?.setValue(false, { emitEvent: false });
            fallbackHeuristicCtrl?.enable({ emitEvent: false });
            fallbackOpenrouterCtrl?.enable({ emitEvent: false });
        } else if (activeProvider === 'openrouter') {
            fallbackOpenrouterCtrl?.disable({ emitEvent: false });
            fallbackOpenrouterCtrl?.setValue(false, { emitEvent: false });
            fallbackHeuristicCtrl?.enable({ emitEvent: false });
            fallbackOllamaCtrl?.enable({ emitEvent: false });
        } else {
            fallbackHeuristicCtrl?.enable({ emitEvent: false });
            fallbackOllamaCtrl?.enable({ emitEvent: false });
            fallbackOpenrouterCtrl?.enable({ emitEvent: false });
        }
    }

    saveChanges(): void {
        const changes = this.getChanges();
        if (Object.keys(changes).length === 0) {
            return;
        }

        this.configService.updateConfig$({ moral: changes }).subscribe({
            next: () => {
                this.notificationService.open({
                    title: 'Success',
                    type: 'success',
                    message: 'Moral Matrix settings updated successfully',
                    autoClose: true,
                });
                this.originalConfig = this.buildMoralConfigFromForm();
                this.moralForm.markAsPristine();
            },
            error: (error) => {
                console.error('Error updating moral settings:', error);
                this.notificationService.open({
                    title: 'Error',
                    type: 'error',
                    message: 'Failed to update Moral Matrix settings',
                    autoClose: true,
                });
            },
        });
    }

    private buildMoralConfigFromForm(): any {
        const formValue = this.moralForm.getRawValue();
        const fallbackOrder: string[] = [];

        if (formValue.fallbackHeuristic && formValue.activeProvider !== 'heuristic') {
            fallbackOrder.push('heuristic');
        }
        if (formValue.fallbackOllama && formValue.activeProvider !== 'ollama') {
            fallbackOrder.push('ollama');
        }
        if (formValue.fallbackOpenrouter && formValue.activeProvider !== 'openrouter') {
            fallbackOrder.push('openrouter');
        }

        const providers = {
            heuristic: {},
            ollama: {
                model: formValue.providers.ollama.model,
                temperature: Number(formValue.providers.ollama.temperature),
                maxTokens: Number(formValue.providers.ollama.maxTokens),
            },
            openrouter: {
                apiKey: formValue.providers.openrouter.apiKey,
                model: formValue.providers.openrouter.model,
                temperature: Number(formValue.providers.openrouter.temperature),
                maxTokens: Number(formValue.providers.openrouter.maxTokens),
            },
        };

        return {
            enabled: formValue.enabled,
            activeProvider: formValue.activeProvider,
            fallbackOrder,
            providers,
        };
    }

    private getChanges(): any {
        const current = this.buildMoralConfigFromForm();
        const original = this.originalConfig || {};
        return this.deepDiff(original, current) || {};
    }

    private deepDiff(original: any, current: any): any {
        if (Array.isArray(current)) {
            const originalArray = Array.isArray(original) ? original : [];
            if (JSON.stringify(current) === JSON.stringify(originalArray)) {
                return undefined;
            }
            return current;
        }

        if (current !== null && typeof current === 'object') {
            const diff: Record<string, any> = {};

            Object.keys(current).forEach((key) => {
                const value = this.deepDiff(original ? original[key] : undefined, current[key]);
                if (value !== undefined) {
                    diff[key] = value;
                }
            });

            return Object.keys(diff).length > 0 ? diff : undefined;
        }

        if (current !== original) {
            return current;
        }

        return undefined;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }

    get providersForm(): FormGroup {
        return this.moralForm.get('providers') as FormGroup;
    }
}
