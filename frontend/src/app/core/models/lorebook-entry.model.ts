// core/models/lorebook-entry.model.ts
export interface LorebookEntry {
    id?: number;
    title: string;
    content: string;
    keywords: string;
    category: string;
    active: boolean;
    created_at?: string;
    updated_at?: string;
}
