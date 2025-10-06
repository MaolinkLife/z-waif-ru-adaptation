import { Component, OnInit } from '@angular/core';
import { LoggerService } from '../../core/services/logger.service';
import { trigger, state, style, transition, animate } from '@angular/animations';

const TAG_RE = /\[([^\]]+)\]/g;

@Component({
    selector: 'app-debug',
    templateUrl: './debug.component.html',
    styleUrls: ['./debug.component.less'],
    animations: [
        trigger('expandCollapse', [
            state('closed', style({ height: '0px', opacity: 0, overflow: 'hidden' })),
            state('open', style({ height: '*', opacity: 1 })),
            transition('closed <=> open', [animate('200ms ease-in-out')]),
        ]),
    ],
})
export class DebugComponent implements OnInit {
    logs: any[] = [];
    filteredLogs: any[] = [];

    expandedLogs: Set<number> = new Set();

    // Фильтры по источникам (квадратные теги)
    availableSources: string[] = [];
    activeSources: string[] = [];

    // Фильтры по статусам
    availableStatuses: string[] = [];
    activeStatuses: string[] = [];

    constructor(private loggerService: LoggerService) { }

    ngOnInit(): void {
        this.loggerService.getDebugLog$().subscribe((logs) => {
            // сортируем по времени
            const sorted = (logs || []).sort(
                (a: any, b: any) =>
                    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
            );

            // обогащаем логи: вытаскиваем теги [ ... ] и нормализуем статус
            this.logs = sorted.map((l: any) => this.enrichLog(l));

            // источники = уникальные квадратные теги
            this.availableSources = Array.from(
                new Set<string>(
                    ([] as string[]).concat(...this.logs.map((l: any) => l.tags || []))
                )
            ).sort();

            // статусы = уникальные нормализованные статусы
            this.availableStatuses = Array.from(
                new Set(this.logs.map((l) => l.statusLabel).filter(Boolean))
            ).sort();

            this.applyFilters();
        });
    }

    private enrichLog(log: any) {
        const tags = this.extractTags(log);
        const statusLabel = this.getStatusLabel(log);
        return { ...log, tags, statusLabel };
    }

    private extractTags(log: any): string[] {
        // Ищем все [Tag] в строковых полях
        const fields: (string | undefined)[] = [
            log.msg,
            log.details?.msg,
            log.details?.error,
            log.details?.status,
            log.details?.context,
            log.event_type,
            log.meta?.source,
        ].filter((v): v is string => typeof v === 'string');

        const collected: string[] = [];
        for (const txt of fields) {
            const safeTxt = txt || "";
            let m: RegExpExecArray | null;
            while ((m = TAG_RE.exec(safeTxt)) !== null) {
                const tag = m[1].trim();
                if (tag) collected.push(tag);
            }
        }

        // Фолбэк: если квадратных тегов нет — можно подхватить префикс до двоеточия вида "[Vision] ...".
        // (Если логи иногда идут как "[Vision] xxx", но вдруг regex не сработал)
        // Если вообще пусто — добавим event_type как последний фолбэк, чтобы лог не терялся при фильтрации.
        if (collected.length === 0) {
            if (typeof log.event_type === 'string' && log.event_type.trim()) {
                collected.push(log.event_type.trim());
            } else if (typeof log.meta?.source === 'string' && log.meta.source.trim()) {
                collected.push(log.meta.source.trim());
            }
        }

        return Array.from(new Set(collected));
    }

    private getStatusLabel(log: any): string {
        // нормализация статуса
        const raw =
            log.status ||
            log.details?.status ||
            log.meta?.severity ||
            (typeof log.event_type === 'string' &&
                log.event_type.toLowerCase().includes('error')
                ? 'Error'
                : '');

        const s = String(raw || '').toLowerCase();
        if (!s) return 'Info';
        if (s.includes('error')) return 'Error';
        if (s.includes('success') || s === 'ok') return 'Success';
        if (s.includes('warn')) return 'Warning';
        if (s.includes('debug')) return 'Debug';
        if (s.includes('info')) return 'Info';
        return raw || 'Info';
    }

    // Проверяем, есть ли у лога значимые детали
    hasDetails(log: any): boolean {
        if (!log.details) return false;

        // Проверяем, не пустой ли объект
        if (typeof log.details === 'object' && Object.keys(log.details).length === 0) {
            return false;
        }

        // Проверяем, не равен ли details пустому объекту
        if (JSON.stringify(log.details) === '{}') {
            return false;
        }

        return true;
    }

    toggleDetails(index: number): void {
        if (this.expandedLogs.has(index)) this.expandedLogs.delete(index);
        else this.expandedLogs.add(index);
    }

    getLogClass(log: any): string {
        switch (log.statusLabel) {
            case 'Error':
                return 'error';
            case 'Success':
                return 'success';
            case 'Warning':
                return 'warning';
            case 'Debug':
                return 'debug';
            default:
                return 'audit';
        }
    }

    // ——— Фильтрация ———
    applyFilters(): void {
        let data = this.logs;

        if (this.activeSources.length > 0) {
            data = data.filter((log) =>
                (log.tags || []).some((t: string) => this.activeSources.includes(t))
            );
        }

        if (this.activeStatuses.length > 0) {
            data = data.filter((log) => this.activeStatuses.includes(log.statusLabel));
        }

        this.filteredLogs = data;
    }

    // источники
    toggleSource(source: string): void {
        if (this.activeSources.includes(source)) {
            this.activeSources = this.activeSources.filter((s) => s !== source);
        } else {
            this.activeSources = [...this.activeSources, source];
        }
        this.applyFilters();
    }
    removeSource(event: MouseEvent, source: string): void {
        event.stopPropagation();
        this.activeSources = this.activeSources.filter((s) => s !== source);
        this.applyFilters();
    }

    // статусы
    toggleStatus(status: string): void {
        if (this.activeStatuses.includes(status)) {
            this.activeStatuses = this.activeStatuses.filter((s) => s !== status);
        } else {
            this.activeStatuses = [...this.activeStatuses, status];
        }
        this.applyFilters();
    }
    removeStatus(event: MouseEvent, status: string): void {
        event.stopPropagation();
        this.activeStatuses = this.activeStatuses.filter((s) => s !== status);
        this.applyFilters();
    }
}
