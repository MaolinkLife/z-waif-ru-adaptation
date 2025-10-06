import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { ChatRoutingModule } from './chat-routing.module';
import { ChatComponent } from './chat.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { ApiService } from '../../core/services/api.service';
import { ConfigService } from '../../core/services/config.service';
import { MarkdownModule } from 'ngx-markdown';
import { SharedModule } from '../../shared/shared.module';


@NgModule({
    declarations: [
        ChatComponent
    ],
    imports: [
        CommonModule,
        ChatRoutingModule,
        FormsModule,
        ReactiveFormsModule,
        HttpClientModule,
        MarkdownModule.forChild(),
        SharedModule,
    ],
    providers: [
        ApiService,
        ConfigService,
    ]
})
export class ChatModule { }
