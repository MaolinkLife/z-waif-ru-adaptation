// services/resources.service.ts (добавляем новый метод)
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

@Injectable({
    providedIn: 'root'
})
export class ResourcesService {
    private apiUrl = environment.apiBaseUrl;

    constructor(private http: HttpClient) { }

    getAudioDevices$(): Observable<any> {
        return this.http.get(`${this.apiUrl}/resources/devices`).pipe(
            catchError((error) => {
                console.error('Error getting audio devices:', error);
                return of({});
            }
            ));
    }

    // НОВЫЙ МЕТОД - Получение скриншотов мониторов
    getMonitorScreens$(): Observable<any> {
        return this.http.get(`${this.apiUrl}/resources/monitors/screens`).pipe(
            catchError((error) => {
                console.error('Error getting monitor screens:', error);
                return of({ monitors: [] });
            }
            ));
    }

    // Дополнительный метод для получения информации о мониторах
    getMonitorInfo$(): Observable<any> {
        return this.http.get(`${this.apiUrl}/resources/monitors/info`).pipe(
            catchError((error) => {
                console.error('Error getting monitor info:', error);
                return of({ data: {} });
            }
            ));
    }

    getEdgeVoices$(): Observable<any> {
        return this.http.get(`${this.apiUrl}/resources/voices`).pipe(
            catchError((error) => {
                console.error('Error getting edge voices:', error);
                return of({ voices: [] });
            })
        );
    }

    getVoiceProviders$(): Observable<any> {
        return this.http.get(`${this.apiUrl}/voice/providers`).pipe(
            catchError((error) => {
                console.error('Error getting voice providers status:', error);
                return of({ status: 'error', providers: {} });
            })
        );
    }
}
