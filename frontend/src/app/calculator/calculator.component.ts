import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ApiService } from '../services/api.service';
import { Header } from '../shared/components/header/Header';
import { Footer } from '../shared/components/footer/Footer';

@Component({
  selector: 'app-calculator',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, Header, Footer],
  templateUrl: './calculator.component.html',
  styleUrls: []
})
export class CalculatorComponent {
  private fb = inject(FormBuilder);
  private apiService = inject(ApiService);

  form: FormGroup = this.fb.group({
    regimen_hidrico: ['Riego', [Validators.required]],
    yield_dm: [20.0, [Validators.required, Validators.min(0.1)]]
  });

  ranking: any[] = [];
  selectedHibridoIndex: number = 0;
  loading: boolean = false;
  error: string | null = null;

  submit(): void {
    if (this.form.valid) {
      this.loading = true;
      this.error = null;
      this.ranking = [];
      this.selectedHibridoIndex = 0;

      this.apiService.optimizarSemilla(this.form.value).subscribe({
        next: (res) => {
          this.ranking = res;
          this.loading = false;
          if (this.ranking.length === 0) {
            this.error = "No se encontraron híbridos con muestras de laboratorio bajo el régimen hídrico seleccionado.";
          }
        },
        error: (err) => {
          console.error("Error al optimizar semillas:", err);
          this.error = err.error?.detail || "Ocurrió un error al procesar la optimización de semillas.";
          this.loading = false;
        }
      });
    } else {
      this.form.markAllAsTouched();
    }
  }

  selectHibrido(index: number): void {
    this.selectedHibridoIndex = index;
  }

  get selectedHibrido(): any {
    if (this.ranking.length > 0 && this.selectedHibridoIndex < this.ranking.length) {
      return this.ranking[this.selectedHibridoIndex];
    }
    return null;
  }

  resetForm(): void {
    this.form.reset({
      regimen_hidrico: 'Riego',
      yield_dm: 20.0
    });
    this.ranking = [];
    this.selectedHibridoIndex = 0;
    this.error = null;
  }
}
