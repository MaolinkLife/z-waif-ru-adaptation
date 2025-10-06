import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component';

const routes: Routes = [
    {
        path: '',
        component: LayoutComponent,
        children: [
            { path: '', redirectTo: 'chat', pathMatch: 'full' },
            { path: 'chat', loadChildren: () => import('./features/chat/chat.module').then(m => m.ChatModule) },
            { path: 'settings', loadChildren: () => import('./features/settings/settings.module').then(m => m.SettingsModule) },
            { path: 'tasks', loadChildren: () => import('./features/tasks/tasks.module').then(m => m.TasksModule) },
            { path: 'debug', loadChildren: () => import('./features/debug/debug.module').then(m => m.DebugModule) },
        ]
    }
];

@NgModule({
    imports: [RouterModule.forRoot(routes)],
    exports: [RouterModule]
})
export class AppRoutingModule { }
