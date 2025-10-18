// services/message-parser.service.ts
import { Injectable } from '@angular/core';

export interface MessageBlock {
    id: string;
    type:
        | 'text'
        | 'code'
        | 'thinking'
        | 'list'
        | 'header'
        | 'table'
        | 'quote';
    content: string;
    language?: string;
    isComplete?: boolean;
    items?: string[];
    ordered?: boolean;
    rows?: string[][];
}

@Injectable({ providedIn: 'root' })
export class MessageParserService {
    private blockCounter = 0;
    private static readonly THINK_REGEX = /<think>([\s\S]*?)<\/think>/gi;
    private static readonly TABLE_DIVIDER_REGEX =
        /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$/;

    parseStreaming(partialContent: string): MessageBlock[] {
        if (!partialContent) {
            return [];
        }

        const lower = partialContent.toLowerCase();
        const lastThinkOpen = lower.lastIndexOf('<think>');
        const lastThinkClose = lower.lastIndexOf('</think>');

        if (lastThinkOpen !== -1 && (lastThinkClose === -1 || lastThinkClose < lastThinkOpen)) {
            const reasoningText = partialContent
                .slice(lastThinkOpen + '<think>'.length)
                .replace(/<[^>]*$/g, '')
                .trim();

            return [
                this.createBlock(
                    'thinking',
                    reasoningText || 'Думаю...',
                    false
                )
            ];
        }

        if (lower.includes('</think>')) {
            return this.parseComplete(partialContent);
        }

        const codeBlockStart = partialContent.lastIndexOf('```');
        if (codeBlockStart !== -1 && partialContent.substring(codeBlockStart).includes('\n')) {
            const afterStart = partialContent.substring(codeBlockStart + 3);
            const hasEnd = afterStart.includes('```');

            if (!hasEnd) {
                const blocks: MessageBlock[] = [];
                const beforeCode = partialContent.substring(0, codeBlockStart).trim();
                const codeContent = partialContent.substring(codeBlockStart);

                if (beforeCode) {
                    this.extractStructuredBlocks(beforeCode, blocks, true);
                }

                const lines = codeContent.split('\n');
                const language = lines.length > 1 ? lines[0].substring(3).trim() : 'plaintext';
                const codeBody = lines.slice(1).join('\n');

                blocks.push(this.createBlock('code', codeBody, false, language));
                return blocks;
            }
        }

        return this.parseComplete(partialContent);
    }

    parseComplete(content: string): MessageBlock[] {
        const blocks: MessageBlock[] = [];
        if (!content) {
            return blocks;
        }

        let lastIndex = 0;
        MessageParserService.THINK_REGEX.lastIndex = 0;
        let match: RegExpExecArray | null;

        while ((match = MessageParserService.THINK_REGEX.exec(content)) !== null) {
            const before = content.slice(lastIndex, match.index);
            this.extractStructuredBlocks(before, blocks, true);

            const reasoning = match[1].trim();
            if (reasoning) {
                blocks.push(this.createBlock('thinking', reasoning, true));
            }

            lastIndex = MessageParserService.THINK_REGEX.lastIndex;
        }

        const remainder = content.slice(lastIndex);
        this.extractStructuredBlocks(remainder, blocks, true);

        return blocks.length ? blocks : [this.createBlock('text', content.trim(), true)];
    }

    private isHeader(line: string): boolean {
        return /^#{1,6}\s+/.test(line.trim());
    }

    private isUnorderedList(line: string): boolean {
        return /^\s*[\*\-\+]\s+/.test(line);
    }

