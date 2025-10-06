import { Component, Input } from '@angular/core';

@Component({
    selector: 'app-skeleton',
    templateUrl: './skeleton.component.html',
    styleUrls: ['./skeleton.component.less']
})
export class SkeletonComponent {
    @Input() width: string = '100%';
    @Input() height: string = '1rem';
    @Input() animated: boolean = true;
    @Input() circle: boolean = false;
}
