import { Injectable } from '@angular/core';

type Theme = 'dark' | 'light';

@Injectable({ providedIn: 'root' })
export class ThemeService {
    private readonly storageKey = 'app-theme';

    setTheme(theme: Theme) {
        document.body.classList.remove('theme-dark', 'theme-light');
        document.body.classList.add(`theme-${theme}`);
        localStorage.setItem(this.storageKey, theme);
    }

    getTheme(): Theme {
        return (localStorage.getItem(this.storageKey) as Theme) || 'dark';
    }

    initTheme() {
        this.setTheme(this.getTheme());
    }

    toggleTheme() {
        this.setTheme(this.getTheme() === 'dark' ? 'light' : 'dark');
    }
}
