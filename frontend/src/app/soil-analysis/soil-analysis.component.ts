import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  inject,
  OnDestroy,
  OnInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import * as L from 'leaflet';

import { ApiService } from '../services/api.service';
import { Header } from '../shared/components/header/Header';
import { Footer } from '../shared/components/footer/Footer';

@Component({
  selector: 'app-soil-analysis',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, Header, Footer],
  templateUrl: './soil-analysis.component.html',
  styleUrls: ['./soil-analysis.component.css'],
})
export class SoilAnalysisComponent implements OnInit, AfterViewInit, OnDestroy {
  private fb = inject(FormBuilder);
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);

  // ── Map ──────────────────────────────────────────────────────────────────
  private map: L.Map | null = null;
  private pinMarker: L.Marker | null = null;
  private smapMarkers: L.LayerGroup | null = null;

  // ── State ─────────────────────────────────────────────────────────────────
  loading = false;
  error: string | null = null;
  result: any = null;
  selectedHybridIdx = 0;
  selectedScenario = 'venta';
  smapPlots: any[] = [];

  // ── Form ──────────────────────────────────────────────────────────────────
  form: FormGroup = this.fb.group({
    lat: [null, [Validators.required, Validators.min(-90), Validators.max(90)]],
    lon: [null, [Validators.required, Validators.min(-180), Validators.max(180)]],
    extension_ha: [1, [Validators.required, Validators.min(0.01)]],
    has_irrigation: [false, Validators.required],
    year: [2024, [Validators.required, Validators.min(2015), Validators.max(2030)]],
    precio_leche: [10.50, [Validators.required, Validators.min(0.01)]],
    precio_ensilaje: [2800, [Validators.required, Validators.min(0)]],
    costo_produccion: [1800, [Validators.required, Validators.min(0)]],
    costo_transporte: [150, [Validators.required, Validators.min(0)]],
  });

  ngOnInit(): void {
    // Fix Leaflet default icon
    const iconDefault = L.icon({
      iconRetinaUrl: 'marker-icon-2x.png',
      iconUrl: 'marker-icon.png',
      shadowUrl: 'marker-shadow.png',
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      shadowSize: [41, 41],
    });
    L.Marker.prototype.options.icon = iconDefault;
  }

  ngAfterViewInit(): void {
    setTimeout(() => {
      this.initMap();
      this.loadSmapPlots();
    }, 120);
  }

  ngOnDestroy(): void {
    this.map?.remove();
    this.map = null;
  }

  // ── Map init ──────────────────────────────────────────────────────────────
  private initMap(): void {
    const el = document.getElementById('sa-map');
    if (!el) return;

    this.map = L.map('sa-map', {
      center: [20.85, -102.7],
      zoom: 9,
      scrollWheelZoom: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      attribution: '© OpenStreetMap',
    }).addTo(this.map);

    this.smapMarkers = L.layerGroup().addTo(this.map);

    // Drop pin on click
    this.map.on('click', (e: L.LeafletMouseEvent) => {
      this.setPin(e.latlng.lat, e.latlng.lng);
    });

    setTimeout(() => this.map?.invalidateSize(), 200);
  }

  private loadSmapPlots(): void {
    this.api.getSoilMoisturePlots().subscribe({
      next: (plots: any[]) => {
        this.smapPlots = plots;
        if (!this.smapMarkers) return;
        plots.forEach((p) => {
          const circle = L.circleMarker([p.lat, p.lon], {
            radius: 7,
            fillColor: '#3b82f6',
            color: '#1d4ed8',
            weight: 2,
            opacity: 0.9,
            fillOpacity: 0.45,
          });
          circle.bindTooltip(`📡 ${p.name}`, { direction: 'top' });
          circle.addTo(this.smapMarkers!);
        });
      },
      error: () => { /* non-fatal */ },
    });
  }

  private setPin(lat: number, lon: number): void {
    const rounded = (v: number) => Math.round(v * 1e6) / 1e6;
    this.form.patchValue({ lat: rounded(lat), lon: rounded(lon) });

    const pinIcon = L.divIcon({
      className: '',
      html: `<div class="sa-pin">📍</div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 32],
    });

    if (this.pinMarker) {
      this.pinMarker.setLatLng([lat, lon]);
    } else {
      this.pinMarker = L.marker([lat, lon], { icon: pinIcon }).addTo(this.map!);
    }
    this.pinMarker.bindPopup(`Lat: ${rounded(lat)}, Lon: ${rounded(lon)}`).openPopup();
    this.cdr.detectChanges();
  }

  // ── Submit ─────────────────────────────────────────────────────────────────
  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading = true;
    this.error = null;
    this.result = null;
    this.selectedHybridIdx = 0;

    const v = this.form.value;
    this.api.recomendacionHumedad({
      lat: v.lat,
      lon: v.lon,
      extension_ha: v.extension_ha,
      has_irrigation: v.has_irrigation,
      year: v.year,
      precio_ensilaje: v.precio_ensilaje,
      precio_leche: v.precio_leche,
      costo_produccion: v.costo_produccion,
      costo_transporte: v.costo_transporte,
    }).subscribe({
      next: (res: any) => {
        this.result = res;
        this.loading = false;
        // Mark snapped plot on map
        if (res.snapped_plot && this.map) {
          const p = res.snapped_plot;
          L.circleMarker([p.lat, p.lon], {
            radius: 12,
            fillColor: '#10b981',
            color: '#065f46',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.6,
          })
            .bindPopup(`✅ Parcela de referencia: ${p.name}`)
            .addTo(this.map)
            .openPopup();
          this.map.panTo([p.lat, p.lon]);
        }
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        this.error = err.error?.detail || 'Error al procesar la solicitud.';
        this.loading = false;
        this.cdr.detectChanges();
      },
    });
  }

  reset(): void {
    this.form.reset({
      lat: null, lon: null,
      extension_ha: 1, has_irrigation: false, year: 2024,
      precio_leche: 10.50, precio_ensilaje: 2800,
      costo_produccion: 1800, costo_transporte: 150,
    });
    this.result = null;
    this.error = null;
    this.pinMarker?.remove();
    this.pinMarker = null;
    this.cdr.detectChanges();
  }

  // ── Getters ────────────────────────────────────────────────────────────────
  get ranking(): any[] { return this.result?.ranking ?? []; }
  get selectedHybrid(): any { return this.ranking[this.selectedHybridIdx] ?? null; }
  get smProfile(): any { return this.result?.sm_profile ?? null; }
  get smWarning(): string | null { return this.result?.sm_warning ?? null; }
  get snappedPlot(): any { return this.result?.snapped_plot ?? null; }
  get notaProyeccion(): string | null { return this.result?.nota_proyeccion ?? null; }
  get extensionHa(): number { return this.form.get('extension_ha')?.value ?? 1; }
  get precioLeche(): number { return this.form.get('precio_leche')?.value ?? 10.50; }

  suitabilityLabel(s: number): string {
    if (s >= 80) return 'Excelente';
    if (s >= 65) return 'Buena';
    if (s >= 50) return 'Moderada';
    if (s >= 35) return 'Baja';
    return 'Severa';
  }

  suitabilityColor(s: number): string {
    if (s >= 80) return 'emerald';
    if (s >= 65) return 'blue';
    if (s >= 50) return 'amber';
    return 'rose';
  }

  confidenceClass(c: any): string {
    const map: Record<string, string> = {
      green: 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-400',
      blue: 'bg-blue-50 dark:bg-blue-950/20 border-blue-400',
      yellow: 'bg-amber-50 dark:bg-amber-950/20 border-amber-400',
      red: 'bg-rose-50 dark:bg-rose-950/20 border-rose-400',
    };
    return map[c?.color_indicador] ?? 'bg-slate-50 border-slate-200';
  }

  confidenceTextClass(c: any): string {
    const map: Record<string, string> = {
      green: 'text-emerald-700 dark:text-emerald-300',
      blue: 'text-blue-700 dark:text-blue-300',
      yellow: 'text-amber-700 dark:text-amber-300',
      red: 'text-rose-700 dark:text-rose-300',
    };
    return map[c?.color_indicador] ?? 'text-slate-700';
  }

  scenarioName(s: string): string {
    return ({ venta: 'Vender Ensilaje', uso_propio: 'Usar en Lechería', compra: 'Comprar Ensilaje' } as any)[s] ?? s;
  }
}
