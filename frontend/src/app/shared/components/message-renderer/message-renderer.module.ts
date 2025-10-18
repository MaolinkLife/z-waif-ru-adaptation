// message-renderer.module.ts
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MessageRendererComponent } from './message-renderer.component';
import { MessageParserService } from './services/message-parser.service';

@NgModule({
    declarations: [
        MessageRendererComponent,
    ],
    imports: [
        CommonModule,
    ],
    exports: [
        MessageRendererComponent
    ],
    providers: [MessageParserService]
})
export class MessageRendererModule { }
