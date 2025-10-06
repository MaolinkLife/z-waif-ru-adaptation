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
            maxAudioLength: [30.0]
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
                    this.originalConfig = { ...config.audio };
                    this.audioForm.patchValue(config.audio);
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
        const changes = this.getChanges();
        if (Object.keys(changes).length > 0) {
            const updateData = { audio: changes };
            this.configService.updateConfig$(updateData).subscribe({
                next: (response) => {
                    console.log('Audio settings updated:', response);
                    this.originalConfig = { ...this.audioForm.value };
                },
                error: (error) => {
                    console.error('Error updating audio settings:', error);
                }
            });
        }
    }

    private getChanges(): any {
        const current = this.audioForm.value;
        const changes: any = {};

        Object.keys(current).forEach(key => {
            const originalValue = this.originalConfig ? this.originalConfig[key] : undefined;
            if (current[key] !== originalValue) {
                changes[key] = current[key];
            }
        });

        return changes;
    }

    hasChanges(): boolean {
        return Object.keys(this.getChanges()).length > 0;
    }
}
