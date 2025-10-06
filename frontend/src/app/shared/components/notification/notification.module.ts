import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NotificationContainerComponent } from './notification-container.component';

@NgModule({
    declarations: [NotificationContainerComponent],
    imports: [CommonModule],
    entryComponents: [NotificationContainerComponent]
})
export class NotificationModule { }
