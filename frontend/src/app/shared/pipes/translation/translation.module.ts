import { NgModule, ModuleWithProviders } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';

import { TranslatePipe } from './translate.pipe';
import { LocalizationService } from './localization.service';

@NgModule({
    declarations: [TranslatePipe],
    imports: [CommonModule, HttpClientModule],
    exports: [TranslatePipe]
})
export class TranslationModule {
    static forRoot(): ModuleWithProviders<TranslationModule> {
        return {
            ngModule: TranslationModule,
            providers: [LocalizationService]
        };
    }
}
