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
    hectareas: [1, [Validators.required, Validators.min(0.01)]],
    precio_leche: [10.50, [Validators.required, Validators.min(0.01)]]
  });

  ranking: any[] = [];
  selectedHibridoIndex: number = 0;
  loading: boolean = false;
  error: string | null = null;
  hibridoSeleccionado: any = null;
  hibridoA: any = null;
  hibridoB: any = null;

  submit(): void {
    if (this.form.valid) {
      this.loading = true;
      this.error = null;
      this.ranking = [];
      this.selectedHibridoIndex = 0;
      this.hibridoSeleccionado = null;
      this.hibridoA = null;
      this.hibridoB = null;

      // Extrae únicamente los parámetros que el backend necesita
      const { regimen_hidrico } = this.form.value;

      this.apiService.optimizarSemilla({ regimen_hidrico }).subscribe({
        next: (res) => {
          this.ranking = res;
          this.loading = false;
          if (this.ranking.length === 0) {
            this.error = "No se encontraron híbridos con muestras de laboratorio bajo el régimen hídrico seleccionado.";
          } else {
            // Auto-seleccionar primer lugar como A por defecto
            this.hibridoA = this.ranking[0];
            this.hibridoSeleccionado = this.ranking[0];
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

  seleccionarHibrido(hibrido: any): void {
    if (this.hibridoA === hibrido) {
      if (this.hibridoB) {
        this.hibridoA = this.hibridoB;
        this.hibridoSeleccionado = this.hibridoB;
        this.hibridoB = null;
      } else {
        this.hibridoA = null;
        this.hibridoSeleccionado = null;
      }
    } else if (this.hibridoB === hibrido) {
      this.hibridoB = null;
    } else {
      if (!this.hibridoA) {
        this.hibridoA = hibrido;
        this.hibridoSeleccionado = hibrido;
      } else if (!this.hibridoB) {
        this.hibridoB = hibrido;
      } else {
        this.hibridoA = this.hibridoB;
        this.hibridoSeleccionado = this.hibridoB;
        this.hibridoB = hibrido;
      }
    }
    this.cdr.detectChanges();
  }

  abrirComparacion(hibrido: any): void {
    this.hibridoSeleccionado = hibrido;
    this.cdr.detectChanges();
  }

  cerrarModal(): void {
    this.hibridoSeleccionado = null;
    this.cdr.detectChanges();
  }

  get costoOportunidad(): number {
    if (this.ranking && this.ranking.length > 0 && this.hibridoSeleccionado) {
      return (this.ranking[0].leche_ha - this.hibridoSeleccionado.leche_ha) * this.hectareas * this.precioLeche;
    }
    return 0;
  }

  get comparacionDiferencia(): number {
    if (this.hibridoA && this.hibridoB) {
      return Math.abs(this.hibridoA.leche_ha - this.hibridoB.leche_ha) * this.hectareas * this.precioLeche;
    }
    return 0;
  }

  get hibridoSuperior(): any {
    if (this.hibridoA && this.hibridoB) {
      return this.hibridoA.leche_ha >= this.hibridoB.leche_ha ? this.hibridoA : this.hibridoB;
    }
    return null;
  }

  get hibridoInferior(): any {
    if (this.hibridoA && this.hibridoB) {
      return this.hibridoA.leche_ha < this.hibridoB.leche_ha ? this.hibridoA : this.hibridoB;
    }
    return null;
  }

  resetForm(): void {
    this.form.reset({
      regimen_hidrico: 'Riego',
      hectareas: 1,
      precio_leche: 10.50
    });
    this.ranking = [];
    this.selectedHibridoIndex = 0;
    this.hibridoSeleccionado = null;
    this.hibridoA = null;
    this.hibridoB = null;
    this.error = null;
  }

  resetConsulta(): void {
    this.resetForm();
  }
}
