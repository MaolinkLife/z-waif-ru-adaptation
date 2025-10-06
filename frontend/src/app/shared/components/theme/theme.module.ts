import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeSelectorComponent } from './theme-selector/theme-selector.component';
import { FormsModule } from '@angular/forms';

@NgModule({
    declarations: [ThemeSelectorComponent],
    imports: [CommonModule, FormsModule],
    exports: [ThemeSelectorComponent]
})
export class ThemeModule { }
