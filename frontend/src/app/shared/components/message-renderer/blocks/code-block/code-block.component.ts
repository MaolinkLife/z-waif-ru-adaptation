// blocks/code-block/code-block.component.ts
import { Component, Input, OnInit } from '@angular/core';

@Component({
    selector: 'app-code-block',
    templateUrl: './code-block.component.html',
    styleUrls: ['./code-block.component.less']
})
export class CodeBlockComponent implements OnInit {
    @Input() content: string = '';
    @Input() language: string = 'plaintext';

    highlightedContent: string = '';

    ngOnInit(): void {
        this.highlightedContent = this.highlightCode(this.content, this.language);
    }

    private highlightCode(code: string, language: string): string {
        // Здесь можно интегрировать библиотеку подсветки синтаксиса
        // Например, Prism.js или highlight.js
        return `<pre><code class="language-${language}">${this.escapeHtml(code)}</code></pre>`;
    }

    private escapeHtml(unsafe: string): string {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "<")
            .replace(/>/g, ">")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}
