export type MessageMediaCategory = 'image' | 'audio' | 'video' | 'document' | 'other';

export interface MessageMedia {
    id: string;
    name: string;
    mimeType: string;
    size: number;
    category: MessageMediaCategory;
    description?: string;
    url?: string;
    data?: string;
    dataUrl?: string;
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    isPending?: boolean;
    media?: MessageMedia[];
}
