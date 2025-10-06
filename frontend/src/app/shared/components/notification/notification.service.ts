import { Injectable, ApplicationRef, ComponentFactoryResolver, Injector, EmbeddedViewRef, ComponentRef, TemplateRef } from '@angular/core';
import { NotificationRef } from './notification-ref';
import { NotificationContainerComponent } from './notification-container.component';
import { NOTIFICATION_DATA } from './notification.tokens';

export interface NotificationOptions {
    message?: string;
    title?: string;
    type: 'success' | 'error' | 'warning' | 'info';
    duration?: number;
    template?: TemplateRef<any>;
    autoClose?: boolean;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
    private container: HTMLElement;

    constructor(
        private appRef: ApplicationRef,
        private cfr: ComponentFactoryResolver,
        private injector: Injector
    ) {
        this.container = this.createContainer();
    }

    open(options: NotificationOptions) {
        const notificationRef = new NotificationRef(() => this.destroy(componentRef));

        const injector = Injector.create({
            providers: [
                { provide: NOTIFICATION_DATA, useValue: options },
                { provide: NotificationRef, useValue: notificationRef }
            ],
            parent: this.injector
        });

        const factory = this.cfr.resolveComponentFactory(NotificationContainerComponent);
        const componentRef = factory.create(injector);

        this.appRef.attachView(componentRef.hostView);
        const domElem = (componentRef.hostView as EmbeddedViewRef<any>).rootNodes[0] as HTMLElement;

        this.container.appendChild(domElem);

        return notificationRef;
    }

    private destroy(componentRef: ComponentRef<any>) {
        this.appRef.detachView(componentRef.hostView);
        componentRef.destroy();
    }

    private createContainer(): HTMLElement {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }
}
