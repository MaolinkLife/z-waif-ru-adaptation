import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { ProjectConfig } from '../models/project-config.model';
import { HttpClient } from '@angular/common/http';
import { ProjectConfigDto } from '../models/project-config.dto';
import { catchError, map, tap } from 'rxjs/operators'
import { mapProjectConfigDtoToModel, mapPartialModelToDto } from '../utils/project-config.mapper';
import { environment } from '../../../environments/environment';
import { GenerationPreset } from '../models/generation-preset.model';

@Injectable({
    providedIn: 'root'
})
export class ConfigService {
    private apiUrl = environment.apiBaseUrl;

    constructor(private http: HttpClient) { }

    getConfig$(): Observable<ProjectConfig | null> {
        return this.http.get<ProjectConfigDto>(`${this.apiUrl}/config/`).pipe(
            tap((config: any) => {
                console.log('[Config Service] Load Config From Server:', { config });
            }),
            map(mapProjectConfigDtoToModel),
            catchError((_err) => of(null))
        )
    }

    updateConfig$(body: any): Observable<any> {
        // Если передается частичный конфиг - используем PATCH
        if (body.voice || body.modules || body.api || body.vision || body.rag || body.analyzer) {
            return this.http.patch(`${this.apiUrl}/config`, mapPartialModelToDto(body));
        }
        // Иначе - используем POST для полной замены
        return this.http.post(`${this.apiUrl}/config`, mapPartialModelToDto(body));
    }

    getGenerationPresets$(): Observable<GenerationPreset[]> {
        return this.http.get<{ status: string; presets: GenerationPreset[] }>(`${this.apiUrl}/presets/`).pipe(
            map(({ presets }) => presets),
            catchError((_err) => of([]))
        )
    }

    saveGenerationPreset$(preset: GenerationPreset): Observable<any> {
        return this.http.post(`${this.apiUrl}/presets/`, preset)
    }

    // Новый метод для получения system
    getSystem$(): Observable<{ system: { char_name: string; prompt: string } } | null> {
        return this.http.get<{ system: { char_name: string; prompt: string } }>(`${this.apiUrl}/config/system`).pipe(
            catchError((_err) => of(null))
        );
    }


    // Новый метод для обновления system
    updateSystem$(prompt: string, charName?: string): Observable<any> {
        const body = { prompt, char_name: charName };
        return this.http.post(`${this.apiUrl}/config/system`, body);
    }

    // Новый метод для получения конкретного значения из конфига (если нужно)
    getConfigValue$(path: string): Observable<any> {
        return this.getConfig$().pipe(
            map(config => {
                if (!config) return null;
                return this.getNestedValue(config, path);
            })
        );
    }

    private getNestedValue(obj: any, path: string): any {
        return path.split('.').reduce((current, key) => current?.[key], obj);
    }
}
