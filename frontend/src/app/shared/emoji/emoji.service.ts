import { Injectable } from '@angular/core';
import { EMOJI_CATEGORIES, EMOJI_DATA, EmojiCategory, EmojiDefinition } from './emoji-data';

@Injectable({ providedIn: 'root' })
export class EmojiService {
    private readonly categories = EMOJI_CATEGORIES;
    private readonly emojis = EMOJI_DATA;

    getCategories(): readonly EmojiCategory[] {
        return this.categories;
    }

    getEmojisByCategory(categoryId: string): EmojiDefinition[] {
        return this.emojis.filter((emoji) => emoji.category === categoryId);
    }

    search(term: string): EmojiDefinition[] {
        const normalized = term.trim().toLowerCase();
        if (!normalized) {
            return [...this.emojis];
        }

        return this.emojis.filter((emoji) =>
            emoji.name.toLowerCase().includes(normalized) ||
            emoji.symbol.includes(normalized) ||
            emoji.keywords.some((keyword) => keyword.includes(normalized))
        );
    }
}
