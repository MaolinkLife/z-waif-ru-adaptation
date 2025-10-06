import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { Message } from '../models/message.model';

@Injectable({
    providedIn: 'root'
})
export class ApiService {
    private apiUrl = `${environment.apiBaseUrl}/ollama`;

    constructor(private http: HttpClient) { }

    getOllamaModels$(): Observable<string[]> {
        return this.http.get<{ status: string; models: string[] }>(`${this.apiUrl}/models`).pipe(
            map(({ models }) => models),
            catchError((_err) => of([]))
        );
    }

    sendMessage$(request: any): Observable<any> {
        return this.http.post<{ response: string }>(`${this.apiUrl}/chat`, request)
    }

    getChatHistory$(limit: number = 32) {
        return this.http.get<{ status: string; history: Message[] }>(`${this.apiUrl}/history?limit=${limit}`)
    }

    deleteMessage$(messageId: string, chain: boolean): Observable<any> {
        return this.http.delete<{ status: string; deleted?: number }>(`${this.apiUrl}/history/message?message_id=${messageId}&chain=${chain}`)
    }

    rerollMessage$(messageId: string) {
        return this.http.post<any>(`${this.apiUrl}/history/reroll`, { message_id: messageId });
    }
}
