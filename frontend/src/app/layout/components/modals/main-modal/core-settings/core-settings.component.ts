import { Component } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

@Component({
    selector: 'app-core-settings',
    templateUrl: './core-settings.component.html',
    styleUrls: ['./core-settings.component.less']
})
export class CoreSettingsComponent {
    showDlModal = false;
    dlForm: FormGroup;

    constructor(
        private fb: FormBuilder,
        private localizationService: LocalizationService
    ) {
        this.dlForm = this.fb.group({});
        this.localizationService.init();
    }

    openDlModal(): void {
        this.showDlModal = true;
    }

    closeDlModal(): void {
        this.showDlModal = false;
    }
}
