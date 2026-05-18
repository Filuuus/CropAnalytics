import { Component, inject, ChangeDetectorRef } from '@angular/core';
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
  private cdr = inject(ChangeDetectorRef);

  form: FormGroup = this.fb.group({
    regimen_hidrico: ['Riego', [Validators.required]],
    yield_dm: [20.0, [Validators.required, Validators.min(0.1)]],
    hectareas: [1, [Validators.required, Validators.min(0.01)]],
    precio_leche: [10.50, [Validators.required, Validators.min(0.01)]]
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

      // Extrae únicamente los parámetros que el backend necesita
      const { regimen_hidrico, yield_dm } = this.form.value;

      this.apiService.optimizarSemilla({ regimen_hidrico, yield_dm }).subscribe({
        next: (res) => {
          this.ranking = res;
          this.loading = false;
          if (this.ranking.length === 0) {
            this.error = "No se encontraron híbridos con muestras de laboratorio bajo el régimen hídrico seleccionado.";
          }
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.error("Error al optimizar semillas:", err);
          this.error = err.error?.detail || "Ocurrió un error al procesar la optimización de semillas.";
          this.loading = false;
          this.cdr.detectChanges();
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

  get proyeccionFinancieraGanador(): number {
    if (this.ranking && this.ranking.length > 0) {
      return this.ranking[0].leche_ha * 10.50;
    }
    return 0;
  }

  // Getters para el cálculo de rancho completo (proyecciones a gran escala)
  get hectareas(): number {
    return this.form.get('hectareas')?.value || 1;
  }

  get precioLeche(): number {
    return this.form.get('precio_leche')?.value || 10.50;
  }

  get hibridoGanador(): any {
    return this.ranking && this.ranking.length > 0 ? this.ranking[0] : null;
  }

  get produccionTotalGanador(): number {
    const ganador = this.hibridoGanador;
    return ganador ? ganador.leche_ha * this.hectareas : 0;
  }

  get ingresoBrutoGanador(): number {
    return this.produccionTotalGanador * this.precioLeche;
  }

  resetForm(): void {
    this.form.reset({
      regimen_hidrico: 'Riego',
      yield_dm: 20.0,
      hectareas: 1,
      precio_leche: 10.50
    });
    this.ranking = [];
    this.selectedHibridoIndex = 0;
    this.error = null;
  }

  resetConsulta(): void {
    this.resetForm();
  }
}
