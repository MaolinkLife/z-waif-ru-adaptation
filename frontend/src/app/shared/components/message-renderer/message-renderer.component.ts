import { Component, Input, OnChanges, SimpleChanges, OnDestroy } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { BehaviorSubject } from 'rxjs';
import { MessageBlock, MessageParserService } from './services/message-parser.service';

interface SafeMessageBlock extends MessageBlock {
    safeContent?: SafeHtml;
    rawContent: string;
    isExpanded?: boolean;
}

type CodeTokenType =
    | 'keyword'
    | 'string'
    | 'number'
    | 'boolean'
    | 'comment'
    | 'operator'
    | 'punctuation'
    | 'identifier'
    | 'whitespace'
    | 'plain';

interface CodeToken {
    type: CodeTokenType;
    value: string;
}

const JS_KEYWORDS = [
    'const',
    'let',
    'var',
    'function',
    'return',
    'if',
    'else',
    'switch',
    'case',
    'break',
    'continue',
    'for',
    'while',
    'do',
    'class',
    'extends',
    'new',
    'this',
    'super',
    'try',
    'catch',
    'finally',
    'throw',
    'await',
    'async',
    'import',
    'from',
    'export',
    'default',
    'in',
    'of',
    'instanceof',
    'delete',
    'typeof',
    'yield',
    'with',
    'switch',
    'case',
    'break',
];

const TS_KEYWORDS = [
    'interface',
    'type',
    'implements',
    'declare',
    'public',
    'private',
    'protected',
    'readonly',
    'abstract',
    'enum',
    'namespace',
    'module',
    'as',
    'any',
    'unknown',
    'never',
];

