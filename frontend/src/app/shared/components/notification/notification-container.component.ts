import { Component, Inject, OnInit, OnDestroy, TemplateRef } from '@angular/core';
import { NotificationRef } from './notification-ref';
import { NOTIFICATION_DATA } from './notification.tokens';
import { trigger, state, style, transition, animate } from '@angular/animations';

export interface NotificationData {
    message?: string;
    title?: string;
    type: 'success' | 'error' | 'warning' | 'info';
    duration?: number;
    template?: TemplateRef<any>;
    autoClose?: boolean;
}

@Component({
    selector: 'app-notification-container',
    templateUrl: './notification-container.component.html',
    styleUrls: ['./notification-container.component.less'],
    animations: [
        trigger('slideIn', [
            state('void', style({ transform: 'translateX(100%)', opacity: 0 })),
            transition(':enter', [
                animate('300ms ease-out', style({ transform: 'translateX(0)', opacity: 1 }))
            ])
        ]),
        trigger('fadeOut', [
            transition(':leave', [
                animate('300ms ease-in', style({ transform: 'translateX(100%)', opacity: 0 }))
            ])
        ])
    ]
})
export class NotificationContainerComponent implements OnInit, OnDestroy {
    constructor(
        @Inject(NOTIFICATION_DATA) public data: NotificationData,
        public notificationRef: NotificationRef
    ) { }

    ngOnInit() {
        if (this.data.autoClose !== false) {
            const duration = this.data.duration || 2000; // По умолчанию 2 сек
            setTimeout(() => this.notificationRef.close(), duration);
        }
    }

    close() {
        this.notificationRef.close();
    }

    ngOnDestroy() { }
}
