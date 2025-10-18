import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ConfigService } from '../../../../../core/services/config.service';
import { ResourcesService } from '../../../../../core/services/resources.service';
import { Observable, BehaviorSubject, combineLatest } from 'rxjs';
import { map, startWith, tap, finalize } from 'rxjs/operators';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

interface AudioDevice {
    id: number;
    name: string;
}

interface AudioDevicesData {
    inputDevices: AudioDevice[];
}

@Component({
    selector: 'app-audio-settings',
    templateUrl: './audio-settings.component.html',
    styleUrls: ['./audio-settings.component.less']
})
export class AudioSettingsComponent implements OnInit {
    audioForm: FormGroup;
    originalConfig: any = {};
    isLoading$ = new BehaviorSubject<boolean>(true);

    devices$: Observable<AudioDevicesData> = new Observable<AudioDevicesData>();

    constructor(
        private fb: FormBuilder,
        private configService: ConfigService,
        private resourcesService: ResourcesService,
        private localizationService: LocalizationService,
    ) {
        this.audioForm = this.createForm();
    }

    ngOnInit(): void {
        this.loadConfigAndDevices();
        this.localizationService.init();
    }

    private createForm(): FormGroup {
        return this.fb.group({
            inputDeviceId: [0],
            sampleRate: [16000],
            channels: [1],
            chunkSize: [1024],
            enableVad: [true],
            vadThreshold: [0.5],
            silenceTimeout: [3.0],
            minAudioLength: [0.5],
            maxAudioLength: [30.0],
            triggerWords: [[]],
            ignoreTriggerWords: [true]
        });
    }

    private loadConfigAndDevices(): void {
        combineLatest([
            this.configService.getConfig$(),
            this.resourcesService.getAudioDevices$()
        ]).pipe(
            tap(() => this.isLoading$.next(true)),
            map(([config, devices]) => {
                // Load config
                if (config && config.audio) {
                    this.originalConfig = this.normalizeAudioPayload(config.audio);
                    this.audioForm.patchValue(this.originalConfig);
                }

                // Load devices
                const inputDevices: AudioDevice[] = [
                    { id: 0, name: 'Default Device' },
                    ...(devices.recording_devices || []).map(
                        ([id, name]: [number, string]) => ({ id, name })
                    )
                ];

                return { inputDevices };
            }),
            finalize(() => this.isLoading$.next(false))
        ).subscribe(devicesData => {
            this.devices$ = new Observable<AudioDevicesData>(subscriber => {
                subscriber.next(devicesData);
                subscriber.complete();
            });
        });
    }

    saveChanges(): void {
        const normalized = this.normalizeAudioPayload(this.audioForm.value);
        if (this.hasPayloadChanged(normalized)) {
            const updateData = { audio: normalized };
            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    console.log('Audio settings updated:', response);
                    this.originalConfig = normalized;
                },
                error: (error) => {
                    console.error('Error updating audio settings:', error);
                }
            });
        }
    }

    private hasPayloadChanged(current: any): boolean {
        return JSON.stringify(current) !== JSON.stringify(this.originalConfig);
    }

    hasChanges(): boolean {
        const normalized = this.normalizeAudioPayload(this.audioForm.value);
        return this.hasPayloadChanged(normalized);
    }

    private normalizeAudioPayload(source: any): any {
        const toNumber = (value: any, fallback: number) => {
            if (value === null || value === undefined || value === '') {
                return fallback;
            }
            const num = Number(value);
            return Number.isFinite(num) ? num : fallback;
        };

        return {
            inputDeviceId: toNumber(source?.inputDeviceId, 0),
            sampleRate: toNumber(source?.sampleRate, 16000),
            channels: toNumber(source?.channels, 1),
            chunkSize: toNumber(source?.chunkSize, 1024),
            enableVad: !!source?.enableVad,
            vadThreshold: Number(source?.vadThreshold ?? 0.5),
            silenceTimeout: Number(source?.silenceTimeout ?? 3.0),
            minAudioLength: Number(source?.minAudioLength ?? 0.5),
            maxAudioLength: Number(source?.maxAudioLength ?? 30.0),
            triggerWords: Array.isArray(source?.triggerWords) ? source.triggerWords : [],
            ignoreTriggerWords: source?.ignoreTriggerWords ?? true,
        };
    }
}