    private isOrderedList(line: string): boolean {
        return /^\s*\d+[\.\)]\s+/.test(line);
    }

    private isBlockquote(line: string): boolean {
        return /^\s*>+\s*/.test(line);
    }

    private isTableRow(line: string): boolean {
        return /\|/.test(line);
    }

    private extractStructuredBlocks(segment: string, blocks: MessageBlock[], isComplete: boolean): void {
        if (!segment || !segment.trim()) {
            return;
        }

        const codeRegex = /```(\w*)\n?([\s\S]*?)```/g;
        let lastIndex = 0;
        let match: RegExpExecArray | null;

        while ((match = codeRegex.exec(segment)) !== null) {
            if (match.index > lastIndex) {
                const textContent = segment.slice(lastIndex, match.index);
                this.splitRichTextBlocks(textContent, blocks, isComplete);
            }

            blocks.push(
                this.createBlock(
                    'code',
                    match[2],
                    isComplete,
                    match[1] ? match[1].trim() : 'plaintext'
                )
            );
            lastIndex = codeRegex.lastIndex;
        }

        if (lastIndex < segment.length) {
            const remainingText = segment.slice(lastIndex);
            this.splitRichTextBlocks(remainingText, blocks, isComplete);
        }
    }

    private splitRichTextBlocks(content: string, blocks: MessageBlock[], isComplete: boolean): void {
        const lines = content.split(/\r?\n/);
        const paragraphBuffer: string[] = [];

        const flushParagraph = () => {
            if (paragraphBuffer.length === 0) {
                return;
            }
            const paragraph = paragraphBuffer.join('\n').trim();
            if (paragraph) {
                blocks.push(this.createBlock('text', paragraph, isComplete));
            }
            paragraphBuffer.length = 0;
        };

        let i = 0;
        while (i < lines.length) {
            const line = lines[i];
            const trimmed = line.trim();
            if (!trimmed) {
                flushParagraph();
                i++;
                continue;
            }

            // Table detection
            if (
                this.isTableRow(line) &&
                i + 1 < lines.length &&
                MessageParserService.TABLE_DIVIDER_REGEX.test(lines[i + 1].trim())
            ) {
                flushParagraph();
                const headerLine = lines[i];
                const tableRows: string[][] = [this.parseTableRow(headerLine)];
                i += 2;
                while (i < lines.length && this.isTableRow(lines[i])) {
                    tableRows.push(this.parseTableRow(lines[i]));
                    i++;
                }
                blocks.push(
                    this.createBlock('table', '', isComplete, undefined, {
                        rows: tableRows,
                    })
                );
                continue;
            }

            // Heading
            if (this.isHeader(line)) {
                flushParagraph();
                blocks.push(
                    this.createBlock('header', line.trim().replace(/^#{1,6}\s*/, ''), isComplete)
                );
                i++;
                continue;
            }

            // List
            if (this.isUnorderedList(line) || this.isOrderedList(line)) {
                const ordered = this.isOrderedList(line);
                flushParagraph();
                const items: string[] = [];
                while (
                    i < lines.length &&
                    ((ordered && this.isOrderedList(lines[i])) ||
                        (!ordered && this.isUnorderedList(lines[i])))
                ) {
                    const item = ordered
                        ? lines[i].replace(/^\s*\d+[\.\)]\s+/, '')
                        : lines[i].replace(/^\s*[\*\-\+]\s+/, '');
                    items.push(item.trim());
                    i++;
                }
                blocks.push(
                    this.createBlock('list', '', isComplete, undefined, {
                        items,
                        ordered,
                    })
                );
                continue;
            }

            // Blockquote
            if (this.isBlockquote(line)) {
                flushParagraph();
                const parts: string[] = [];
                while (i < lines.length && this.isBlockquote(lines[i])) {
                    parts.push(lines[i].replace(/^\s*>+\s?/, ''));
                    i++;
                }
                blocks.push(
                    this.createBlock('quote', parts.join('\n').trim(), isComplete)
                );
                continue;
            }

            paragraphBuffer.push(line);
            i++;
        }
        flushParagraph();
    }

    private parseTableRow(line: string): string[] {
        const cleaned = line.trim().replace(/^\|/, '').replace(/\|$/, '');
        return cleaned.split('|').map((cell) => cell.trim());
    }

    private createBlock(
        type: MessageBlock['type'],
        content: string,
        isComplete: boolean,
        language?: string,
        extras: Partial<MessageBlock> = {}
    ): MessageBlock {
        return {
            id: `${type}-${this.blockCounter++}`,
            type,
            content: content,
            language,
            isComplete,
            ...extras,
        };
    }
}

