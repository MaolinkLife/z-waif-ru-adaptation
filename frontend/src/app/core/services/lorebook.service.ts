// lorebook.service.ts
import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { LorebookEntry } from '../models/lorebook-entry.model';

@Injectable({
    providedIn: 'root'
})
export class LorebookService {
    apiUrl: string = `${environment.apiBaseUrl}/lorebook`;

    constructor(private http: HttpClient) { }

    getLorebook$(): Observable<LorebookEntry[]> {
        return this.http.get<LorebookEntry[]>(this.apiUrl);
    }

    createEntry$(entry: LorebookEntry): Observable<any> {
        return this.http.post(this.apiUrl, entry);
    }

    updateEntry$(id: number, entry: LorebookEntry): Observable<any> {
        return this.http.put(`${this.apiUrl}/${id}`, entry);
    }

    deleteEntry$(id: number): Observable<any> {
        return this.http.delete(`${this.apiUrl}/${id}`);
    }

    searchEntries$(query: string): Observable<LorebookEntry[]> {
        return this.http.get<LorebookEntry[]>(`${this.apiUrl}/search?query=${encodeURIComponent(query)}`);
    }
}
