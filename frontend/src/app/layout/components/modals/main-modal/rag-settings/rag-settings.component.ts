import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { FormBuilder, FormGroup, FormArray } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';
import { RagConfig, RagVectorProfile } from '../../../../../core/models/project-config.model';

@Component({
    selector: 'app-rag-settings',
    templateUrl: './rag-settings.component.html',
    styleUrls: ['./rag-settings.component.less']
})
export class RagSettingsComponent implements OnInit {
    ragForm: FormGroup;
    originalConfig: any = {};
    private readonly defaultVectorProfiles: Record<string, RagVectorProfile> = {
        embed768: {
            label: '768d • nomic-embed-text',
            enabled: true,
            provider: 'ollama',
            model: 'nomic-embed-text',
            topK: 8,
            threshold: 0.9,
            endpoint: 'http://localhost:11434/api/embeddings',
            timeout: 30,
            maxRetries: 2,
            retryBackoff: 0.75,
        },
        embed384: {
            label: '384d • all-MiniLM-L6-v2',
            enabled: true,
            provider: 'st',
            model: 'all-MiniLM-L6-v2',
            topK: 10,
            threshold: 0.9,
            device: 'cpu',
        },
    };

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private localizationService: LocalizationService,
        private cdr: ChangeDetectorRef
    ) {
        this.ragForm = this.createForm();
    }

    get vectorProfiles(): FormArray {
        return this.ragForm.get('vectorProfiles') as FormArray;
    }

    get vectorProfilesControls() {
        return this.vectorProfiles.controls;
    }

    ngOnInit(): void {
        this.loadConfig();
        this.localizationService.init();
    }

    private createForm(): FormGroup {
        return this.fb.group({
            // Basic settings
            enabled: [true],
            embeddingModel: ['all-MiniLM-L6-v2'],
            vectorDbPath: ['./data/vector_db'],
            chunkSize: [500],
            chunkOverlap: [50],
            topK: [5],
            similarityThreshold: [0.7],
            enableCaching: [true],
            cacheTtl: [60],

            // Hybrid retrieval controls
            retrievalRecentLimit: [32],
            retrievalSessionEnabled: [true],
            retrievalSessionWindow: ['day'],
            retrievalKeywordEnabled: [true],
            retrievalKeywordMaxCandidates: [8],
            retrievalKeywordMinScore: [0.2],
            retrievalKeywordMinOverlap: [0.25],
            retrievalKeywordBoostUser: [1.05],
            retrievalKeywordBoostAssistant: [0.95],
            retrievalKeywordStopwords: [''],
            primaryVector: ['embed768'],
            shortTermEnabled: [true],
            shortTermThreshold: [0.6],
            rerankEnabled: [true],
            rerankTopN: [6],
            rerankUsePrimary: [true],
            rerankBoostRecency: [0.15],
            rerankWeightEmbedding: [0.65],
            rerankWeightKeyword: [0.25],
            rerankWeightShortTerm: [0.1],
            loreTopK: [3],
            loreSimilarityThreshold: [0.7],
            vectorProfiles: this.fb.array([]),

            // Search strategy settings
            sessionContextEnabled: [true],
            sessionContextMaxMessages: [32],
            sessionContextLookBackToToday: [true],

            dailySummaryEnabled: [true],
            dailySummaryLookBackDays: [7],
            dailySummaryUseTags: [true],

            longTermMemoryEnabled: [true],
            longTermMemoryVectorSearch: [true],
            longTermMemoryGraphSearch: [true],
            longTermMemoryPriorityRules: [true],

            fallbackAskUser: [true],
            fallbackAutoLearn: [true],

            // Memory settings
            factsEnabled: [true],
            factsAutoUpdate: [true],

            graphEnabled: [true],
            graphRelationships: [true],
            graphInference: [true]
        });
    }

    private loadConfig(): void {
        this.configService.getConfig$().subscribe(config => {
            if (config && config.rag) {
                this.patchFormWithRagConfig(config.rag as RagConfig);
            }
        });
    }

    private patchFormWithRagConfig(ragConfig: RagConfig): void {
        // Basic settings
        const basicSettings = {
            enabled: ragConfig.enabled ?? true,
            embeddingModel: ragConfig.embeddingModel ?? 'all-MiniLM-L6-v2',
            vectorDbPath: ragConfig.vectorDbPath ?? './data/vector_db',
            chunkSize: ragConfig.chunkSize ?? 500,
            chunkOverlap: ragConfig.chunkOverlap ?? 50,
            topK: ragConfig.topK ?? 5,
            similarityThreshold: ragConfig.similarityThreshold ?? 0.7,
            enableCaching: ragConfig.enableCaching ?? true,
            cacheTtl: ragConfig.cacheTtl ?? 60
        };

        const retrieval = ragConfig.retrieval;
        const vectorProfiles = retrieval?.vectors?.profiles ?? {};
        const profilesWithFallback =
            Object.keys(vectorProfiles).length > 0
                ? vectorProfiles
                : this.defaultVectorProfiles;

        let primaryVector = retrieval?.vectors?.primary ?? '';
        const profileKeys = Object.keys(profilesWithFallback);
        if (
            (!primaryVector || !profilesWithFallback[primaryVector]) &&
            profileKeys.length > 0
        ) {
            primaryVector = profileKeys[0];
        }
        if (profileKeys.length === 0) {
            primaryVector = Object.keys(this.defaultVectorProfiles)[0] ?? '';
        }

        const retrievalSettings = {
            retrievalRecentLimit: retrieval?.recent?.limit ?? 32,
            retrievalSessionEnabled: retrieval?.session?.enabled ?? true,
            retrievalSessionWindow: retrieval?.session?.window ?? 'day',
            retrievalKeywordEnabled: retrieval?.keyword?.enabled ?? true,
            retrievalKeywordMaxCandidates: retrieval?.keyword?.maxCandidates ?? 8,
            retrievalKeywordMinScore: retrieval?.keyword?.minScore ?? 0.2,
            retrievalKeywordMinOverlap: retrieval?.keyword?.minOverlap ?? 0.25,
            retrievalKeywordBoostUser: retrieval?.keyword?.boostUser ?? 1.05,
            retrievalKeywordBoostAssistant: retrieval?.keyword?.boostAssistant ?? 0.95,
            retrievalKeywordStopwords: (retrieval?.keyword?.stopwords ?? []).join(', '),
            primaryVector,
            shortTermEnabled: retrieval?.shortTerm?.enabled ?? true,
            shortTermThreshold: retrieval?.shortTerm?.threshold ?? 0.6,
            rerankEnabled: retrieval?.rerank?.enabled ?? true,
            rerankTopN: retrieval?.rerank?.topN ?? 6,
            rerankUsePrimary: retrieval?.rerank?.usePrimaryRerank ?? true,
            rerankBoostRecency: retrieval?.rerank?.boostRecency ?? 0.15,
            rerankWeightEmbedding: retrieval?.rerank?.weights?.embedding ?? 0.65,
            rerankWeightKeyword: retrieval?.rerank?.weights?.keyword ?? 0.25,
            rerankWeightShortTerm: retrieval?.rerank?.weights?.shortTerm ?? 0.1,
            loreTopK: ragConfig.lore?.topK ?? 3,
            loreSimilarityThreshold: ragConfig.lore?.similarityThreshold ?? 0.7,
        };

        // Search strategy settings
        const searchStrategy = ragConfig.searchStrategy || {};
        const sessionContext = searchStrategy.sessionContext || {};
        const dailySummary = searchStrategy.dailySummary || {};
        const longTermMemory = searchStrategy.longTermMemory || {};
        const fallback = searchStrategy.fallback || {};

        const strategySettings = {
            sessionContextEnabled: sessionContext.enabled ?? true,
            sessionContextMaxMessages: sessionContext.maxMessages ?? 32,
            sessionContextLookBackToToday: sessionContext.lookBackToToday ?? true,

            dailySummaryEnabled: dailySummary.enabled ?? true,
            dailySummaryLookBackDays: dailySummary.lookBackDays ?? 7,
            dailySummaryUseTags: dailySummary.useTags ?? true,

            longTermMemoryEnabled: longTermMemory.enabled ?? true,
            longTermMemoryVectorSearch: longTermMemory.vectorSearch ?? true,
            longTermMemoryGraphSearch: longTermMemory.graphSearch ?? true,
            longTermMemoryPriorityRules: longTermMemory.priorityRules ?? true,

            fallbackAskUser: fallback.askUser ?? true,
            fallbackAutoLearn: fallback.autoLearn ?? true
        };

        // Memory settings
        const memory = ragConfig.memory || {};
        const facts = memory.facts || {};
        const graph = memory.graph || {};

        const memorySettings = {
            factsEnabled: facts.enabled ?? true,
            factsAutoUpdate: facts.autoUpdate ?? true,

            graphEnabled: graph.enabled ?? true,
            graphRelationships: graph.relationships ?? true,
            graphInference: graph.inference ?? true
        };

        this.setVectorProfiles(
            profilesWithFallback as Record<string, RagVectorProfile>
        );

        // Patch all settings
        this.ragForm.patchValue({
            ...basicSettings,
            ...retrievalSettings,
            ...strategySettings,
            ...memorySettings
        }, { emitEvent: false });

        this.ragForm.updateValueAndValidity({ emitEvent: false });
        this.ragForm.markAsPristine();
        this.cdr.detectChanges();

        const snapshot = this.buildRagConfigFromForm();
        this.originalConfig = JSON.parse(JSON.stringify(snapshot));
    }

    private setVectorProfiles(profiles: Record<string, RagVectorProfile>): void {
        const array = this.vectorProfiles;
        array.clear();

        const entries =
            Object.entries(profiles || {}).length > 0
                ? Object.entries(profiles)
                : Object.entries(this.defaultVectorProfiles);

        entries.forEach(([key, profile]) => {
            array.push(
                this.fb.group({
                    key: [key],
                    label: [profile?.label ?? key],
                    enabled: [profile?.enabled ?? true],
                    provider: [profile?.provider ?? 'auto'],
                    model: [profile?.model ?? ''],
                    topK: [profile?.topK ?? this.defaultVectorProfiles[key]?.topK ?? 5],
                    threshold: [profile?.threshold ?? this.defaultVectorProfiles[key]?.threshold ?? 0.9],
                    endpoint: [profile?.endpoint ?? ''],
                    timeout: [profile?.timeout ?? null],
                    maxRetries: [profile?.maxRetries ?? null],
                    retryBackoff: [profile?.retryBackoff ?? null],
                    device: [profile?.device ?? ''],
                })
            );
        });

        array.updateValueAndValidity({ emitEvent: false });
        this.cdr.detectChanges();
    }

    private buildVectorProfilesFromForm(): Record<string, RagVectorProfile> {
        const result: Record<string, RagVectorProfile> = {};
        this.vectorProfiles.controls.forEach((control) => {
            const value = control.value;
            if (!value?.key) {
                return;
            }
            const defaults = this.defaultVectorProfiles[value.key] || {};
            const endpoint = typeof value.endpoint === 'string' ? value.endpoint.trim() : '';
            const timeout = this.parseOptionalNumber(value.timeout, defaults.timeout);
            const maxRetries = this.parseOptionalNumber(value.maxRetries, defaults.maxRetries);
            const retryBackoff = this.parseOptionalNumber(value.retryBackoff, defaults.retryBackoff);
            const topK = this.parseOptionalNumber(value.topK, defaults.topK ?? 5) ?? 5;
            const threshold = this.parseOptionalNumber(value.threshold, defaults.threshold ?? 0.9) ?? 0.9;
            result[value.key] = {
                label: value.label || defaults.label || value.key,
                enabled:
                    value.enabled !== undefined
                        ? !!value.enabled
                        : defaults.enabled ?? true,
                provider: value.provider || defaults.provider || 'auto',
                model: value.model || defaults.model || '',
                topK,
                threshold,
                endpoint: endpoint || defaults.endpoint,
                timeout,
                maxRetries,
                retryBackoff,
                device: value.device
                    ? String(value.device).trim()
                    : defaults.device,
            };
        });
        return result;
    }

    private parseOptionalNumber(value: any, fallback?: number): number | undefined {
        if (value === null || value === undefined || value === '') {
            return fallback;
        }
        const num = Number(value);
        if (Number.isFinite(num)) {
            return num;
        }
        return fallback;
    }

    private parseStopwords(value: string): string[] {
        if (!value) {
            return [];
        }
        return value
            .split(/[,;\n]/)
            .map((item) => item.trim())
            .filter((item) => item.length > 0);
    }

    private buildRagConfigFromForm(): any {
        const formValue = this.ragForm.value;
        const vectorProfiles = this.buildVectorProfilesFromForm();
        let primaryVector = formValue.primaryVector;
        const profileKeys = Object.keys(vectorProfiles);
        if ((!primaryVector || !vectorProfiles[primaryVector]) && profileKeys.length > 0) {
            primaryVector = profileKeys[0];
        }

        return {
            enabled: formValue.enabled,
            embeddingModel: formValue.embeddingModel,
            vectorDbPath: formValue.vectorDbPath,
            chunkSize: formValue.chunkSize,
            chunkOverlap: formValue.chunkOverlap,
            topK: formValue.topK,
            similarityThreshold: formValue.similarityThreshold,
            enableCaching: formValue.enableCaching,
            cacheTtl: formValue.cacheTtl,
            retrieval: {
                recent: {
                    limit: Number(formValue.retrievalRecentLimit),
                },
                session: {
                    enabled: !!formValue.retrievalSessionEnabled,
                    window: formValue.retrievalSessionWindow,
                },
                keyword: {
                    enabled: !!formValue.retrievalKeywordEnabled,
                    maxCandidates: Number(formValue.retrievalKeywordMaxCandidates),
                    minScore: Number(formValue.retrievalKeywordMinScore),
                    minOverlap: Number(formValue.retrievalKeywordMinOverlap),
                    boostUser: Number(formValue.retrievalKeywordBoostUser),
                    boostAssistant: Number(formValue.retrievalKeywordBoostAssistant),
                    stopwords: this.parseStopwords(formValue.retrievalKeywordStopwords),
                },
                vectors: {
                    primary: primaryVector,
                    profiles: vectorProfiles,
                },
                shortTerm: {
                    enabled: !!formValue.shortTermEnabled,
                    threshold: Number(formValue.shortTermThreshold),
                },
                rerank: {
                    enabled: !!formValue.rerankEnabled,
                    topN: Number(formValue.rerankTopN),
                    usePrimaryRerank: !!formValue.rerankUsePrimary,
                    boostRecency: Number(formValue.rerankBoostRecency),
                    weights: {
                        embedding: Number(formValue.rerankWeightEmbedding),
                        keyword: Number(formValue.rerankWeightKeyword),
                        shortTerm: Number(formValue.rerankWeightShortTerm),
                    },
                },
            },
            lore: {
                topK: Number(formValue.loreTopK),
                similarityThreshold: Number(formValue.loreSimilarityThreshold),
            },
            searchStrategy: {
                sessionContext: {
                    enabled: formValue.sessionContextEnabled,
                    maxMessages: formValue.sessionContextMaxMessages,
                    lookBackToToday: formValue.sessionContextLookBackToToday
                },
                dailySummary: {
                    enabled: formValue.dailySummaryEnabled,
                    lookBackDays: formValue.dailySummaryLookBackDays,
                    useTags: formValue.dailySummaryUseTags
                },
                longTermMemory: {
                    enabled: formValue.longTermMemoryEnabled,
                    vectorSearch: formValue.longTermMemoryVectorSearch,
                    graphSearch: formValue.longTermMemoryGraphSearch,
                    priorityRules: formValue.longTermMemoryPriorityRules
                },
                fallback: {
                    askUser: formValue.fallbackAskUser,
                    autoLearn: formValue.fallbackAutoLearn
                }
            },
            memory: {
                facts: {
                    enabled: formValue.factsEnabled,
                    autoUpdate: formValue.factsAutoUpdate
                },
                graph: {
                    enabled: formValue.graphEnabled,
                    relationships: formValue.graphRelationships,
                    inference: formValue.graphInference
                }
            }
        };
    }

    saveChanges(): void {
        const changes = this.getChanges();
        if (Object.keys(changes).length > 0) {
            const updateData = { rag: this.expandPathMap(changes) };
            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    console.log('RAG settings updated:', response);
                    this.originalConfig = JSON.parse(
                        JSON.stringify(this.buildRagConfigFromForm())
                    );
                },
                error: (error) => {
                    console.error('Error updating RAG settings:', error);
                }
            });
        }
    }

    private getChanges(): any {
        const current = this.buildRagConfigFromForm();
        const changes: any = {};

        const compareObjects = (currentObj: any, originalObj: any, path: string = ''): void => {
            Object.keys(currentObj).forEach(key => {
                const currentPath = path ? `${path}.${key}` : key;
                const currentValue = currentObj[key];
                const originalValue = originalObj?.[key];

                if (typeof currentValue === 'object' && currentValue !== null && !Array.isArray(currentValue)) {
                    compareObjects(currentValue, originalValue, currentPath);
                } else if (currentValue !== originalValue) {
                    changes[currentPath] = currentValue;
                }
            });
        };

        compareObjects(current, this.originalConfig);
        return changes;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }

    private expandPathMap(changes: Record<string, any>): Record<string, any> {
        const result: Record<string, any> = {};

        Object.entries(changes).forEach(([path, value]) => {
            const keys = path.split('.');
            let cursor: Record<string, any> = result;

            keys.forEach((key, index) => {
                if (index === keys.length - 1) {
                    cursor[key] = value;
                } else {
                    cursor[key] = cursor[key] ?? {};
                    cursor = cursor[key];
                }
            });
        });

        return result;
    }
}
