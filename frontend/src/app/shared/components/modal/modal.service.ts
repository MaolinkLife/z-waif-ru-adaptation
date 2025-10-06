import {
    ApplicationRef,
    ComponentFactoryResolver,
    ComponentRef,
    Injectable,
    Injector,
    Type,
    EmbeddedViewRef
} from '@angular/core';
import { ModalRef } from './modal-ref';
import { ModalContainerComponent } from './modal-container.component';

@Injectable({ providedIn: 'root' })
export class ModalService {
    constructor(
        private appRef: ApplicationRef,
        private cfr: ComponentFactoryResolver,
        private injector: Injector
    ) { }

    open<T>(component: Type<T>, options: { data?: any, title?: string } = {}): ModalRef {
        const modalRef = new ModalRef(() => this.destroy(modalComponentRef));

        const injector = Injector.create({
            providers: [
                { provide: 'MODAL_DATA', useValue: { ...options, component } },
                { provide: ModalRef, useValue: modalRef }
            ],
            parent: this.injector
        });

        const factory = this.cfr.resolveComponentFactory(ModalContainerComponent);
        const modalComponentRef = factory.create(injector);

        this.appRef.attachView(modalComponentRef.hostView);
        const domElem = (modalComponentRef.hostView as EmbeddedViewRef<any>).rootNodes[0] as HTMLElement;

        const hostElem = document.getElementById('modal-host');
        hostElem?.appendChild(domElem);
        modalRef.notifyOpen();

        return modalRef;
    }


    private destroy(componentRef: ComponentRef<any>) {
        this.appRef.detachView(componentRef.hostView);
        componentRef.destroy();
    }
}
