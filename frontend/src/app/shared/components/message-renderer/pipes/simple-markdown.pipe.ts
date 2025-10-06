// pipes/simple-markdown.pipe.ts - улучшенная версия
import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
    name: 'simpleMarkdown'
})
export class SimpleMarkdownPipe implements PipeTransform {
    transform(value: string): string {
        if (!value) return '';

        // Экранируем HTML сначала для безопасности
        let safeValue = this.escapeHtml(value);

        return safeValue
            // Жирный текст
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/__(.*?)__/g, '<strong>$1</strong>')

            // Курсив
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/_(.*?)_/g, '<em>$1</em>')

            // Зачеркнутый
            .replace(/~~(.*?)~~/g, '<del>$1</del>')

            // Inline код
            .replace(/`(.*?)`/g, '<code>$1</code>')

            // Ссылки
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="markdown-link">$1</a>')

            // Переносы строк (только двойные)
            .replace(/\n\n/g, '</p><p>')
            .replace(/^(.*)$/, '<p>$1</p>') // Оборачиваем в параграфы
            .replace(/<p><\/p>/g, ''); // Убираем пустые параграфы
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
