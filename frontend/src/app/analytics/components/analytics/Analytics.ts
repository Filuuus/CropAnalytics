import { Component, ChangeDetectionStrategy, OnInit, inject, signal, computed } from "@angular/core";
import { Router } from "@angular/router";
import { Header } from "../../../shared/components/header/Header";
import { Main } from "../main/Main";
import { Footer } from "../../../shared/components/footer/Footer";
import { ApiService } from "../../../services/api.service";
import { CommonModule } from "@angular/common";

export interface GroupedHibrido {
  hibrido_nombre: string;
  total_muestras: number;
  anos_estudiados: number[];
  ciclos_detalle: any[];
}

@Component({
  selector: "analytics",
  imports: [CommonModule, Header, Main, Footer],
  templateUrl: "./Analytics.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Analytics implements OnInit {
  private apiService = inject(ApiService);

  labConfig: { [key: string]: { label: string, unit: string } } = {
    ms: { label: 'Rendimiento Seco (MS)', unit: '%' },
    pc: { label: 'Proteína Cruda (PC)', unit: '%' },
    gc: { label: 'Grasa/Ext. Etéreo (GC)', unit: '%' },
    cen: { label: 'Cenizas (CEN)', unit: '%' },
    fdn: { label: 'Fibra D.N. (FDN)', unit: '%' },
    cnf: { label: 'Carbohidratos (CNF)', unit: '%' },
    pem: { label: 'Peso Específico (PEM)', unit: ' kg/hl' },
    pff: { label: 'PFF', unit: '' },
    dff: { label: 'DFF', unit: '%' },
    ucaff: { label: 'UCAFF', unit: '' },
    npc: { label: 'NPC', unit: '' },
    ppc: { label: 'PPC', unit: '%' },
    rmf: { label: 'RMF', unit: '' },
    rms: { label: 'RMS', unit: '' }
  };

  // Data Signals
  terrenos = signal<any[]>([]);
  ciclos = signal<any[]>([]);

  // Derived Filter Options
  estadoMunicipioOptions = computed(() => {
    // Unique pairs of "Estado - Municipio"
    const map = new Map<string, number[]>();
    for (const t of this.terrenos()) {
      const info = t.properties?.municipio_info;
      if (info) {
        const label = `${info.estado_nombre} - ${info.nombre}`;
        if (!map.has(label)) {
          map.set(label, []);
        }
        map.get(label)!.push(t.id);
      }
    }

    return Array.from(map.entries()).map(([label, ids]) => ({
      label,
      terrenoIds: ids
    })).sort((a, b) => a.label.localeCompare(b.label));
  });

  aniosDisponibles = computed(() => {
    const years = new Set(this.ciclos().map(c => c.year).filter(y => y != null));
    return Array.from(years).sort((a, b) => b - a);
  });

  marcasDisponibles: string[] = [];
  condicionesDisponibles: string[] = [];

  // Dropdown UI States
  locationDropdownOpen = signal<boolean>(false);
  yearDropdownOpen = signal<boolean>(false);
  marcaDropdownOpen = signal<boolean>(false);
  condicionDropdownOpen = signal<boolean>(false);

  // State Signals (Multi-select)
  selectedLocation = signal<{ label: string, terrenoIds: number[] }[]>([]);
  selectedYear = signal<number[]>([]);
  selectedMarca = signal<string[]>([]);
  selectedCondicion = signal<string[]>([]);
  searchTerm = signal<string>('');

  // Expansion, Collapse and Selection map for Hierarchical Accordion
  collapsedMarcas = signal<Set<string>>(new Set());
  expandedHybrids = signal<Set<string>>(new Set());
  expandedRows = signal<Set<number>>(new Set());
  selectedCiclosIds = signal<Set<number>>(new Set());
  hibridoSortOption = signal<'alphabetical' | 'rms_desc'>('alphabetical');
  precioLeche = signal<number>(10.50);

  actualizarPrecioLeche(event: Event) {
    const inputElement = event.target as HTMLInputElement;
    const value = parseFloat(inputElement.value);
    if (!isNaN(value) && value > 0) {
      this.precioLeche.set(value);
    }
  }

  calcularLecheHa(ciclo: any): number {
    const lab = ciclo.laboratorio_info;
    if (!lab) return 0;
    
    // Ecuaciones de Wisconsin Milk2024 adaptadas al frontend de forma simple
    const ms = lab.ms || 35.0;
    const cp = lab.pc || 8.5;
    const ee = lab.gc || 3.2;
    const ash = lab.cen || 4.0;
    const ndf = lab.fdn || 42.0;
    const starch = lab.cnf || 30.0;
    const rms = lab.rms || 20.0; // rms es el rendimiento de materia seca en t/ha
    
    // Constantes estándar de Wisconsin MILK2024
    const ndfd = 58.0;
    const undf240 = 15.0;
    const starch_d = 75.0;

    const fa = Math.max(0.0, ee - 1.0);
    const d_fa = fa * 0.73;
    const rom = Math.max(0.0, 100.0 - (ash + ndf + starch + fa + cp));
    const d_rom = rom * 0.91;
    const d_cp = cp * 0.70;
    const d_starch = starch * (starch_d / 100.0);
    const d_ndf_rumen = ndf * (ndfd / 100.0);
    const remanente_fibra_digestible = Math.max(0.0, ndf - d_ndf_rumen - undf240);
    const d_ndf = d_ndf_rumen + (remanente_fibra_digestible * 0.10);

    const tdn = d_cp + d_rom + (d_fa * 2.25) + d_starch + d_ndf;
    const de = (tdn / 100.0) * 4.409;
    const nel = Math.max(0.0, (0.703 * de) - 0.19);
    const leche_ton = (nel * 311.4) + 120.0;
    return leche_ton * rms;
  }

  // Computed Properties
  filteredCiclos = computed(() => {
    let c = this.ciclos();

    const marcas = this.selectedMarca();
    const locs = this.selectedLocation();
    const years = this.selectedYear();
    const conds = this.selectedCondicion();

    c = c.filter(ciclo => {
      let match = true;

      if (marcas.length > 0) {
        match = match && marcas.includes(ciclo.hibrido_marca);
      }

      if (locs.length > 0) {
        const isLocMatch = locs.some(l => l.terrenoIds.includes(ciclo.terreno));
        match = match && isLocMatch;
      }

      if (years.length > 0) {
        match = match && years.includes(ciclo.year);
      }

      if (conds.length > 0) {
        match = match && conds.includes(ciclo.condicion);
      }

      return match;
    });

    // Filter by Search Term (checking Marca, Híbrido, or Año)
    const term = this.searchTerm().toLowerCase().trim();
    if (term) {
      c = c.filter(ciclo => {
        const hName = ciclo.hibrido_nombre ? ciclo.hibrido_nombre.toLowerCase() : '';
        const hMarca = (ciclo.hibrido_marca && ciclo.hibrido_marca.trim() !== '') 
          ? ciclo.hibrido_marca.toLowerCase() 
          : 'sin marca registrada';
        const cYear = ciclo.year ? String(ciclo.year) : '';
        return hName.includes(term) || hMarca.includes(term) || cYear.includes(term);
      });
    }

    return c;
  });

  groupedHierarchy = computed(() => {
    const cycles = this.filteredCiclos() || [];
    const sortOpt = this.hibridoSortOption();
    
    const grouped = cycles.reduce((acc: any, ciclo: any) => {
      const marca = (ciclo.hibrido_marca && ciclo.hibrido_marca.trim() !== '') 
        ? ciclo.hibrido_marca 
        : 'Sin Marca Registrada';
      const hibrido = ciclo.hibrido_nombre || 'Desconocido';
      
      if (!acc[marca]) {
        acc[marca] = {};
      }
      if (!acc[marca][hibrido]) {
        acc[marca][hibrido] = [];
      }
      acc[marca][hibrido].push(ciclo);
      return acc;
    }, {});
    
    const result = Object.keys(grouped).map(marcaName => {
      const hibridosMap = grouped[marcaName];
      const hibridos = Object.keys(hibridosMap).map(hibridoName => {
        const cyclesList = hibridosMap[hibridoName];
        
        // Calculate average RMS for this hybrid to allow sorting by RMS
        const validRmsValues = cyclesList.map((c: any) => c.laboratorio_info?.rms).filter((v: any) => typeof v === 'number');
        const avgRms = validRmsValues.length > 0 
          ? validRmsValues.reduce((sum: number, val: number) => sum + val, 0) / validRmsValues.length 
          : 0;

        return {
          hibrido_nombre: hibridoName,
          avg_rms: avgRms,
          ciclos: cyclesList.sort((a: any, b: any) => b.year - a.year)
        };
      });

      // Sort hybrids within brand based on selector option
      if (sortOpt === 'rms_desc') {
        hibridos.sort((a: any, b: any) => b.avg_rms - a.avg_rms);
      } else {
        hibridos.sort((a: any, b: any) => a.hibrido_nombre.localeCompare(b.hibrido_nombre));
      }
      
      return {
        marca: marcaName,
        hibridos: hibridos
      };
    }).sort((a: any, b: any) => a.marca.localeCompare(b.marca));
    
    return result;
  });

  groupedHibridos = computed<GroupedHibrido[]>(() => {
    const filtered = this.filteredCiclos();
    const groupsMap = new Map<string, any[]>();

    filtered.forEach(ciclo => {
      const name = ciclo.hibrido_nombre || 'Desconocido';
      if (!groupsMap.has(name)) {
        groupsMap.set(name, []);
      }
      groupsMap.get(name)!.push(ciclo);
    });

    const result: GroupedHibrido[] = Array.from(groupsMap.entries()).map(([name, detail]) => {
      const uniqueYears = Array.from(new Set(detail.map(d => d.year))).sort((a, b) => b - a);
      return {
        hibrido_nombre: name,
        total_muestras: detail.length,
        anos_estudiados: uniqueYears,
        ciclos_detalle: detail
      };
    });

    result.sort((a, b) => a.hibrido_nombre.localeCompare(b.hibrido_nombre));

    return result;
  });

  selectedCiclosObjects = computed(() => {
    const all = this.ciclos();
    const selectedIds = this.selectedCiclosIds();
    return all.filter(c => selectedIds.has(c.id));
  });

  constructor(private router: Router) { }

  ngOnInit() {
    this.apiService.getTerrenos().subscribe({
      next: (data) => {
        console.log('Terrenos:', data);
        this.terrenos.set(data.features || data);
      },
      error: (error) => console.error('Error al obtener Terrenos:', error)
    });

    this.apiService.getCiclos().subscribe({
      next: (data) => {
        console.log('Ciclos:', data);
        const ciclosArray = data.results ? data.results : (Array.isArray(data) ? data : [data]);
        this.ciclos.set(ciclosArray);
        this.marcasDisponibles = Array.from(new Set(ciclosArray.map((c: any) => c.hibrido_marca).filter((m: any) => m))).sort((a: any, b: any) => a.localeCompare(b)) as string[];
        this.condicionesDisponibles = Array.from(new Set(ciclosArray.map((c: any) => c.condicion).filter((c: any) => c))).sort((a: any, b: any) => a.localeCompare(b)) as string[];
      },
      error: (error) => console.error('Error al obtener Ciclos:', error)
    });
  }

  // Interaction Methods
  toggleDropdown(dropdown: 'location' | 'year' | 'marca' | 'condicion') {
    if (dropdown === 'location') this.locationDropdownOpen.update(v => !v);
    if (dropdown === 'year') this.yearDropdownOpen.update(v => !v);
    if (dropdown === 'marca') this.marcaDropdownOpen.update(v => !v);
    if (dropdown === 'condicion') this.condicionDropdownOpen.update(v => !v);
  }

  toggleLocationSelection(option: { label: string, terrenoIds: number[] }) {
    const current = this.selectedLocation();
    const exists = current.find(l => l.label === option.label);
    if (exists) {
      this.selectedLocation.set(current.filter(l => l.label !== option.label));
    } else {
      this.selectedLocation.set([...current, option]);
    }
  }

  toggleYearSelection(year: number) {
    const current = this.selectedYear();
    if (current.includes(year)) {
      this.selectedYear.set(current.filter(y => y !== year));
    } else {
      this.selectedYear.set([...current, year]);
    }
  }

  toggleMarcaSelection(marca: string) {
    const current = this.selectedMarca();
    if (current.includes(marca)) {
      this.selectedMarca.set(current.filter(m => m !== marca));
    } else {
      this.selectedMarca.set([...current, marca]);
    }
  }

  toggleCondicionSelection(cond: string) {
    const current = this.selectedCondicion();
    if (current.includes(cond)) {
      this.selectedCondicion.set(current.filter(c => c !== cond));
    } else {
      this.selectedCondicion.set([...current, cond]);
    }
  }

  isLocSelected(label: string): boolean {
    return this.selectedLocation().some(l => l.label === label);
  }

  isYearSelected(year: number): boolean {
    return this.selectedYear().includes(year);
  }

  isMarcaSelected(marca: string): boolean {
    return this.selectedMarca().includes(marca);
  }

  isCondicionSelected(cond: string): boolean {
    return this.selectedCondicion().includes(cond);
  }

  limpiarFiltros() {
    this.selectedLocation.set([]);
    this.selectedYear.set([]);
    this.selectedMarca.set([]);
    this.selectedCondicion.set([]);
    this.searchTerm.set('');
  }

  onSearch(event: Event) {
    const inputElement = event.target as HTMLInputElement;
    this.searchTerm.set(inputElement.value);
  }

  limpiarBusqueda() {
    this.searchTerm.set('');
  }

  getValidLabMetrics(labInfo: any) {
    if (!labInfo) return [];
    const excludedKeys = ['id', 'ciclo', 'metodologia'];
    return Object.keys(labInfo)
      .filter(key => !excludedKeys.includes(key) && labInfo[key] !== null && labInfo[key] !== undefined && labInfo[key] !== '')
      .map(key => {
        const config = this.labConfig[key] || { label: key.toUpperCase(), unit: '' };
        return {
          key,
          label: config.label,
          unit: config.unit,
          value: labInfo[key]
        };
      });
  }

  limpiarSelecciones() {
    this.selectedCiclosIds.set(new Set<number>());
  }

  enfocarEnTabla(hibrido_nombre: string) {
    const cycle = this.filteredCiclos().find((c: any) => c.hibrido_nombre === hibrido_nombre);
    if (!cycle) return;
    const marca = (cycle.hibrido_marca && cycle.hibrido_marca.trim() !== '') ? cycle.hibrido_marca : 'Sin Marca Registrada';

    // Expand Marca by removing from collapsedMarcas
    const collapsedM = new Set(this.collapsedMarcas());
    if (collapsedM.has(marca)) {
      collapsedM.delete(marca);
      this.collapsedMarcas.set(collapsedM);
    }

    // Expand Hybrid by adding to expandedHybrids
    const key = `${marca}::${hibrido_nombre}`;
    const expandedH = new Set(this.expandedHybrids());
    expandedH.add(key);
    this.expandedHybrids.set(expandedH);

    // Select the cycles of this hybrid
    this.toggleHibridoSelection(marca, hibrido_nombre);
  }

  hibridosSeleccionados = computed(() => {
    const selectedIds = this.selectedCiclosIds();
    if (selectedIds.size === 0) return [];

    const hybMap = new Map<string, any>();

    // Group all globally matched cycles that are specifically selected
    this.groupedHibridos().forEach(h => {
      const selectedCyclesOfHybrid = h.ciclos_detalle.filter((c: any) => selectedIds.has(c.id));
      if (selectedCyclesOfHybrid.length > 0) {
        hybMap.set(h.hibrido_nombre, { ...h, selected_ciclos: selectedCyclesOfHybrid });
      }
    });

    const result: any[] = [];
    hybMap.forEach((hyb, nombre) => {
      const statsAccumulator: any = {};
      const metrics = Object.keys(this.labConfig);

      hyb.selected_ciclos.forEach((c: any) => {
        const lab = c.laboratorio_info;
        if (lab) {
          metrics.forEach(m => {
            if (typeof lab[m] === 'number') {
              if (!statsAccumulator[m]) statsAccumulator[m] = { sum: 0, count: 0 };
              statsAccumulator[m].sum += lab[m];
              statsAccumulator[m].count++;
            }
          });
        }
      });

      const promedio: any = {};
      metrics.forEach(m => {
        const s = statsAccumulator[m];
        promedio[m] = s && s.count > 0 ? (s.sum / s.count).toFixed(2) : '--';
      });

      result.push({ ...hyb, promedio });
    });


    return result;
  });

  toggleSeleccion(hibridoInput: any) {
    if (typeof hibridoInput === 'number') {
      this.toggleRowSelection(hibridoInput);
      return;
    }

    const nombre = hibridoInput.hibrido_nombre || hibridoInput.hibrido || hibridoInput;
    if (typeof nombre === 'string') {
      const cycle = this.filteredCiclos().find((c: any) => c.hibrido_nombre === nombre);
      if (cycle) {
        const marca = (cycle.hibrido_marca && cycle.hibrido_marca.trim() !== '') ? cycle.hibrido_marca : 'Sin Marca Registrada';
        this.toggleHibridoSelection(marca, nombre);
      }
    }
  }

  toggleHibridoSelection(marca: string, hibrido_nombre: string) {
    const brand = this.groupedHierarchy().find(b => b.marca === marca);
    if (!brand) return;
    const h = brand.hibridos.find((x: any) => x.hibrido_nombre === hibrido_nombre);
    if (!h) return;
    const current = new Set(this.selectedCiclosIds());
    const isSelected = h.ciclos.every((c: any) => current.has(c.id));
    h.ciclos.forEach((c: any) => {
      if (isSelected) {
        current.delete(c.id);
      } else {
        current.add(c.id);
      }
    });
    this.selectedCiclosIds.set(current);
  }

  isHybridSelected(marca: string, hibrido_nombre: string): boolean {
    const brand = this.groupedHierarchy().find(b => b.marca === marca);
    if (!brand) return false;
    const h = brand.hibridos.find((x: any) => x.hibrido_nombre === hibrido_nombre);
    if (!h || h.ciclos.length === 0) return false;
    return h.ciclos.every((c: any) => this.selectedCiclosIds().has(c.id));
  }

  calcularHibridoLecheHa(hibrido: any): number {
    if (!hibrido || !hibrido.ciclos || hibrido.ciclos.length === 0) return 0;
    const sum = hibrido.ciclos.reduce((acc: number, c: any) => acc + this.calcularLecheHa(c), 0);
    return sum / hibrido.ciclos.length;
  }

  toggleRowSelection(id: number) {
    const selected = new Set(this.selectedCiclosIds());
    if (selected.has(id)) {
      selected.delete(id);
    } else {
      selected.add(id);
    }
    this.selectedCiclosIds.set(selected);
  }

  toggleRowExpansion(id: number, event: Event) {
    const target = event.target as HTMLElement;
    if (target.tagName.toLowerCase() === 'input' && target.getAttribute('type') === 'checkbox') {
      return;
    }

    const expanded = new Set(this.expandedRows());
    if (expanded.has(id)) {
      expanded.delete(id);
    } else {
      expanded.add(id);
    }
    this.expandedRows.set(expanded);
  }

  toggleMarcaExpansion(marca: string) {
    const collapsed = new Set(this.collapsedMarcas());
    if (collapsed.has(marca)) {
      collapsed.delete(marca);
    } else {
      collapsed.add(marca);
    }
    this.collapsedMarcas.set(collapsed);
  }

  toggleHierarchyHybridExpansion(marca: string, hibrido: string) {
    const key = `${marca}::${hibrido}`;
    const expanded = new Set(this.expandedHybrids());
    if (expanded.has(key)) {
      expanded.delete(key);
    } else {
      expanded.add(key);
    }
    this.expandedHybrids.set(expanded);
  }

  isMarcaExpanded(marca: string): boolean {
    return !this.collapsedMarcas().has(marca);
  }

  isHierarchyHybridExpanded(marca: string, hibrido: string): boolean {
    return this.expandedHybrids().has(`${marca}::${hibrido}`);
  }

  toggleAllExpansionState() {
    const allExpanded = this.collapsedMarcas().size === 0;
    if (allExpanded) {
      const brandNames = new Set<string>();
      this.groupedHierarchy().forEach(brandGroup => {
        brandNames.add(brandGroup.marca);
      });
      this.collapsedMarcas.set(brandNames);
    } else {
      this.collapsedMarcas.set(new Set<string>());
    }
  }

  get areAllHierarchyNodesExpanded(): boolean {
    return this.collapsedMarcas().size === 0;
  }

  toggleMarcaSelectionInHierarchy(hibridos: any[], event: Event) {
    const isChecked = (event.target as HTMLInputElement).checked;
    const currentSelected = new Set(this.selectedCiclosIds());
    
    hibridos.forEach(h => {
      h.ciclos.forEach((c: any) => {
        if (isChecked) {
          currentSelected.add(c.id);
        } else {
          currentSelected.delete(c.id);
        }
      });
    });
    
    this.selectedCiclosIds.set(currentSelected);
  }

  isMarcaSelectedInHierarchy(hibridos: any[]): boolean {
    if (hibridos.length === 0) return false;
    return hibridos.every(h => h.ciclos.every((c: any) => this.selectedCiclosIds().has(c.id)));
  }

  toggleHybridSelectionInHierarchy(hibridoCiclos: any[], event: Event) {
    const isChecked = (event.target as HTMLInputElement).checked;
    const currentSelected = new Set(this.selectedCiclosIds());
    
    hibridoCiclos.forEach(c => {
      if (isChecked) {
        currentSelected.add(c.id);
      } else {
        currentSelected.delete(c.id);
      }
    });
    
    this.selectedCiclosIds.set(currentSelected);
  }

  isHybridSelectedInHierarchy(hibridoCiclos: any[]): boolean {
    if (hibridoCiclos.length === 0) return false;
    return hibridoCiclos.every(c => this.selectedCiclosIds().has(c.id));
  }

  toggleAllSelection(event: Event) {
    const isChecked = (event.target as HTMLInputElement).checked;
    const currentSelected = new Set(this.selectedCiclosIds());

    this.filteredCiclos().forEach(c => {
      if (isChecked) {
        currentSelected.add(c.id);
      } else {
        currentSelected.delete(c.id);
      }
    });

    this.selectedCiclosIds.set(currentSelected);
  }

  isRowExpanded(id: number): boolean {
    return this.expandedRows().has(id);
  }

  isRowSelected(id: number): boolean {
    return this.selectedCiclosIds().has(id);
  }

  get isAllFilteredSelected(): boolean {
    const filtered = this.filteredCiclos();
    if (filtered.length === 0) return false;
    return filtered.every(c => this.selectedCiclosIds().has(c.id));
  }
}
