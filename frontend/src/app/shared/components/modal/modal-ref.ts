import { EventEmitter } from '@angular/core';

export class ModalRef<T = any> {
    private _open = new EventEmitter<void>();
    private _close = new EventEmitter<T>();

    /** Emits when modal is fully created and attached to DOM */
    readonly opened$ = this._open.asObservable();

    /** Emits when modal is closed with optional result */
    readonly afterClosed$ = this._close.asObservable();

    constructor(private destroyFn: () => void) { }

    /** Internal: Called by service when modal is rendered */
    notifyOpen() {
        this._open.emit();
    }

    closeModal(result?: T) {
        this._close.emit(result);
        this.destroyFn();
    }
}
