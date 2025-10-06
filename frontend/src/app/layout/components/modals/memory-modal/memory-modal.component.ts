import { Component, Inject, Output, EventEmitter, ChangeDetectionStrategy, OnInit } from '@angular/core';
import { ModalRef } from '../../../../shared/components/modal/modal-ref';
import { LorebookEntry } from '../../../../core/models/lorebook-entry.model';
import { BehaviorSubject } from 'rxjs';
import { MOCK_LOREBOOK } from '../../../../shared/mock/lorebook-mock';

@Component({
    selector: 'app-memory-modal',
    templateUrl: './memory-modal.component.html',
    styleUrls: ['./memory-modal.component.less'],
    changeDetection: ChangeDetectionStrategy.Default
})
export class MemoryModalComponent implements OnInit {
    entries: LorebookEntry[] = [];
    modalRef: ModalRef;

    mock = MOCK_LOREBOOK;

    entries$: BehaviorSubject<LorebookEntry[]> = new BehaviorSubject<LorebookEntry[]>([]);

    constructor(@Inject('MODAL_DATA') public data: any, private _modalRef: ModalRef) {
        const content = data.data;
        this.entries = [...content.entries ? content.entries : []];
        this.modalRef = _modalRef;
        this.entries$.next(this.entries);
    }

    ngOnInit() {
        const entries: LorebookEntry[] = [...MOCK_LOREBOOK];
        this.entries$.next(entries);
    }


    save() {
        this.modalRef.closeModal({ saved: true });
    }

    close() {
        this.modalRef.closeModal({ closed: true });
    }
}