const PY_KEYWORDS = [
    'def',
    'return',
    'if',
    'elif',
    'else',
    'for',
    'while',
    'break',
    'continue',
    'class',
    'import',
    'from',
    'as',
    'pass',
    'raise',
    'try',
    'except',
    'finally',
    'with',
    'lambda',
    'nonlocal',
    'global',
    'True',
    'False',
    'None',
    'yield',
    'assert',
    'del',
];

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
            let rawContent = block.content;
            let html = '';

            if (block.type === 'thinking') {
                if (this.isStreaming) {
                    isExpanded = true;
                } else {
                    isExpanded = this.expandedState.get(key) ?? false;
                    this.expandedState.set(key, isExpanded);
                }
            }

            switch (block.type) {
                case 'text':
                    html = this.renderRichText(block.content);
                    break;
                case 'thinking':
                    html = this.renderRichText(block.content);
                    break;
                case 'header':
                    html = this.renderHeader(block.content);
                    break;
                case 'list':
                    html = this.renderList(block.items || [], block.ordered, block.isComplete);
                    rawContent = (block.items || []).join('\n');
                    break;
                case 'table':
                    html = this.renderTable(block.rows || []);
                    rawContent = JSON.stringify(block.rows || []);
                    break;
                case 'quote':
                    html = this.renderQuote(block.content);
                    break;
                case 'code':
                    html = this.highlightCode(block.content, block.language);
                    break;
                default:
                    html = this.renderRichText(block.content);
                    break;
            }

            return {
                ...block,
                rawContent,
                safeContent: this.sanitizer.bypassSecurityTrustHtml(html),
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
        if (block.type === 'list') {
            return `${block.type}:${(block.items || []).join('|')}|${block.ordered}`;
        }
        if (block.type === 'table') {
            return `${block.type}:${JSON.stringify(block.rows || [])}`;
        }
        return `${block.type}:${block.content}`;
    }

    private buildSafeBlockKey(block: SafeMessageBlock): string {
        return `${block.type}:${block.rawContent}`;
    }

    private renderRichText(content: string): string {
        if (!content) {
            return '';
        }
        const paragraphs = content
            .split(/\n{2,}/)
            .map((paragraph) => paragraph.trim())
            .filter(Boolean)
            .map((paragraph) => {
                const lines = paragraph.split(/\n/).map((line) => this.renderInline(line));
                return `<p>${lines.join('<br>')}</p>`;
            });
        return paragraphs.join('');
    }

    private renderHeader(content: string): string {
        const escaped = this.renderInline(content.trim());
        return `<h3>${escaped}</h3>`;
    }

    private renderList(items: string[], ordered = false, isComplete?: boolean): string {
        if (!items.length) {
            return '';
        }
        const tag = ordered ? 'ol' : 'ul';
        const renderedItems = items
            .map((item) => `<li>${this.renderInline(item)}</li>`)
            .join('');
        const classes = ['rich-list'];
        if (ordered) {
            classes.push('ordered');
        }
        if (!isComplete) {
            classes.push('streaming');
        }
        const classAttr = classes.join(' ');
        return `<${tag} class="${classAttr}">${renderedItems}</${tag}>`;
    }

    private renderTable(rows: string[][]): string {
        if (!rows.length) {
            return '';
        }
        const [header, ...body] = rows;
        const headerHtml = header
            .map((cell) => `<th>${this.renderInline(cell)}</th>`)
            .join('');
        const bodyHtml = body
            .map((row) => {
                const cells = row
                    .map((cell) => `<td>${this.renderInline(cell)}</td>`)
                    .join('');
                return `<tr>${cells}</tr>`;
            })
            .join('');
        return `<table class="rich-table"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
    }

    private renderQuote(content: string): string {
        const lines = content
            .split(/\n/)
            .map((line) => this.renderInline(line.trim()))
            .join('<br>');
        return `<blockquote>${lines}</blockquote>`;
    }

    private renderInline(text: string): string {
        if (!text) {
            return '';
        }
        let escaped = this.escapeHtml(text);
        escaped = escaped.replace(/`([^`]+)`/g, (_match, code) => `<code>${this.escapeHtml(code)}</code>`);
        escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/__(.+?)__/g, '<strong>$1</strong>');
        escaped = escaped.replace(/~~(.+?)~~/g, '<del>$1</del>');
        escaped = this.applyEmphasis(escaped, '*');
        escaped = this.applyEmphasis(escaped, '_');
        escaped = escaped.replace(
            /\[([^\]]+)\]\(([^)]+)\)/g,
            (_match, label, url) =>
                `<a href="${this.escapeHtml(url)}" target="_blank" class="markdown-link">${label}</a>`
        );
        escaped = escaped.replace(/\\([*_~])/g, '$1');
        return escaped;
    }

    private applyEmphasis(input: string, marker: '*' | '_'): string {
        const pattern =
            marker === '*'
                ? /(^|[\s>])\*(?!\*)([^*]+?)\*(?=[\s<]|$)/g
                : /(^|[\s>])_(?!_)([^_]+?)_(?=[\s<]|$)/g;
        const segments = input.split(/(<[^>]+>)/g);
        return segments
            .map((segment) => {
                if (segment.startsWith('<') && segment.endsWith('>')) {
                    return segment;
                }
                return segment.replace(
                    pattern,
                    (
                        match: string,
                        prefix: string,
                        inner: string,
                        offset: number,
                        original: string
                    ) => {
                        const start = offset + prefix.length;
                        const end = start + inner.length;
                        const prev = original[start - 1];
                        const next = original[end];
                        if (!inner.trim()) {
                            return match;
                        }
                        if ((prev && /[\w]/.test(prev)) || (next && /[\w]/.test(next))) {
                            return match;
                        }
                        return `${prefix}<em>${inner}</em>`;
                    }
                );
            })
            .join('');
    }
    private highlightCode(code: string, language?: string): string {
        const lang = (language || 'plaintext').toLowerCase();
        let source = code || '';

        if (lang === 'json') {
            try {
                const parsed = JSON.parse(code);
                source = JSON.stringify(parsed, null, 2);
            } catch {
                source = code;
            }
        }

        const tokens = this.tokenizeCode(source, lang);
        const html = tokens
            .map((token) => {
                const value = this.escapeHtml(token.value);
                switch (token.type) {
                    case 'keyword':
                        return `<span class="token keyword">${value}</span>`;
                    case 'string':
                        return `<span class="token string">${value}</span>`;
                    case 'number':
                        return `<span class="token number">${value}</span>`;
                    case 'boolean':
                        return `<span class="token boolean">${value}</span>`;
                    case 'comment':
                        return `<span class="token comment">${value}</span>`;
                    case 'operator':
                        return `<span class="token operator">${value}</span>`;
                    case 'punctuation':
                        return `<span class="token punctuation">${value}</span>`;
                    default:
                        return value;
                }
            })
            .join('');

        return `<code class="language-${lang}">${html}</code>`;
    }

    private tokenizeCode(code: string, language: string): CodeToken[] {
        const tokens: CodeToken[] = [];
        const length = code.length;
        let i = 0;

        const isIdentifierStart = (char: string) => /[A-Za-z_$]/.test(char);
        const isIdentifierPart = (char: string) => /[A-Za-z0-9_$]/.test(char);
        const isDigit = (char: string) => /[0-9]/.test(char);
        const isWhitespace = (char: string) => /\s/.test(char);

        while (i < length) {
            const char = code[i];
            const next = i + 1 < length ? code[i + 1] : '';

            // Strings
            if (char === '"' || char === "'" || char === '`') {
                const quote = char;
                let value = char;
                i++;
                while (i < length) {
                    const current = code[i];
                    value += current;
                    if (current === '\\' && i + 1 < length) {
                        value += code[i + 1];
                        i += 2;
                        continue;
                    }
                    if (current === quote) {
                        i++;
                        break;
                    }
                    i++;
                }
                tokens.push({ type: 'string', value });
                continue;
            }

            // Comments
            if (char === '/' && next === '/') {
                let value = char + next;
                i += 2;
                while (i < length && code[i] !== '\n') {
                    value += code[i];
                    i++;
                }
                tokens.push({ type: 'comment', value });
                continue;
            }
            if (char === '/' && next === '*') {
                let value = char + next;
                i += 2;
                while (i < length) {
                    const current = code[i];
                    value += current;
                    if (current === '*' && i + 1 < length && code[i + 1] === '/') {
                        value += '/';
                        i += 2;
                        break;
                    }
                    i++;
                }
                tokens.push({ type: 'comment', value });
                continue;
            }
            if (char === '#' && (language === 'python' || language === 'py' || language === 'shell' || language === 'bash' || language === 'sh')) {
                let value = char;
                i++;
                while (i < length && code[i] !== '\n') {
                    value += code[i];
                    i++;
                }
                tokens.push({ type: 'comment', value });
                continue;
            }

            // Numbers
            if (isDigit(char) || (char === '.' && isDigit(next))) {
                let value = char;
                i++;
                while (i < length && /[0-9a-fA-FxX._]/.test(code[i])) {
                    value += code[i];
                    i++;
                }
                tokens.push({ type: 'number', value });
                continue;
            }

            // Identifiers / keywords
            if (isIdentifierStart(char)) {
                let value = char;
                i++;
                while (i < length && isIdentifierPart(code[i])) {
                    value += code[i];
                    i++;
                }
                const type = this.classifyIdentifier(value, language);
                tokens.push({ type, value });
                continue;
            }

            // Whitespace
            if (isWhitespace(char)) {
                let value = char;
                i++;
                while (i < length && isWhitespace(code[i])) {
                    value += code[i];
                    i++;
                }
                tokens.push({ type: 'whitespace', value });
                continue;
            }

            // Operators / punctuation
            const punctuations = '(){}[],:;.';
            if (punctuations.includes(char)) {
                tokens.push({ type: 'punctuation', value: char });
                i++;
                continue;
            }

            let value = char;
            if ('+-*/%=!&|^<>~'.includes(char)) {
                if (next && '+=-|&<>'.includes(next)) {
                    value += next;
                    i += 2;
                    if (i < length && code[i] === '=') {
                        value += '=';
                        i++;
                    }
                } else {
                    i++;
                }
                tokens.push({ type: 'operator', value });
                continue;
            }

            tokens.push({ type: 'plain', value: char });
            i++;
        }

        return tokens;
    }

    private classifyIdentifier(identifier: string, language: string): CodeTokenType {
        if (!identifier) {
            return 'identifier';
        }
        if (identifier === 'true' || identifier === 'false' || identifier === 'null' || identifier === 'undefined' || identifier === 'None') {
            return 'boolean';
        }
        const lang = language.toLowerCase();
        let keywords = JS_KEYWORDS;
        if (lang === 'typescript' || lang === 'ts') {
            keywords = [...JS_KEYWORDS, ...TS_KEYWORDS];
        } else if (lang === 'python' || lang === 'py') {
            keywords = PY_KEYWORDS;
        }
        if (keywords.includes(identifier)) {
            return 'keyword';
        }
        return 'identifier';
    }

    private escapeHtml(value: string): string {
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}







