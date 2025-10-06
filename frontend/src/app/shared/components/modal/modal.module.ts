import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModalWrapperComponent } from './modal-wrapper.component';
import { ModalService } from './modal.service';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';

@NgModule({
    declarations: [ModalWrapperComponent],
    imports: [CommonModule, FormsModule, ReactiveFormsModule],
    exports: [ModalWrapperComponent],
    providers: [ModalService],
})
export class ModalModule { }
