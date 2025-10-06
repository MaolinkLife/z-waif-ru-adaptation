import { CommonModule } from '@angular/common';
import { NgModule } from '@angular/core';
import { ThemeModule } from './components/theme/theme.module';
import { IconsToolbarModule } from './components/icons-toolbar/icons-toolbar.module';
import { TranslationModule } from './pipes/translation/translation.module';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { ModalModule } from './components/modal/modal.module';
import { MessageRendererModule } from './components/message-renderer/message-renderer.module';
import { EmojiModule } from './emoji/emoji.module';
import { SkeletonModule } from './components/skeleton/skeleton.module';
import { NotificationModule } from './components/notification/notification.module';

@NgModule({
    imports: [
        CommonModule,
        ThemeModule,
        IconsToolbarModule,
        TranslationModule.forRoot(),
        FormsModule,
        ReactiveFormsModule,
        ModalModule,
        MessageRendererModule,
        EmojiModule,
        SkeletonModule,
        NotificationModule,
    ],
    exports: [
        ThemeModule,
        IconsToolbarModule,
        TranslationModule,
        FormsModule,
        ReactiveFormsModule,
        ModalModule,
        MessageRendererModule,
        EmojiModule,
        SkeletonModule,
        NotificationModule,
    ]
})
export class SharedModule { }
