import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { BehaviorSubject } from 'rxjs';
import { finalize, take } from 'rxjs/operators';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';

@Component({
    selector: 'app-analyzer-settings',
    templateUrl: './analyzer-settings.component.html',
    styleUrls: ['./analyzer-settings.component.less']
})
export class AnalyzerSettingsComponent implements OnInit {
    analyzerForm: FormGroup;
    isLoading$ = new BehaviorSubject<boolean>(true);
    originalConfig: any = {};

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private notificationService: NotificationService
    ) {
        this.analyzerForm = this.createForm();
    }

    ngOnInit(): void {
        this.loadConfig();

        // Подписка на изменения провайдера
        this.analyzerForm.get('activeProvider')?.valueChanges.subscribe((provider: string) => {
            this.toggleFallbackControls(provider);
        });
    }

    private createForm(): FormGroup {
        return this.fb.group({
            activeProvider: ['openrouter', Validators.required],
            fallbackOpenrouter: [false],
            fallbackOllama: [true],
            providers: this.fb.group({})
        });
    }

    private loadConfig(): void {
        this.isLoading$.next(true);

        this.configService.getConfig$().pipe(
            take(1),
            finalize(() => this.isLoading$.next(false))
        ).subscribe({
            next: (config: any) => {
                const analyzer = config?.analyzer || {};
                const providers = analyzer.providers || {};

                // Загружаем основные настройки
                this.analyzerForm.patchValue({
                    activeProvider: analyzer.activeProvider || 'openrouter',
                    fallbackOpenrouter: (analyzer.fallbackOrder || []).includes('openrouter'),
                    fallbackOllama: (analyzer.fallbackOrder || []).includes('ollama'),
                });

                // Загружаем провайдеров в динамическую форму
                const providersGroup = this.analyzerForm.get('providers') as FormGroup;
                Object.keys(providers).forEach(providerName => {
                    const providerConfig = providers[providerName];

                    // Создаём FormGroup для провайдера в camelCase
                    const providerGroup = this.fb.group({
                        apiKey: [providerConfig.apiKey || ''],
                        model: [providerConfig.model || '', Validators.required],
                        temperature: [providerConfig.temperature || 0.7, [Validators.min(0), Validators.max(2)]],
                        maxTokens: [providerConfig.maxTokens || 1024, [Validators.min(1), Validators.max(4096)]],
                    });

                    providersGroup.addControl(providerName, providerGroup);
                });

                this.originalConfig = this.buildAnalyzerConfigFromForm();
                this.toggleFallbackControls(this.analyzerForm.get('activeProvider')?.value);
            },
            error: (error) => {
                console.error('Error loading analyzer config:', error);
                this.notificationService.open({
                    title: 'Error',
                    type: 'error',
                    message: 'Failed to load analyzer configuration',
                    autoClose: true
                });
            }
        });
    }

    private toggleFallbackControls(activeProvider: string): void {
        const fallbackOpenrouterCtrl = this.analyzerForm.get('fallbackOpenrouter');
        const fallbackOllamaCtrl = this.analyzerForm.get('fallbackOllama');

        if (activeProvider === 'openrouter') {
            fallbackOpenrouterCtrl?.disable({ emitEvent: false });
            fallbackOpenrouterCtrl?.setValue(false);
            fallbackOllamaCtrl?.enable({ emitEvent: false });
        } else if (activeProvider === 'ollama') {
            fallbackOllamaCtrl?.disable({ emitEvent: false });
            fallbackOllamaCtrl?.setValue(false);
            fallbackOpenrouterCtrl?.enable({ emitEvent: false });
        } else {
            fallbackOpenrouterCtrl?.enable({ emitEvent: false });
            fallbackOllamaCtrl?.enable({ emitEvent: false });
        }
    }

    saveChanges(): void {
        const changes = this.getChanges();
        if (Object.keys(changes).length === 0) {
            return;
        }

        // Отправляем изменения в формате model (camelCase)
        this.configService.updateConfig$({ analyzer: changes }).subscribe({
            next: () => {
                this.notificationService.open({
                    title: 'Success',
                    type: 'success',
                    message: 'Analyzer settings updated successfully',
                    autoClose: true
                });
                this.originalConfig = this.buildAnalyzerConfigFromForm();
                this.analyzerForm.markAsPristine();
            },
            error: (error) => {
                console.error('Error updating analyzer settings:', error);
                this.notificationService.open({
                    title: 'Error',
                    type: 'error',
                    message: 'Failed to update analyzer settings',
                    autoClose: true
                });
            }
        });
    }

    private buildAnalyzerConfigFromForm(): any {
        const formValue = this.analyzerForm.getRawValue();
        const fallbackOrder: string[] = [];

        if (formValue.fallbackOpenrouter && formValue.activeProvider !== 'openrouter') {
            fallbackOrder.push('openrouter');
        }
        if (formValue.fallbackOllama && formValue.activeProvider !== 'ollama') {
            fallbackOrder.push('ollama');
        }

        const providers = { ...formValue.providers };
        Object.keys(providers).forEach(providerName => {
            const provider = providers[providerName];
            // Приводим числовые поля
            provider.temperature = Number(provider.temperature);
            provider.maxTokens = Number(provider.maxTokens);
        });

        return {
            activeProvider: formValue.activeProvider,
            fallbackOrder: fallbackOrder,
            providers: providers
        };
    }

    private getChanges(): any {
        const current = this.buildAnalyzerConfigFromForm();
        const original = this.originalConfig;
        const changes: Record<string, any> = {};

        const compare = (currentObj: any, originalObj: any, path: string = ''): void => {
            Object.keys(currentObj).forEach((key) => {
                const currentPath = path ? `${path}.${key}` : key;
                const currentValue = currentObj[key];
                const originalValue = originalObj?.[key];

                if (currentValue && typeof currentValue === 'object' && !Array.isArray(currentValue)) {
                    if (originalValue && typeof originalValue === 'object') {
                        const nestedChanges: Record<string, any> = {};
                        compare(currentValue, originalValue, '');
                        if (Object.keys(nestedChanges).length > 0) {
                            changes[currentPath] = nestedChanges;
                        }
                    } else if (JSON.stringify(currentValue) !== JSON.stringify(originalValue)) {
                        changes[currentPath] = currentValue;
                    }
                } else if (Array.isArray(currentValue)) {
                    const originalArray = Array.isArray(originalValue) ? originalValue : [];
                    if (JSON.stringify(currentValue) !== JSON.stringify(originalArray)) {
                        changes[currentPath] = currentValue;
                    }
                } else if (currentValue !== originalValue) {
                    changes[currentPath] = currentValue;
                }
            });
        };

        compare(current, original);
        return changes;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }

    // Геттеры для удобства доступа к контролам
    get providersForm() {
        return this.analyzerForm.get('providers') as FormGroup;
    }

    get activeProvider() {
        return this.analyzerForm.get('activeProvider')?.value;
    }
}
