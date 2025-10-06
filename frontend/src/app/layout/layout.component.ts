import { Component, OnInit } from '@angular/core';
import { ModalService } from '../shared/components/modal/modal.service';
import { MemoryModalComponent } from './components/modals/memory-modal/memory-modal.component';
import { MOCK_LOREBOOK } from '../shared/mock/lorebook-mock';
import { MainModalComponent } from './components/modals/main-modal/main-modal.component';
import { NotificationService } from '../shared/components/notification/notification.service';
import { ThemeService } from '../core/services/theme.service';

@Component({
    selector: 'app-layout',
    templateUrl: './layout.component.html',
    styleUrls: ['./layout.component.less']
})
export class LayoutComponent implements OnInit {
    currentTheme: 'dark' | 'light' = 'dark';

    constructor(
        private modalService: ModalService,
        private notificationService: NotificationService,
        private theme: ThemeService
    ) { }

    ngOnInit(): void {
        this.currentTheme = this.theme.getTheme();
        this.theme.initTheme();
    }

    toggleTheme() {
        this.theme.toggleTheme();
        this.currentTheme = this.theme.getTheme();
    }

    memoryClick() {
        this.modalService.open(MainModalComponent, {
            title: 'Settings',
            data: { entries: [] }
        }).afterClosed$.subscribe(updated => {
            console.log('Сохранено:', updated);
        });
    }

    openSettingsModal() {
        this.modalService.open(MainModalComponent, {
            title: 'Settings',
            data: { entries: [] }
        }).afterClosed$.subscribe(updated => {
            console.log('Сохранено:', updated);
        });
    }
}
