import { Component, EventEmitter, HostListener, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
import { EmojiCategory, EmojiDefinition } from './emoji-data';
import { EmojiService } from './emoji.service';

interface EmojiPanelPosition {
    x: number;
    y: number;
}

@Component({
    selector: 'app-emoji-picker',
    templateUrl: './emoji-picker.component.html',
    styleUrls: ['./emoji-picker.component.less']
})
export class EmojiPickerComponent implements OnInit, OnChanges {
    @Input() position: EmojiPanelPosition | null = null;
    @Input() displayMode: 'dropdown' | 'side-panel' = 'dropdown';
    @Input() sidePanelPosition: 'left' | 'right' | 'top' | 'bottom' = 'right';
    @Output() emojiSelect = new EventEmitter<string>();
    @Output() requestClose = new EventEmitter<void>();

    categories: EmojiCategory[] = [];
    activeCategoryId: string | null = null;
    searchTerm = '';
    filteredEmojis: EmojiDefinition[] = [];

    private readonly panelWidth = 320;
    private readonly panelHeight = 300;
    private adjustedPosition: EmojiPanelPosition = { x: 0, y: 0 };

    constructor(private readonly emojiService: EmojiService) {}

    ngOnInit(): void {
        this.categories = [...this.emojiService.getCategories()];
        this.activeCategoryId = this.categories[0]?.id ?? null;
        this.updateEmojiList();
    }

    ngOnChanges(changes: SimpleChanges): void {
        if (changes['displayMode'] && this.displayMode === 'dropdown') {
            this.recomputePosition();
        }

        if (changes['position'] && this.displayMode === 'dropdown') {
            this.recomputePosition();
        }
    }

    selectCategory(categoryId: string): void {
        if (this.activeCategoryId === categoryId) {
            return;
        }
        this.activeCategoryId = categoryId;
        this.searchTerm = '';
        this.updateEmojiList();
    }

    onSearch(term: string): void {
        this.searchTerm = term;
        const normalized = this.searchTerm.trim();
        if (normalized) {
            this.filteredEmojis = this.emojiService.search(normalized);
        } else {
            this.updateEmojiList();
        }
    }

    selectEmoji(symbol: string): void {
        this.emojiSelect.emit(symbol);
    }

    @HostListener('click', ['$event'])
    handleComponentClick(event: MouseEvent): void {
        event.stopPropagation();
    }

    @HostListener('document:keydown.escape')
    handleEscape(): void {
        this.requestClose.emit();
    }

    get panelStyle(): { [key: string]: string } {
        if (this.displayMode !== 'dropdown') {
            return {};
        }

        return {
            left: `${this.adjustedPosition.x}px`,
            top: `${this.adjustedPosition.y}px`
        };
    }

    get containerClasses(): { [key: string]: boolean } {
        return {
            'mode-dropdown': this.displayMode === 'dropdown',
            'mode-side-panel': this.displayMode === 'side-panel',
            'side-left': this.displayMode === 'side-panel' && this.sidePanelPosition === 'left',
            'side-right': this.displayMode === 'side-panel' && this.sidePanelPosition === 'right',
            'side-top': this.displayMode === 'side-panel' && this.sidePanelPosition === 'top',
            'side-bottom': this.displayMode === 'side-panel' && this.sidePanelPosition === 'bottom'
        };
    }

    private updateEmojiList(): void {
        if (this.activeCategoryId) {
            this.filteredEmojis = this.emojiService.getEmojisByCategory(this.activeCategoryId);
        } else {
            this.filteredEmojis = [];
        }
    }

    private recomputePosition(): void {
        if (this.displayMode !== 'dropdown') {
            this.adjustedPosition = { x: 0, y: 0 };
            return;
        }

        const source = this.position ?? { x: 0, y: 0 };
        let x = source.x;
        let y = source.y;

        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (x + this.panelWidth > viewportWidth - 10) {
            x = Math.max(10, viewportWidth - this.panelWidth - 10);
        }

        if (x < 10) {
            x = 10;
        }

        if (y + this.panelHeight > viewportHeight - 10) {
            y = Math.max(10, viewportHeight - this.panelHeight - 10);
        }

        if (y < 10) {
            y = 10;
        }

        this.adjustedPosition = { x, y };
    }
}
