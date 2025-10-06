import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Observable } from 'rxjs';
import { Message } from '../models/message.model';
import { map } from 'rxjs/operators';

export interface VoiceModeResponse {
    status: string;
    message: string;
    running: boolean;
}

@Injectable({
    providedIn: 'root'
})
export class VoiceService {
    apiUrl: string = `${environment.apiBaseUrl}/voice`;

    constructor(private http: HttpClient) { }

    stopPlay$(): Observable<any> {
        return this.http.post(`${this.apiUrl}/stop`, {});
    }

    playMessage(message_id: string): Observable<any> {
        return this.http.post<{ status: string; context: any }>(`${this.apiUrl}/play`, { message_id });
    }

    startRecord$(): Observable<any> {
        return this.http.post(`${this.apiUrl}/record/start`, {}).pipe(map((res) => {
            console.log({ res });
            return res;
        }));
    }

    stopRecord$(): Observable<{ data: Message }> {
        return this.http.post<{ data: Message }>(`${this.apiUrl}/record/stop`, {});
    }

    voiceModeStatus$(): Observable<VoiceModeResponse> {
        return this.http.get<VoiceModeResponse>(`${this.apiUrl}/mode/status`);
    }

    voiceModeStart$(): Observable<VoiceModeResponse> {
        return this.http.post<VoiceModeResponse>(`${this.apiUrl}/mode/start`, {});
    }

    voiceModeStop$(): Observable<VoiceModeResponse> {
        return this.http.post<VoiceModeResponse>(`${this.apiUrl}/mode/stop`, {});
    }
}
