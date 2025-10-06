import { Component, Inject, OnInit } from '@angular/core';
import { catchError, map, startWith, finalize } from 'rxjs/operators';
import { Observable, of } from 'rxjs';
import { ResourcesService } from '../../../../core/services/resources.service';
import { ModalRef } from '../../../../shared/components/modal/modal-ref';

interface Monitor {
    index: number;
    width: number;
    height: number;
    left: number;
    top: number;
    preview: string;
}

interface MonitorResponse {
    status: string;
    monitors: Monitor[];
}

@Component({
    selector: 'app-monitor-selection-modal',
    templateUrl: './monitor-selection-modal.component.html',
    styleUrls: ['./monitor-selection-modal.component.less']
})
export class MonitorSelectionModalComponent implements OnInit {
    selectedMonitor: number = 0;
    error: string | null = null;
    debugInfo: string = 'Initial state';

    monitors$: Observable<Monitor[]> = of([]);

    constructor(
        @Inject('MODAL_DATA') public data: any,
        private modalRef: ModalRef,
        private resourcesService: ResourcesService
    ) {
        this.selectedMonitor = data?.selectedMonitor || 0;
        console.log('Modal data received:', this.data);
    }

    ngOnInit(): void {
        this.loadMonitorData();
    }

    private cleanBase64String(base64String: string): string {
        if (!base64String) return '';

        // Убираем data URL префикс если есть
        let cleanString = base64String.replace(/^data:image\/[a-z]+;base64,/, '');

        // Убираем пробелы и переносы строк
        cleanString = cleanString.replace(/\s/g, '');

        return cleanString;
    }

    private loadMonitorData(): void {
        console.log('Starting to load monitor data...');

        // Если данные уже переданы через data, используем их
        if (this.data?.monitors) {
            console.log('Using monitors data from modal input:', this.data.monitors);
            // Восстановим выбранный монитор из данных, если он есть
            this.selectedMonitor = this.data?.selectedMonitor || 0;
            const cleanedMonitors = this.data.monitors.map((monitor: any) => ({
                ...monitor,
                preview: this.cleanBase64String(monitor.preview)
            }));
            this.monitors$ = of(cleanedMonitors);
            this.debugInfo = `Loaded ${cleanedMonitors.length} monitors from input`;
            console.log('Final monitors array:', cleanedMonitors);
            return;
        }

        console.log('Calling getMonitorScreens$()...');

        // Загружаем данные с сервера
        this.monitors$ = this.resourcesService.getMonitorScreens$().pipe(
            map((response: MonitorResponse) => {
                console.log('Raw response from server:', response);

                if (response && response.monitors) {
                    const cleanedMonitors = response.monitors.map((monitor: any) => ({
                        ...monitor,
                        preview: this.cleanBase64String(monitor.preview)
                    }));
                    console.log('Processed monitors:', cleanedMonitors);
                    this.debugInfo = `Loaded ${cleanedMonitors.length} monitors from server`;
                    return cleanedMonitors;
                } else {
                    throw new Error('No monitor data received');
                }
            }),
            catchError(error => {
                console.error('Error loading monitor data from server:', error);
                this.error = 'Failed to load monitor information';
                this.debugInfo = 'Error loading data';
                return of([]);
            })
        );
    }

    trackByIndex(index: number, item: any): number {
        return index;
    }

    // Методы для обработки событий изображения
    onImageError(index: number, event: any): void {
        console.error(`Image load error for monitor ${index}`, event);
    }

    onImageLoad(index: number): void {
        console.log(`Image loaded successfully for monitor ${index}`);
    }

    selectMonitor(index: number): void {
        console.log(`Monitor ${index} selected`);
        this.selectedMonitor = index; // Сохраняем выбранный индекс

        // Вызываем callback если он передан
        if (this.data?.onSelect && typeof this.data.onSelect === 'function') {
            this.data.onSelect({ selectedMonitor: index });
        }

        // Закрываем модалку с результатом
        this.modalRef.closeModal({ selectedMonitor: index });
    }

    close(): void {
        console.log('Modal closed');
        this.modalRef.closeModal();
    }
}
