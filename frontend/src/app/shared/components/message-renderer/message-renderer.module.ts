// message-renderer.module.ts
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MessageRendererComponent } from './message-renderer.component';
import { MessageParserService } from './services/message-parser.service';
import { SimpleMarkdownPipe } from './pipes/simple-markdown.pipe';
import { MarkdownModule } from 'ngx-markdown';

@NgModule({
    declarations: [
        MessageRendererComponent,
        SimpleMarkdownPipe,
    ],
    imports: [
        CommonModule,
        MarkdownModule.forChild(),
    ],
    exports: [
        MessageRendererComponent
    ],
    providers: [
        MessageParserService
    ]
})
export class MessageRendererModule { }
