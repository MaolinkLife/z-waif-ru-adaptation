// main-modal.component.ts
import { Component, Inject, OnInit } from '@angular/core';
import { ModalRef } from '../../../../shared/components/modal/modal-ref';

@Component({
    selector: 'app-main-modal',
    templateUrl: './main-modal.component.html',
    styleUrls: ['./main-modal.component.less']
})
export class MainModalComponent implements OnInit {
    modalRef: ModalRef;

    tabs = [
        { key: 'lorebook', label: 'Lorebook' },
        { key: 'voice', label: 'Voice' },
        { key: 'audio', label: 'Audio' },
        { key: 'vision', label: 'Vision' },
        { key: 'rag', label: 'RAG' },
        { key: 'analyzer', label: 'Analyzer' },
        { key: 'moral', label: 'Moral Matrix' },
        { key: 'generate', label: 'Generation' },
        { key: 'core', label: 'Core' },
        { key: 'system', label: 'System' }
    ];

    activeView = 'lorebook';

    constructor(@Inject('MODAL_DATA') public data: any, private _modalRef: ModalRef) {
        this.modalRef = _modalRef;
    }

    ngOnInit(): void {
        console.log({ action: 'MainModalComponent ngOnInit' });
    }

    selectView(view: string): void {
        this.activeView = view;
    }

    close(): void {
        this.modalRef.closeModal({ closed: true });
    }
}
