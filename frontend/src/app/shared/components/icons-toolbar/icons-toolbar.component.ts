import { Component, EventEmitter, Input, Output } from '@angular/core';
import { Message } from '../../../core/models/message.model';


@Component({
    selector: 'app-icons-toolbar',
    templateUrl: './icons-toolbar.component.html',
    styleUrls: ['./icons-toolbar.component.less']
})
export class IconsToolbarComponent {
    @Input() msg!: Message;
    @Input() index!: number;
    @Input() lastIndex!: number;

    @Output() deleteChange = new EventEmitter<{ msg: Message; chain: boolean }>();
    @Output() rerollChange = new EventEmitter<Message>();
    @Output() playVoiceChange = new EventEmitter<Message>();
}
