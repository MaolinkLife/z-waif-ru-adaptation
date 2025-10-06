import { EventEmitter } from '@angular/core';

export class NotificationRef {
    private _close = new EventEmitter<void>();

    readonly afterClosed$ = this._close.asObservable();

    constructor(private destroyFn: () => void) { }

    close() {
        this._close.emit();
        this.destroyFn();
    }
}
