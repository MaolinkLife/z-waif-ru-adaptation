import { ChangeDetectorRef, Pipe, PipeTransform } from '@angular/core';
import { LocalizationService } from './localization.service';
import { Subscription } from 'rxjs';

@Pipe({
    name: 'translate',
    pure: false
})
export class TranslatePipe implements PipeTransform {
    private lastKey = '';
    private lastValue = '';
    private sub: Subscription;

    constructor(
        private loc: LocalizationService,
        private cd: ChangeDetectorRef
    ) {
        this.sub = this.loc.getTranslationUpdates().subscribe(() => {
            this.lastValue = this.loc.t(this.lastKey);
            this.cd.markForCheck();
        });
    }

    transform(key: string): string {
        if (key !== this.lastKey) {
            this.lastKey = key;
            this.lastValue = this.loc.t(key);
        }
        return this.lastValue;
    }

    ngOnDestroy(): void {
        this.sub.unsubscribe();
    }
}
