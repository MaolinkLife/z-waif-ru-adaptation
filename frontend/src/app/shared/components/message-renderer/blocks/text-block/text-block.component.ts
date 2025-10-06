// blocks/text-block/text-block.component.ts
import { Component, Input, OnChanges } from '@angular/core';

@Component({
    selector: 'app-text-block',
    templateUrl: './text-block.component.html',
    styleUrls: ['./text-block.component.less']
})
export class TextBlockComponent implements OnChanges {
    @Input() content: string = '';
    @Input() isStreaming: boolean = false;

    displayContent: string = '';
    private typingIndex: number = 0;
    private typingInterval: any;

    ngOnChanges(): void {
        if (this.isStreaming) {
            this.startTyping();
        } else {
            this.displayContent = this.content;
            this.stopTyping();
        }
    }

    private startTyping(): void {
        this.stopTyping();
        this.typingIndex = 0;
        this.displayContent = '';

        this.typingInterval = setInterval(() => {
            if (this.typingIndex < this.content.length) {
                this.displayContent += this.content[this.typingIndex];
                this.typingIndex++;
            } else {
                this.stopTyping();
            }
        }, 20); // Скорость печатания
    }

    private stopTyping(): void {
        if (this.typingInterval) {
            clearInterval(this.typingInterval);
            this.typingInterval = null;
        }
    }

    ngOnDestroy(): void {
        this.stopTyping();
    }
}
