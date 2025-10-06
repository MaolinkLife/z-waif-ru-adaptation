import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject } from 'rxjs';

@Injectable({
    providedIn: 'root'
})
export class LocalizationService {
    private translations = new BehaviorSubject<Record<string, string>>({});
    currentLang = new BehaviorSubject<string>('ru-RU');

    constructor(private http: HttpClient) { }

    setLanguage(lang: string) {
        this.currentLang.next(lang);
        localStorage.setItem('language', lang);
        this.loadTranslations(lang);
    }

    getTranslationUpdates() {
        return this.translations.asObservable();
    }

    t(key: string): string {
        const keys = key.split('.');
        let value: any = this.translations.getValue(); // вот тут — any, baby

        for (const k of keys) {
            if (value && k in value) {
                value = value[k];
            } else {
                return key;
            }
        }

        return typeof value === 'string' ? value : key;
    }

    private loadTranslations(lang: string) {
        this.http.get<Record<string, string>>(`/assets/i18n/${lang}.json`).subscribe(
            data => this.translations.next(data),
            err => console.error(`Failed to load translations for ${lang}`, err)
        );
    }

    init() {
        const saved = localStorage.getItem('language') || 'ru-RU';
        this.setLanguage(saved);
    }
}
