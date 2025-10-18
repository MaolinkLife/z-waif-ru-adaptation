import { Component, OnInit } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { finalize, take } from 'rxjs/operators';
import { LorebookEntry } from '../../../../../core/models/lorebook-entry.model';
import { LorebookService } from '../../../../../core/services/lorebook.service';
import { NotificationService } from '../../../../../shared/components/notification/notification.service';
import { LocalizationService } from '../../../../../shared/pipes/translation/localization.service';

@Component({
    selector: 'app-lorebook',
    templateUrl: './lorebook.component.html',
    styleUrls: ['./lorebook.component.less']
})
export class LorebookComponent implements OnInit {

    entries$: BehaviorSubject<LorebookEntry[]> = new BehaviorSubject<LorebookEntry[]>([]);
    isLoading$ = new BehaviorSubject<boolean>(true);

    constructor(
        private lorebookService: LorebookService,
        private notificationService: NotificationService,
        private localizationService: LocalizationService
    ) { }

    ngOnInit(): void {
        this.loadEntries();
        this.localizationService.init();
    }

    loadEntries(): void {
        this.lorebookService.getLorebook$().pipe(
            take(1),
            finalize(() => {
                this.isLoading$.next(false);
            })
        ).subscribe({
            next: (entries) => {
                this.entries$.next(entries);
            },
            error: (error) => {
                console.error('Ошибка загрузки записей:', error);
                this.isLoading$.next(false);
            }
        });
    }

    clickDelete(entry: LorebookEntry): void {
        if (entry.id && confirm('Вы уверены, что хотите удалить эту запись?')) {
            this.lorebookService.deleteEntry$(entry.id).subscribe(
                () => {
                    this.loadEntries(); // Перезагружаем список
                },
                error => {
                    console.error('Ошибка удаления записи:', error);
                }
            );
        }
    }

    addNewEntry(): void {
        const newEntry: LorebookEntry = {
            title: '',
            content: '',
            keywords: '',
            category: 'general',
            active: true
        };

        this.lorebookService.createEntry$(newEntry).subscribe(
            response => {
                this.notificationService.open({
                    title: 'New Entry Created',
                    type: 'success',
                    autoClose: true
                });
                this.loadEntries(); // Перезагружаем список
            },
            error => {
                console.error('Ошибка создания записи:', error);
            }
        );
    }

    updateEntry(entry: LorebookEntry): void {
        if (entry.id) {
            this.lorebookService.updateEntry$(entry.id, entry).subscribe(
                response => {
                    this.notificationService.open({
                        message: 'Lorebook Updated',
                        title: 'Success',
                        type: 'success',
                        autoClose: true
                    });
                    console.log('Lorebook Updated', response);
                },
                error => {
                    console.error('Ошибка обновления записи:', error);
                }
            );
        }
    }
}
