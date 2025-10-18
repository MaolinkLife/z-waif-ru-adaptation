import { Component, ElementRef, HostListener, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { Observable } from 'rxjs';
import { finalize, map } from 'rxjs/operators';
import { Message, MessageMedia, MessageMediaCategory } from '../../core/models/message.model';
import { ProjectConfig } from './../../core/models/project-config.model';
import { ApiService } from '../../core/services/api.service';
import { ConfigService } from '../../core/services/config.service';
import { VoiceModeResponse, VoiceService } from '../../core/services/voice.service';
import { WebsocketService } from '../../core/services/websocket.service';
import { NotificationService } from '../../shared/components/notification/notification.service';

function generateTempId(): string {
    if ((crypto as any).randomUUID) {
        return (crypto as any).randomUUID();
    }
    return 'temp-' + Math.random().toString(36).substr(2, 9);
}

const DEFAULT_MIME_TYPE = 'application/octet-stream';
const DOCUMENT_EXTENSIONS = new Set(['pdf', 'doc', 'docx', 'txt', 'rtf', 'xls', 'xlsx', 'csv', 'ppt', 'pptx']);

@Component({
    selector: 'app-chat',
    templateUrl: './chat.component.html',
    styleUrls: ['./chat.component.less']
})
export class ChatComponent implements OnInit, OnDestroy {
    @HostListener('document:click', ['$event'])
    onClickOutside(): void {
        this.activeDropdown = null;
        this.showEmojiPicker = false;
    }

    // Pagination properties
    hasMoreMessages = true;
    isLoadingHistory = false;
    currentOffset = 0;
    readonly MESSAGES_PER_PAGE = 32;

    showEmojiPicker = false;
    emojiDropdownPosition: { x: number; y: number } = { x: 0, y: 0 };
    emojiPickerMode: 'dropdown' | 'side-panel' = 'side-panel';
    emojiPickerSide: 'left' | 'right' | 'top' | 'bottom' = 'right';
    readonly emojiPanelWidth = 360;
    readonly emojiPanelHeight = 360;
    chatInput = new FormControl('');
    chatHistory: Message[] = [];
    loading = false;
    chatInputValue: string = '';
    userName: string = '';
    charName: string = '';
    attachments: MessageMedia[] = [];
    selectedMedia: MessageMedia | null = null;
    isProcessingAttachments = false;

    config$: Observable<{ userName: string; charName: string } | null> | null = null;

    recording = false;
    voiceModeEnabled = false;
    voiceModeLoading = false;
    activeDropdown: string | null = null;
    currentPlayingMessage: string | null = null;
    private currentStreamingMessage: Message | null = null;
    @ViewChild('fileInput') private fileInputRef?: ElementRef<HTMLInputElement>;

    constructor(
        private apiService: ApiService,
        private configService: ConfigService,
        private voiceService: VoiceService,
        private websocketService: WebsocketService,
        private notificationService: NotificationService
    ) { }

    ngOnInit(): void {
        this.getSettings();
        this.loadHistory();
        this.fetchVoiceModeStatus();

        this.websocketService.messages$.subscribe((rawMsg: string) => {
            let event: any;
            try {
                event = JSON.parse(rawMsg);
            } catch {
                console.warn('[WS] ⚠️ Received non-JSON message:', rawMsg);
                this.isLoadingHistory = false;
                return;
            }

            switch (event.type) {
                case 'message_chunk':
                    if (!this.currentStreamingMessage) {
                        this.loading = false;
                        const tempId = generateTempId();
                        this.currentStreamingMessage = {
                            id: tempId,
                            role: event.role,
                            content: event.content,
                            timestamp: new Date().toISOString(),
                            isPending: true,
                            media: this.normalizeMediaList(event.media),
                        };
                        this.chatHistory.push(this.currentStreamingMessage);
                    } else {
                        this.currentStreamingMessage.content += event.content;
                        if (event.media !== undefined && this.currentStreamingMessage) {
                            this.currentStreamingMessage.media = this.normalizeMediaList(event.media);
                        }
                    }
                    break;

                case 'message': {
                    const normalizedMedia = this.normalizeMediaList(event.media);
                    if (this.currentStreamingMessage) {
                        this.currentStreamingMessage.id = event.id || this.currentStreamingMessage.id;
                        this.currentStreamingMessage.isPending = false;
                        this.currentStreamingMessage.content = event.content;
                        if (event.timestamp) {
                            this.currentStreamingMessage.timestamp = event.timestamp;
                        }
                        if (event.media !== undefined) {
                            this.currentStreamingMessage.media = normalizedMedia;
                        }
                        this.currentStreamingMessage = null;
                    } else if (event.role === 'user') {
                        const messageIndex = this.chatHistory.findIndex(m => m.id === event.id);
                        if (messageIndex !== -1) {
                            const existingMessage = this.chatHistory[messageIndex];
                            existingMessage.role = event.role;
                            existingMessage.content = event.content;
                            existingMessage.isPending = false;
                            existingMessage.timestamp = event.timestamp || existingMessage.timestamp || new Date().toISOString();
                            existingMessage.media = normalizedMedia;
                        } else {
                            this.chatHistory.push({
                                id: event.id,
                                role: event.role,
                                content: event.content,
                                timestamp: event.timestamp || new Date().toISOString(),
                                isPending: false,
                                media: normalizedMedia,
                            });
                        }
                    } else {
                        this.chatHistory.push({
                            id: event.id,
                            role: event.role,
                            content: event.content,
                            timestamp: event.timestamp || new Date().toISOString(),
                            isPending: false,
                            media: normalizedMedia,
                        });
                    }
                    this.loading = false;
                    break;
                }

                case 'history':
                    const newMessages = event.items.map((m: any) => ({
                        ...m,
                        isPending: false,
                        media: this.normalizeMediaList(m.media),
                    })).sort(
                        (a: any, b: any) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
                    );

                    if (this.isLoadingHistory) {
                        // Append older messages to the beginning
                        this.chatHistory = [...newMessages, ...this.chatHistory];
                        this.currentOffset += newMessages.length;
                        this.hasMoreMessages = newMessages.length === this.MESSAGES_PER_PAGE;
                        this.isLoadingHistory = false;
                    } else {
                        // Initial load
                        this.chatHistory = newMessages;
                        this.currentOffset = newMessages.length;
                        this.hasMoreMessages = newMessages.length === this.MESSAGES_PER_PAGE;
                    }
                    break;

                case 'deleted':
                    if (event.chain) {
                        const deletedMsgIndex = this.chatHistory.findIndex(m => m.id === event.message_id);
                        if (deletedMsgIndex !== -1) {
                            const deletedMsg = this.chatHistory[deletedMsgIndex];
                            this.chatHistory.splice(deletedMsgIndex, 1);

                            if (deletedMsg.role === 'user') {
                                for (let i = deletedMsgIndex; i < this.chatHistory.length; i++) {
                                    if (this.chatHistory[i].role === 'assistant') {
                                        this.chatHistory.splice(i, 1);
                                        break;
                                    }
                                }
                            }
                        }
                    } else {
                        this.chatHistory = this.chatHistory.filter(m => m.id !== event.message_id);
                    }
                    break;

                case 'reroll':
                    this.chatHistory.push({
                        id: event.new_message.id,
                        role: event.new_message.role,
                        content: event.new_message.content,
                        timestamp: event.new_message.timestamp,
                        isPending: false,
                        media: this.normalizeMediaList(event.new_message?.media),
                    });
                    this.loading = false;
                    setTimeout(() => this.scrollToBottom(), 0);
                    break;

                case 'system':
                    if (event.event === 'typing_start') {
                        this.loading = true;
                    } else if (event.event === 'typing_end') {
                        this.loading = false;
                        this.currentStreamingMessage = null;
                    }
                    break;

                case 'message_end': {
                    const targetId = event.id || this.currentStreamingMessage?.id;
                    if (targetId) {
                        const messageIndex = this.chatHistory.findIndex(m => m.id === targetId);
                        if (messageIndex !== -1) {
                            const message = this.chatHistory[messageIndex];
                            message.isPending = false;
                            if (event.provider) {
                                (message as any).provider = event.provider;
                            }
                            if (typeof event.reasoning === 'string') {
                                (message as any).reasoning = event.reasoning;
                            }
                        }
                    }
                    this.currentStreamingMessage = null;
                    this.loading = false;
                    break;
                }

                case 'error':
                    console.error('[WS] ❌ Error from server:', event.message);
                    this.loading = false;
                    break;

                case 'ack_message':
                    const idx = this.chatHistory.findIndex(m => m.id === event.tempId);
                    if (idx !== -1) {
                        this.chatHistory[idx].id = event.realId;
                        this.chatHistory[idx].isPending = false;
                        if (event.media) {
                            this.chatHistory[idx].media = this.normalizeMediaList(event.media);
                        }
                    }
                    break;

                default:
                    console.warn('[WS] ⚠️ Unknown event:', event);
            }

            setTimeout(() => this.scrollToBottom(), 50);
        });
    }

    ngOnDestroy(): void {
        this.resetAttachments();
    }

    isMessageStreaming(msg: Message): boolean {
        return msg.isPending === true && msg.role === 'assistant';
    }

    toggleEmojiDropdown(event: Event): void {
        event.stopPropagation();

        if (!this.showEmojiPicker) {
            if (this.emojiPickerMode === 'dropdown') {
                const target = (event.currentTarget as HTMLElement) || (event.target as HTMLElement);
                if (!target) {
                    return;
                }
                const rect = target.getBoundingClientRect();
                const dropdownWidth = 320;
                const dropdownHeight = 300;

                let x = rect.left;
                if (x + dropdownWidth > window.innerWidth) {
                    x = window.innerWidth - dropdownWidth;
                }
                if (x < 0) {
                    x = 0;
                }

                let y = rect.top - dropdownHeight - 10;
                if (y < 0) {
                    y = rect.bottom + 10;
                }
                if (y + dropdownHeight > window.innerHeight) {
                    y = Math.max(10, window.innerHeight - dropdownHeight - 10);
                }

                this.emojiDropdownPosition = { x, y };
            }

            this.showEmojiPicker = true;
            this.activeDropdown = 'emoji';
        } else {
            this.closeEmojiPicker();
        }
    }

    closeEmojiPicker(): void {
        this.showEmojiPicker = false;
        if (this.activeDropdown === 'emoji') {
            this.activeDropdown = null;
        }
    }

    // Load more messages with cumulative offset
    loadMoreHistory(): void {
        if (!this.hasMoreMessages || this.isLoadingHistory) return;

        this.isLoadingHistory = true;

        this.websocketService.send(JSON.stringify({
            action: 'fetch_history',
            payload: {
                limit: this.MESSAGES_PER_PAGE,
                offset: this.currentOffset // Правильный offset - не увеличиваем лимит, а сдвигаем позицию
            }
        }));
    }

    addEmoji(emoji: string): void {
        const currentValue = this.chatInput.value || '';
        const newValue = currentValue + emoji;
        this.chatInput.setValue(newValue);
        this.closeEmojiPicker();

        setTimeout(() => {
            const textarea = document.querySelector('.chat-input') as HTMLTextAreaElement;
            if (textarea) {
                textarea.focus();
                this.onKeyUp();
            }
        });
    }

    get sidePanelOffsetStyle(): { [key: string]: string } {
        if (!this.showEmojiPicker || this.emojiPickerMode !== 'side-panel') {
            return {};
        }

        switch (this.emojiPickerSide) {
            case 'right':
                return { 'padding-right': `${this.emojiPanelWidth}px` };
            case 'left':
                return { 'padding-left': `${this.emojiPanelWidth}px` };
            case 'top':
                return { 'padding-top': `${this.emojiPanelHeight}px` };
            case 'bottom':
                return { 'padding-bottom': `${this.emojiPanelHeight}px` };
            default:
                return {};
        }
    }

    loadHistory(): void {
        this.currentOffset = 0;
        this.hasMoreMessages = true;
        this.isLoadingHistory = false;

        this.websocketService.send(JSON.stringify({
            action: 'fetch_history',
            payload: { limit: this.MESSAGES_PER_PAGE }
        }));
    }
    private fetchVoiceModeStatus(): void {
        this.voiceModeLoading = true;
        this.voiceService.voiceModeStatus$()
            .pipe(finalize(() => this.voiceModeLoading = false))
            .subscribe({
                next: (res: VoiceModeResponse) => {
                    if (res && typeof res.running !== 'undefined') {
                        this.voiceModeEnabled = !!res.running;
                    } else {
                        this.fetchVoiceModeStatus();
                    }
                },
                error: (err: any) => {
                    console.error('[VoiceMode] Status error', err);
                },
            });
    }

    toggleVoiceMode(): void {
        if (this.voiceModeLoading) {
            return;
        }

        this.voiceModeLoading = true;
        const request$ = this.voiceModeEnabled
            ? this.voiceService.voiceModeStop$()
            : this.voiceService.voiceModeStart$();

        request$
            .pipe(
                finalize(() => {
                    this.fetchVoiceModeStatus();
                }),
            )
            .subscribe({
                next: (res: VoiceModeResponse) => {
                    this.voiceModeEnabled = !!res?.running;
                },
                error: (err: any) => {
                    console.error('[VoiceMode] Toggle error', err);
                },
            });
    }

    getSettings(): void {
        this.config$ = this.configService.getConfig$().pipe(
            map((config: ProjectConfig | null) => {
                if (!config) {
                    return null;
                }

                const system = config.system || {} as ProjectConfig['system'];
                const userName = system.userName || '';
                const charName = system.charName || '';
                this.userName = userName;
                this.charName = charName;

                return {
                    userName,
                    charName
                };
            })
        )
    }

    // Message handling methods
    sendMessage(): void {
        const trimmed = this.chatInput.value?.trim();
        const mediaPayload = this.attachments.map((attachment) => ({ ...attachment }));
        const hasContent = !!(trimmed && trimmed.length > 0);

        if (!hasContent && mediaPayload.length === 0) {
            return;
        }

        if (this.isProcessingAttachments) {
            this.notificationService.open({
                type: 'warning',
                message: 'Дождитесь завершения обработки вложений перед отправкой.',
                autoClose: true,
            });
            return;
        }

        const tempId = generateTempId();
        const timestamp = new Date().toISOString();

        const userMessage: Message = {
            id: tempId,
            role: 'user',
            content: trimmed ?? '',
            timestamp,
            isPending: true,
            media: mediaPayload,
        };

        this.chatHistory.push(userMessage);
        this.chatInputValue = '';
        this.chatInput.setValue('');
        this.loading = true;
        setTimeout(() => this.scrollToBottom(), 0);

        const transportPayload = {
            ...userMessage,
            media: mediaPayload.map((media) => this.serializeMediaForTransport(media)),
        };

        this.websocketService.send(JSON.stringify({
            action: 'send_message',
            payload: transportPayload,
        }));

        this.resetAttachments();
    }

    copyMessage(msg: Message): void {
        navigator.clipboard.writeText(msg.content).then(() => {
            console.log('Copied!');
        });
    }

    deleteMessage(msg: Message, chain: boolean): void {
        if (!msg || !msg.id) return;
        this.websocketService.send(JSON.stringify({
            action: 'delete_message',
            payload: { message_id: msg.id, chain }
        }));
    }

    rerollMessage(messageId: string | null): void {
        if (!messageId) {
            for (let i = this.chatHistory.length - 1; i >= 0; i--) {
                if (this.chatHistory[i].role === 'assistant') {
                    messageId = this.chatHistory[i].id;
                    break;
                }
            }

            if (!messageId) {
                console.warn('No assistant message found for reroll');
                return;
            }
        }

        this.loading = true;

        const lastAssistantIndex = this.chatHistory.map((msg, i) => ({ msg, i }))
            .reverse()
            .find(item => item.msg.role === 'assistant')?.i;

        if (lastAssistantIndex !== undefined) {
            this.chatHistory.splice(lastAssistantIndex, 1);
        }

        setTimeout(() => this.scrollToBottom(), 0);

        this.websocketService.send(JSON.stringify({
            action: 'reroll_message',
            payload: { message_id: messageId }
        }));
    }

    // Voice methods
    toggleRecording() {
        if (!this.recording) {
            this.voiceService.startRecord$().subscribe(() => {
                this.recording = true;
            });
        } else {
            this.voiceService.stopRecord$().subscribe((res) => {
                this.recording = false;
                const msg = res.data;
                if (msg && msg.content.trim()) {
                    this.scrollToBottom();
                }
            });
        }
    }

    toggleVoice(msgId: string | null | undefined): void {
        if (!msgId) return;

        if (this.currentPlayingMessage === msgId) {
            this.voiceService.stopPlay$().subscribe();
            this.currentPlayingMessage = null;
        } else {
            this.voiceService.playMessage(msgId).subscribe();
            this.currentPlayingMessage = msgId;
        }
    }

    stopVoice() {
        this.voiceService.stopPlay$().subscribe();
        this.currentPlayingMessage = null;
    }

    playMessage(msg: Message) {
        this.voiceService.playMessage(msg.id as string).subscribe();
    }

    // UI methods
    onKeyDown(event: KeyboardEvent): void {
        if (event.key === 'Enter' && event.shiftKey) {
            // Allow line break
        } else if (event.key === 'Enter') {
            event.preventDefault();
            this.sendMessage();
        }
    }

    onKeyUp(): void {
        const textarea = document.querySelector('.chat-input') as HTMLTextAreaElement;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${textarea.scrollHeight}px`;
        }
    }

    scrollToBottom(): void {
        const tryScroll = () => {
            const anchor = document.getElementById('bottomAnchor');
            if (anchor) {
                anchor.scrollIntoView({ behavior: 'auto' });
            } else {
                setTimeout(() => requestAnimationFrame(tryScroll), 50);
            }
        };
        requestAnimationFrame(tryScroll);
    }

    formatTimestamp(isoDate?: string): string {
        if (!isoDate) return '';

        const date = new Date(isoDate);
        const now = new Date();

        const isToday =
            date.getDate() === now.getDate() &&
            date.getMonth() === now.getMonth() &&
            date.getFullYear() === now.getFullYear();

        const time = date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
        });

        if (isToday) return time;

        const dateStr = date.toLocaleDateString(undefined, {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
        });

        return `${dateStr} ${time}`;
    }

    // Unused methods - can be removed if not needed
    toggleMessageMenu(msgId: string | null, event: Event): void {
        event.stopPropagation();
        this.activeDropdown = this.activeDropdown === msgId ? null : msgId;
    }

    editMessage(msg: Message): void {
        console.log('Editing:', msg);
    }

    toggleAttachDropdown(): void {
        if (this.isProcessingAttachments) {
            return;
        }
        if (this.fileInputRef?.nativeElement) {
            this.fileInputRef.nativeElement.click();
        }
    }

    async onFilesSelected(event: Event): Promise<void> {
        event.stopPropagation();
        const input = event.target as HTMLInputElement;
        const files = Array.from(input?.files ?? []);

        if (!files.length) {
            return;
        }

        this.isProcessingAttachments = true;

        try {
            const processed = await Promise.all(
                files.map((file) =>
                    this.buildMediaFromFile(file).catch((error) => {
                        const message = error instanceof Error ? error.message : String(error);
                        this.notificationService.open({
                            type: 'error',
                            message,
                            autoClose: true,
                        });
                        return null;
                    })
                )
            );

            const validMedia = processed.filter((item): item is MessageMedia => !!item);
            if (validMedia.length) {
                this.attachments = [...this.attachments, ...validMedia];
            }
        } finally {
            this.isProcessingAttachments = false;
            if (this.fileInputRef?.nativeElement) {
                this.fileInputRef.nativeElement.value = '';
            }
        }
    }

    removeAttachment(id: string): void {
        this.attachments = this.attachments.filter((item) => item.id !== id);
    }

    private resetAttachments(): void {
        this.attachments = [];
        this.isProcessingAttachments = false;
        this.selectedMedia = null;
        if (this.fileInputRef?.nativeElement) {
            this.fileInputRef.nativeElement.value = '';
        }
    }

    private serializeMediaForTransport(media: MessageMedia): Omit<MessageMedia, 'dataUrl'> {
        const { dataUrl, ...rest } = media;
        return rest;
    }

    private async buildMediaFromFile(file: File): Promise<MessageMedia> {
        if (!file) {
            throw new Error('Файл не найден.');
        }

        const mimeType = file.type || DEFAULT_MIME_TYPE;
        const category = this.determineMediaCategory(mimeType, file.name);
        const dataUrl = await this.readFileAsDataUrl(file);
        const base64 = dataUrl.split(',')[1];

        if (!base64) {
            throw new Error(`Не удалось прочитать файл ${file.name}.`);
        }

        return {
            id: generateTempId(),
            name: file.name,
            mimeType,
            size: file.size,
            category,
            data: base64,
            dataUrl,
        };
    }

    private readFileAsDataUrl(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = () => reject(new Error(`Ошибка чтения файла ${file.name}.`));
            reader.readAsDataURL(file);
        });
    }

    private determineMediaCategory(mimeType: string, fileName: string): MessageMediaCategory {
        if (mimeType?.startsWith('image/')) {
            return 'image';
        }
        if (mimeType?.startsWith('audio/')) {
            return 'audio';
        }
        if (mimeType?.startsWith('video/')) {
            return 'video';
        }

        const extension = fileName?.split('.').pop()?.toLowerCase();
        if (extension && DOCUMENT_EXTENSIONS.has(extension)) {
            return 'document';
        }

        return 'other';
    }

    private normalizeMediaList(media?: any[]): MessageMedia[] {
        if (!Array.isArray(media)) {
            return [];
        }

        return media.map((item: any) => {
            const mimeType = item.mimeType || item.type || DEFAULT_MIME_TYPE;
            const name = item.name || item.originalName || 'file';
            const category: MessageMediaCategory = item.category || this.determineMediaCategory(mimeType, name);
            const data: string | undefined = item.data || undefined;
            const dataUrl: string | undefined = item.dataUrl || (data ? 'data:' + mimeType + ';base64,' + data : undefined);

            return {
                id: item.id || generateTempId(),
                name,
                mimeType,
                size: item.size ?? 0,
                category,
                description: item.description || undefined,
                url: item.url || undefined,
                data,
                dataUrl,
            } as MessageMedia;
        });
    }

    getMediaSource(media: MessageMedia | null | undefined): string {
        if (!media) {
            return '';
        }
        if (media.dataUrl) {
            return media.dataUrl;
        }
        if (media.data) {
            return `data:${media.mimeType};base64,${media.data}`;
        }
        return media.url ?? '';
    }

    previewMedia(media: MessageMedia): void {
        if (media.category === 'image') {
            this.selectedMedia = media;
            return;
        }

        if (media.category === 'document' || media.category === 'other') {
            this.downloadMedia(media);
        }
    }

    closeMediaPreview(): void {
        this.selectedMedia = null;
    }

    downloadMedia(media: MessageMedia): void {
        const source = this.getMediaSource(media);
        if (!source) {
            this.notificationService.open({
                type: 'warning',
                message: 'Не удалось загрузить файл.',
                autoClose: true,
            });
            return;
        }

        const link = document.createElement('a');
        link.href = source;
        link.download = media.name;
        link.target = '_blank';
        link.rel = 'noopener';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    shouldShowReroll(msg: Message, index: number): boolean {
        return msg.role === 'assistant' && index === this.chatHistory.length - 1;
    }
}
