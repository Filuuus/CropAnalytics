import { Component, Input, OnInit, OnDestroy, AfterViewInit, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import * as L from 'leaflet';
import { ApiService } from '../../../services/api.service';

@Component({
  selector: 'map-view',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './MapView.html',
  styleUrls: ['./MapView.css']
})
export class MapView implements OnInit, AfterViewInit, OnDestroy {
  @Input() filteredCiclos: any[] = [];
  @Input() selectedYear: number[] = [];
  @Input() selectedMarca: string[] = [];
  @Input() selectedCondicion: string[] = [];
  
  private map: L.Map | null = null;
  private markersLayer: L.LayerGroup | null = null;
  isLoading = signal<boolean>(true);
  error = signal<string | null>(null);
  mapData = signal<any>(null);

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    // Fix Leaflet default icon issue with Angular
    try {
      const iconRetinaUrl = 'marker-icon-2x.png';
      const iconUrl = 'marker-icon.png';
      const shadowUrl = 'marker-shadow.png';
      const iconDefault = L.icon({
        iconRetinaUrl,
        iconUrl,
        shadowUrl,
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        tooltipAnchor: [16, -28],
        shadowSize: [41, 41]
      });
      L.Marker.prototype.options.icon = iconDefault;
    } catch (e) {
      console.warn('Could not set default Leaflet icon:', e);
    }
  }

  ngAfterViewInit(): void {
    // Delay map initialization to ensure DOM is ready
    setTimeout(() => {
      this.initMap();
      this.loadMapData();
    }, 100);
  }

  ngOnDestroy(): void {
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
  }

  private initMap(): void {
    try {
      // Initialize map centered on Los Altos de Jalisco region
      // Coordinates adjusted for better coverage of Los Altos municipalities
      this.map = L.map('map', {
        center: [20.85, -102.7],
        zoom: 10,
        zoomControl: true,
        scrollWheelZoom: true,
        maxBounds: [[19.5, -104.0], [22.0, -101.5]] // Restrict to Jalisco region
      });

      // Add OpenStreetMap tile layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 15,
        minZoom: 8,
        attribution: '© OpenStreetMap'
      }).addTo(this.map);

      // Initialize markers layer
      this.markersLayer = L.layerGroup().addTo(this.map);

      // Force map to invalidate size after initialization
      setTimeout(() => {
        if (this.map) {
          this.map.invalidateSize();
        }
      }, 200);
    } catch (error) {
      console.error('Error initializing map:', error);
      this.error.set('Error al inicializar el mapa');
      this.isLoading.set(false);
    }
  }

  private loadMapData(): void {
    if (!this.map) return;

    this.isLoading.set(true);
    this.error.set(null);

    // Build query parameters based on filters
    const params: any = {};
    if (this.selectedYear.length > 0) {
      params.year = this.selectedYear[0]; // Use first selected year
    }
    if (this.selectedMarca.length > 0) {
      params.marca = this.selectedMarca[0]; // Use first selected brand
    }
    if (this.selectedCondicion.length > 0) {
      params.condicion = this.selectedCondicion[0]; // Use first selected condition
    }

    this.apiService.getMapStatistics(params).subscribe({
      next: (data) => {
        this.mapData.set(data);
        this.updateMarkers(data);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Error loading map data:', err);
        this.error.set('Error al cargar datos del mapa');
        this.isLoading.set(false);
      }
    });
  }

  private updateMarkers(geoJsonData: any): void {
    if (!this.map || !this.markersLayer) return;

    // Clear existing markers
    this.markersLayer.clearLayers();

    if (!geoJsonData || !geoJsonData.features || geoJsonData.features.length === 0) {
      return;
    }

    // Calculate min and max for color scaling
    const lecheValues = geoJsonData.features.map((f: any) => f.properties.leche_ha);
    const minLeche = Math.min(...lecheValues);
    const maxLeche = Math.max(...lecheValues);

    // Add markers for each feature
    geoJsonData.features.forEach((feature: any) => {
      const coords = feature.geometry.coordinates;
      const props = feature.properties;

      // Calculate color based on milk production
      const color = this.getColorForValue(props.leche_ha, minLeche, maxLeche);

      // Create circle with size representing approximate municipality/city area
      // Uniform size with minimal variation to keep all circles proportional
      const baseRadiusMeters = 5000; // 5km base radius (municipality scale)
      // Cap the multiplier to prevent some circles from being too large
      const cappedCiclos = Math.min(props.total_ciclos, 10); // Max 10 cycles for size calculation
      const radiusMultiplier = 1 + (cappedCiclos * 0.03); // Small increment (3% per cycle)
      const finalRadius = baseRadiusMeters * radiusMultiplier;
      
      const marker = L.circle([coords[1], coords[0]], {
        radius: finalRadius, // radius in meters for geographic accuracy
        fillColor: color,
        color: color,
        weight: 1.5,
        opacity: 0.4,
        fillOpacity: 0.2
      });

      // Create popup content
      const popupContent = `
        <div class="map-popup">
          <h3 class="font-bold text-lg mb-2">${props.municipio}</h3>
          <p class="text-sm text-gray-600 mb-3">${props.estado}</p>
          <div class="space-y-1 text-sm">
            <div class="flex justify-between">
              <span class="font-semibold">Ciclos:</span>
              <span>${props.total_ciclos}</span>
            </div>
            <div class="flex justify-between">
              <span class="font-semibold">Leche/ha:</span>
              <span class="text-blue-600 font-bold">${props.leche_ha.toFixed(0)} kg</span>
            </div>
            <div class="flex justify-between">
              <span class="font-semibold">RMS Promedio:</span>
              <span>${props.avg_rms.toFixed(2)} t/ha</span>
            </div>
            <div class="flex justify-between">
              <span class="font-semibold">MS Promedio:</span>
              <span>${props.avg_ms.toFixed(2)}%</span>
            </div>
            <div class="flex justify-between">
              <span class="font-semibold">PC Promedio:</span>
              <span>${props.avg_pc.toFixed(2)}%</span>
            </div>
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      
      // Add tooltip
      marker.bindTooltip(`${props.municipio}: ${props.leche_ha.toFixed(0)} kg/ha`, {
        permanent: false,
        direction: 'top'
      });

      marker.addTo(this.markersLayer!);
    });

    // Fit map to markers bounds
    if (geoJsonData.features.length > 0) {
      const bounds = L.latLngBounds(
        geoJsonData.features.map((f: any) => [f.geometry.coordinates[1], f.geometry.coordinates[0]])
      );
      this.map!.fitBounds(bounds, { padding: [50, 50] });
    }
  }

  private getColorForValue(value: number, min: number, max: number): string {
    // Normalize value between 0 and 1
    const normalized = (value - min) / (max - min);
    
    // Color gradient from red (low) to yellow to green (high)
    if (normalized < 0.5) {
      // Red to Yellow
      const r = 255;
      const g = Math.round(255 * (normalized * 2));
      return `rgb(${r}, ${g}, 0)`;
    } else {
      // Yellow to Green
      const r = Math.round(255 * (1 - (normalized - 0.5) * 2));
      const g = 255;
      return `rgb(${r}, ${g}, 0)`;
    }
  }

  refreshMap(): void {
    this.loadMapData();
  }
}

// Made with Bob
