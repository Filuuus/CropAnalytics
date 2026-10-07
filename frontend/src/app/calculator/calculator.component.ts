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
    estado_id: [null],
    municipio_id: [null],
    hectareas: [1, [Validators.required, Validators.min(0.01)]],
    precio_leche: [10.50, [Validators.required, Validators.min(0.01)]],
    precio_ensilaje: [2800, [Validators.required, Validators.min(0)]],
    costo_produccion: [1800, [Validators.required, Validators.min(0)]],
    costo_transporte: [150, [Validators.required, Validators.min(0)]]
  });

  ranking: any[] = [];
  selectedHibridoIndex: number = 0;
  loading: boolean = false;
  error: string | null = null;
  hibridoSeleccionado: any = null;
  hibridoA: any = null;
  hibridoB: any = null;
  
  // Location data
  estados: any[] = [];
  municipios: any[] = [];
  loadingEstados: boolean = false;
  loadingMunicipios: boolean = false;

  ngOnInit(): void {
    this.loadEstados();
    
    // Watch for estado changes to load municipios
    this.form.get('estado_id')?.valueChanges.subscribe(estadoId => {
      this.form.patchValue({ municipio_id: null });
      this.municipios = [];
      if (estadoId) {
        this.loadMunicipios(estadoId);
      }
    });
  }

  loadEstados(): void {
    this.loadingEstados = true;
    this.apiService.getEstados().subscribe({
      next: (data) => {
        this.estados = data;
        this.loadingEstados = false;
      },
      error: (err) => {
        console.error('Error loading estados:', err);
        this.loadingEstados = false;
      }
    });
  }

  loadMunicipios(estadoId: number): void {
    this.loadingMunicipios = true;
    this.apiService.getMunicipios(estadoId).subscribe({
      next: (data) => {
        this.municipios = data;
        this.loadingMunicipios = false;
      },
      error: (err) => {
        console.error('Error loading municipios:', err);
        this.loadingMunicipios = false;
      }
    });
  }

  submit(): void {
    if (this.form.valid) {
      this.loading = true;
      this.error = null;
      this.ranking = [];
      this.selectedHibridoIndex = 0;
      this.hibridoSeleccionado = null;
      this.hibridoA = null;
      this.hibridoB = null;

      // Extrae los parámetros que el backend necesita
      const { regimen_hidrico, estado_id, municipio_id, precio_leche, precio_ensilaje, costo_produccion, costo_transporte } = this.form.value;

      const payload: any = {
        regimen_hidrico,
        precio_leche,
        precio_ensilaje,
        costo_produccion,
        costo_transporte
      };

      // Add location parameters if selected
      if (estado_id) {
        payload.estado_id = estado_id;
      }
      if (municipio_id) {
        payload.municipio_id = municipio_id;
      }

      this.apiService.optimizarSemilla(payload).subscribe({
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
  // Helper methods for confidence display
  getConfidenceClass(confianza: any): string {
    if (!confianza) return 'bg-slate-100 dark:bg-slate-800';
    const color = confianza.color_indicador || 'gray';
    const colorMap: { [key: string]: string } = {
      'green': 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 dark:border-emerald-500/80',
      'blue': 'bg-blue-50 dark:bg-blue-950/20 border-blue-500 dark:border-blue-500/80',
      'yellow': 'bg-amber-50 dark:bg-amber-950/20 border-amber-500 dark:border-amber-500/80',
      'red': 'bg-rose-50 dark:bg-rose-950/20 border-rose-500 dark:border-rose-500/80'
    };
    return colorMap[color] || 'bg-slate-100 dark:bg-slate-800';
  }

  getConfidenceIcon(nivel: string): string {
    const iconMap: { [key: string]: string } = {
      'Excelente': '✅',
      'Buena': '👍',
      'Moderada': '⚠️',
      'Baja': '❌'
    };
    return iconMap[nivel] || '❓';
  }

  getConfidenceTextClass(confianza: any): string {
    if (!confianza) return 'text-slate-700 dark:text-slate-300';
    const color = confianza.color_indicador || 'gray';
    const colorMap: { [key: string]: string } = {
      'green': 'text-emerald-700 dark:text-emerald-300',
      'blue': 'text-blue-700 dark:text-blue-300',
      'yellow': 'text-amber-700 dark:text-amber-300',
      'red': 'text-rose-700 dark:text-rose-300'
    };
    return colorMap[color] || 'text-slate-700 dark:text-slate-300';
  }

  getScenarioName(scenario: string): string {
    const nameMap: { [key: string]: string } = {
      'venta': 'Vender Ensilaje',
      'uso_propio': 'Usar en Lechería',
      'compra': 'Comprar Ensilaje'
    };
    return nameMap[scenario] || scenario;
  }

  selectedScenario: string = 'venta';


  resetForm(): void {
    this.form.reset({
      regimen_hidrico: 'Riego',
      estado_id: null,
      municipio_id: null,
      hectareas: 1,
      precio_leche: 10.50,
      precio_ensilaje: 2800,
      costo_produccion: 1800,
      costo_transporte: 150
    });
    this.municipios = [];
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
