import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NgModule } from '@angular/core';

import { EmojiPickerComponent } from './emoji-picker.component';

@NgModule({
    declarations: [EmojiPickerComponent],
    imports: [CommonModule, FormsModule],
    exports: [EmojiPickerComponent]
})
export class EmojiModule {}
