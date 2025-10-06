import { Component, Input, OnChanges, SimpleChanges, OnDestroy } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { BehaviorSubject } from 'rxjs';
import { MessageBlock, MessageParserService } from './services/message-parser.service';

interface SafeMessageBlock extends MessageBlock {
    safeContent?: SafeHtml;
    rawContent: string;
    isExpanded?: boolean;
}

@Component({
    selector: 'app-message-renderer',
    templateUrl: './message-renderer.component.html',
    styleUrls: ['./message-renderer.component.less']
})
export class MessageRendererComponent implements OnChanges, OnDestroy {
    @Input() content: string = '';
    @Input() isStreaming: boolean = false;

    // теперь Observable
    private blocksSubject = new BehaviorSubject<SafeMessageBlock[]>([]);
    blocks$ = this.blocksSubject.asObservable();

    private previousBlocks: MessageBlock[] = [];
    private expandedState = new Map<string, boolean>();
    private wasStreaming = false;

    constructor(
        private parser: MessageParserService,
        private sanitizer: DomSanitizer
    ) { }

    ngOnChanges(changes: SimpleChanges): void {
        if (changes['isStreaming']) {
            if (this.wasStreaming && !this.isStreaming) {
                this.expandedState.clear();
            }
            this.wasStreaming = this.isStreaming;
        }

        if (changes['content'] || changes['isStreaming']) {
            this.parseContent();
        }
    }

    private parseContent(): void {
        if (!this.content) {
            this.blocksSubject.next([]);
            this.previousBlocks = [];
            this.expandedState.clear();
            return;
        }

        let parsedBlocks: MessageBlock[];
        if (this.isStreaming) {
            parsedBlocks = this.parser.parseStreaming(this.content);
        } else {
            parsedBlocks = this.parser.parseComplete(this.content);
        }

        const safeBlocks: SafeMessageBlock[] = parsedBlocks.map(block => {
            const key = this.buildBlockKey(block);
            let isExpanded = false;

            if (block.type === 'thinking') {
                if (this.isStreaming) {
                    isExpanded = true;
                } else {
                    isExpanded = this.expandedState.get(key) ?? false;
                    this.expandedState.set(key, isExpanded);
                }
            }

            return {
                ...block,
                rawContent: block.content,
                safeContent: this.sanitizer.bypassSecurityTrustHtml(block.content),
                isExpanded,
            };
        });

        this.blocksSubject.next(safeBlocks);
        this.previousBlocks = [...parsedBlocks];
    }

    ngOnDestroy(): void {
        this.previousBlocks = [];
        this.blocksSubject.complete();
    }

    trackByBlock(index: number, block: MessageBlock): string {
        return block.id;
    }

    toggleThinking(block: SafeMessageBlock): void {
        if (this.isStreaming || block.type !== 'thinking') {
            return;
        }

        block.isExpanded = !block.isExpanded;
        const key = this.buildSafeBlockKey(block);
        this.expandedState.set(key, !!block.isExpanded);
        this.blocksSubject.next([...this.blocksSubject.value]);
    }

    private buildBlockKey(block: MessageBlock): string {
        return `${block.type}:${block.content}`;
    }

    private buildSafeBlockKey(block: SafeMessageBlock): string {
        return `${block.type}:${block.rawContent}`;
    }
}
