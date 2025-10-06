import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

interface RagSearchStrategy {
    sessionContext: {
        enabled: boolean;
        maxMessages: number;
        lookBackToToday: boolean;
    };
    dailySummary: {
        enabled: boolean;
        lookBackDays: number;
        useTags: boolean;
    };
    longTermMemory: {
        enabled: boolean;
        vectorSearch: boolean;
        graphSearch: boolean;
        priorityRules: boolean;
    };
    fallback: {
        askUser: boolean;
        autoLearn: boolean;
    };
}

interface RagMemory {
    facts: {
        enabled: boolean;
        priorityRules: string[];
        autoUpdate: boolean;
    };
    graph: {
        enabled: boolean;
        relationships: boolean;
        inference: boolean;
    };
}

interface RagConfig {
    enabled: boolean;
    embeddingModel: string;
    vectorDbPath: string;
    chunkSize: number;
    chunkOverlap: number;
    topK: number;
    similarityThreshold: number;
    enableCaching: boolean;
    cacheTtl: number;
    searchStrategy: RagSearchStrategy;
    memory: RagMemory;
}

@Component({
    selector: 'app-rag-settings',
    templateUrl: './rag-settings.component.html',
    styleUrls: ['./rag-settings.component.less']
})
export class RagSettingsComponent implements OnInit {
    ragForm: FormGroup;
    originalConfig: any = {};

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private localizationService: LocalizationService
    ) {
        this.ragForm = this.createForm();
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
                this.originalConfig = { ...config.rag };
                this.patchFormWithRagConfig(config.rag);
            }
        });
    }

    private patchFormWithRagConfig(ragConfig: any): void {
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

        // Patch all settings
        this.ragForm.patchValue({
            ...basicSettings,
            ...strategySettings,
            ...memorySettings
        });
    }

    private buildRagConfigFromForm(): any {
        const formValue = this.ragForm.value;

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
            const updateData = { rag: changes };
            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    console.log('RAG settings updated:', response);
                    this.originalConfig = this.buildRagConfigFromForm();
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
}
