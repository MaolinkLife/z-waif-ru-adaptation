import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { SidebarComponent } from './layout/components/sidebar/sidebar.component';
import { HeaderComponent } from './layout/components/header/header.component';
import { LayoutComponent } from './layout/layout.component';
import { ThemeService } from './core/services/theme.service';
import { SharedModule } from './shared/shared.module';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { ConfigService } from './core/services/config.service';
import { MarkdownModule } from 'ngx-markdown';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { MemoryModalComponent } from './layout/components/modals/memory-modal/memory-modal.component';
import { MainModalComponent } from './layout/components/modals/main-modal/main-modal.component';
import { LorebookComponent } from './layout/components/modals/main-modal/lorebook/lorebook.component';
import { VoiceSettingsComponent } from './layout/components/modals/main-modal/voice-settings/voice-settings.component';
import { AudioSettingsComponent } from './layout/components/modals/main-modal/audio-settings/audio-settings.component';
import { VisionSettingsComponent } from './layout/components/modals/main-modal/vision-settings/vision-settings.component';
import { RagSettingsComponent } from './layout/components/modals/main-modal/rag-settings/rag-settings.component';
import { AnalyzerSettingsComponent } from './layout/components/modals/main-modal/analyzer-settings/analyzer-settings.component';
import { GenerationSettingsComponent } from './layout/components/modals/main-modal/generation-settings/generation-settings.component';
import { MonitorSelectionModalComponent } from './layout/components/modals/monitor-selection-modal/monitor-selection-modal.component';
import { CoreSettingsComponent } from './layout/components/modals/main-modal/core-settings/core-settings.component';
import { SystemSettingsComponent } from './layout/components/modals/main-modal/system-settings/system-settings.component';


@NgModule({
    declarations: [
        AppComponent,
        SidebarComponent,
        HeaderComponent,
        LayoutComponent,
        MemoryModalComponent,
        MainModalComponent,
        LorebookComponent,
        VoiceSettingsComponent,
        VisionSettingsComponent,
        AudioSettingsComponent,
        RagSettingsComponent,
        AnalyzerSettingsComponent,
        GenerationSettingsComponent,
        MonitorSelectionModalComponent,
        CoreSettingsComponent,
        SystemSettingsComponent,
    ],
    imports: [
        BrowserModule,
        AppRoutingModule,
        SharedModule,
        HttpClientModule,
        BrowserAnimationsModule,
        MarkdownModule.forRoot({ loader: HttpClient }),
    ],
    providers: [ThemeService, ConfigService],
    bootstrap: [AppComponent],
    entryComponents: [
        MemoryModalComponent,
        MainModalComponent,
    ]
})
export class AppModule { }
