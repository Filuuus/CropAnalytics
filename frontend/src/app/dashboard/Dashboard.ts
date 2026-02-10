import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="p-10 text-center">
      <h1 class="text-2xl font-bold">Dashboard</h1>
      <p>Este componente no se exportó correctamente de Locofy.</p>
    </div>
  `,
  styles: []
})
export class Dashboard { }