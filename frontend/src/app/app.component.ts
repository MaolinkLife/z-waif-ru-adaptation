import { Component, OnInit } from '@angular/core';
import { WebsocketService } from './core/services/websocket.service';

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.less']
})
export class AppComponent implements OnInit {
    title = 'z-waif-project';

    constructor(private websocketService: WebsocketService) {

    }

    ngOnInit() {
        this.websocketService.connect();
    }
}
