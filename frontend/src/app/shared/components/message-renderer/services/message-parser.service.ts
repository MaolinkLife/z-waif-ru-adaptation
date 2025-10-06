// services/message-parser.service.ts
import { Injectable } from '@angular/core';

export interface MessageBlock {
    id: string;
    type: 'text' | 'code' | 'thinking' | 'list' | 'header';
    content: string;
    language?: string;
    isComplete?: boolean;
}

@Injectable({ providedIn: 'root' })
export class MessageParserService {
    private blockCounter = 0;
    private static readonly THINK_REGEX = /<think>([\s\S]*?)<\/think>/gi;

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
                    this.extractNonThinkingBlocks(beforeCode, blocks, true);
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

    processMarkdown(content: string): string {
        if (!content) return '';

        const parsed = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/__(.*?)__/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/_(.*?)_/g, '<em>$1</em>')
            .replace(/~~(.*?)~~/g, '<del>$1</del>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="markdown-link">$1</a>')
            .replace(/\n/g, '<br>');
        return parsed;
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
            this.extractNonThinkingBlocks(before, blocks, true);

            const reasoning = match[1].trim();
            if (reasoning) {
                blocks.push(this.createBlock('thinking', reasoning, true));
            }

            lastIndex = MessageParserService.THINK_REGEX.lastIndex;
        }

        const remainder = content.slice(lastIndex);
        this.extractNonThinkingBlocks(remainder, blocks, true);

        return blocks.length ? blocks : [this.createBlock('text', content.trim(), true)];
    }

    private extractNonThinkingBlocks(segment: string, blocks: MessageBlock[], isComplete: boolean): void {
        if (!segment || !segment.trim()) {
            return;
        }

        const codeRegex = /```(\w*)\n?([\s\S]*?)```/g;
        let lastIndex = 0;
        let match: RegExpExecArray | null;

        while ((match = codeRegex.exec(segment)) !== null) {
            if (match.index > lastIndex) {
                const textContent = segment.slice(lastIndex, match.index).trim();
                if (textContent) {
                    this.addTextBlocks(blocks, textContent, isComplete);
                }
            }

            blocks.push(this.createBlock('code', match[2].trim(), isComplete, match[1] || 'plaintext'));
            lastIndex = codeRegex.lastIndex;
        }

        if (lastIndex < segment.length) {
            const remainingText = segment.slice(lastIndex).trim();
            if (remainingText) {
                this.addTextBlocks(blocks, remainingText, isComplete);
            }
        }
    }

    private addTextBlocks(blocks: MessageBlock[], content: string, isComplete: boolean): void {
        if (!content) {
            return;
        }

        const lines = content.split('\n');
        let currentParagraph = '';

        for (const line of lines) {
            if (this.isHeader(line)) {
                if (currentParagraph.trim()) {
                    blocks.push({
                        id: `text-${this.blockCounter++}`,
                        type: 'text',
                        content: this.processMarkdown(currentParagraph.trim()),
                        isComplete
                    });
                    currentParagraph = '';
                }
                blocks.push({
                    id: `header-${this.blockCounter++}`,
                    type: 'header',
                    content: line.trim().replace(/^#+\s*/, ''),
                    isComplete
                });
            } else if (this.isListItem(line)) {
                if (currentParagraph.trim()) {
                    blocks.push({
                        id: `text-${this.blockCounter++}`,
                        type: 'text',
                        content: this.processMarkdown(currentParagraph.trim()),
                        isComplete
                    });
                    currentParagraph = '';
                }
                blocks.push({
                    id: `list-${this.blockCounter++}`,
                    type: 'list',
                    content: line.trim().replace(/^[\*\-\+]\s*/, ''),
                    isComplete
                });
            } else {
                currentParagraph += line + '\n';
            }
        }

        if (currentParagraph.trim()) {
            blocks.push({
                id: `text-${this.blockCounter++}`,
                type: 'text',
                content: this.processMarkdown(currentParagraph.trim()),
                isComplete
            });
        }
    }

    private isHeader(line: string): boolean {
        return /^#{1,6}\s+/.test(line.trim());
    }

    private isListItem(line: string): boolean {
        return /^[\*\-\+]\s+/.test(line.trim());
    }

    private createBlock(
        type: MessageBlock['type'],
        content: string,
        isComplete: boolean,
        language?: string
    ): MessageBlock {
        const trimmed = content.trim();
        const processedContent =
            type === 'text' || type === 'thinking'
                ? this.processMarkdown(trimmed)
                : trimmed;

        return {
            id: `${type}-${this.blockCounter++}`,
            type,
            content: processedContent,
            language,
            isComplete
        };
    }
}
