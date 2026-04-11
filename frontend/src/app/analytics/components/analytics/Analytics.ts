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

  // Pagination
  currentPage = signal<number>(1);
  pageSize = signal<number>(10);

  // Sorting
  sortColumn = signal<string>('hibrido_nombre');
  sortDirection = signal<'asc' | 'desc'>('asc');

  // Expansion and Selection map
  expandedHybrids = signal<Set<string>>(new Set());
  expandedRows = signal<Set<number>>(new Set());
  selectedCiclosIds = signal<Set<number>>(new Set());

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

    // Filter by Search Term
    const term = this.searchTerm().toLowerCase();
    if (term) {
      c = c.filter(ciclo => {
        const hName = ciclo.hibrido_nombre ? ciclo.hibrido_nombre.toLowerCase() : '';
        const hMarca = ciclo.hibrido_marca ? ciclo.hibrido_marca.toLowerCase() : '';
        return hName.includes(term) || hMarca.includes(term);
      });
    }

    return c;
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

    // Apply sorting to hybrids
    const col = this.sortColumn();
    const dir = this.sortDirection() === 'asc' ? 1 : -1;

    result.sort((a: any, b: any) => {
      let valA = a[col];
      let valB = b[col];
      
      if (valA == null) valA = '';
      if (valB == null) valB = '';

      if (typeof valA === 'string' && typeof valB === 'string') {
        return valA.localeCompare(valB) * dir;
      }
      return (valA < valB ? -1 : (valA > valB ? 1 : 0)) * dir;
    });

    return result;
  });

  paginatedHibridos = computed(() => {
    const grouped = this.groupedHibridos();
    const start = (this.currentPage() - 1) * this.pageSize();
    return grouped.slice(start, start + this.pageSize());
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
    this.currentPage.set(1);
  }

  toggleYearSelection(year: number) {
    const current = this.selectedYear();
    if (current.includes(year)) {
      this.selectedYear.set(current.filter(y => y !== year));
    } else {
      this.selectedYear.set([...current, year]);
    }
    this.currentPage.set(1);
  }

  toggleMarcaSelection(marca: string) {
    const current = this.selectedMarca();
    if (current.includes(marca)) {
      this.selectedMarca.set(current.filter(m => m !== marca));
    } else {
      this.selectedMarca.set([...current, marca]);
    }
    this.currentPage.set(1);
  }

  toggleCondicionSelection(cond: string) {
    const current = this.selectedCondicion();
    if (current.includes(cond)) {
      this.selectedCondicion.set(current.filter(c => c !== cond));
    } else {
      this.selectedCondicion.set([...current, cond]);
    }
    this.currentPage.set(1);
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
    this.currentPage.set(1);
  }

  onSearch(event: Event) {
    const inputElement = event.target as HTMLInputElement;
    this.searchTerm.set(inputElement.value);
    this.currentPage.set(1);
  }

  limpiarBusqueda() {
    this.searchTerm.set('');
    this.currentPage.set(1);
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

  toggleSort(column: string) {
    if (this.sortColumn() === column) {
      this.sortDirection.set(this.sortDirection() === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set('asc');
    }
    this.currentPage.set(1);
  }

  limpiarSelecciones() {
    this.selectedCiclosIds.set(new Set<number>());
  }

  toggleHybridExpansion(name: string) {
    const expanded = new Set(this.expandedHybrids());
    if (expanded.has(name)) {
      expanded.delete(name);
    } else {
      expanded.add(name);
    }
    this.expandedHybrids.set(expanded);
  }

  enfocarEnTabla(hibrido_nombre: string) {
    const expanded = new Set(this.expandedHybrids());
    if (!expanded.has(hibrido_nombre)) {
      expanded.add(hibrido_nombre);
      this.expandedHybrids.set(expanded);
    }
    
    setTimeout(() => {
      const element = document.getElementById('row-' + hibrido_nombre);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // highlight briefly
        element.style.transition = 'background-color 0.5s';
        element.style.backgroundColor = '#e8f5e9'; // light green
        setTimeout(() => element.style.backgroundColor = '', 1500);
      }
    }, 100);
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
       let msSum = 0, pcSum = 0, fdnSum = 0, cnfSum = 0;
       let msCount = 0, pcCount = 0, fdnCount = 0, cnfCount = 0;

       hyb.selected_ciclos.forEach((c: any) => {
         const lab = c.laboratorio_info;
         if (lab) {
           if (typeof lab.ms === 'number') { msSum += lab.ms; msCount++; }
           if (typeof lab.pc === 'number') { pcSum += lab.pc; pcCount++; }
           if (typeof lab.fdn === 'number') { fdnSum += lab.fdn; fdnCount++; }
           if (typeof lab.cnf === 'number') { cnfSum += lab.cnf; cnfCount++; }
         }
       });

       const promedio = {
         ms: msCount > 0 ? (msSum / msCount).toFixed(2) : '--',
         pc: pcCount > 0 ? (pcSum / pcCount).toFixed(2) : '--',
         fdn: fdnCount > 0 ? (fdnSum / fdnCount).toFixed(2) : '--',
         cnf: cnfCount > 0 ? (cnfSum / cnfCount).toFixed(2) : '--'
       };
       
       result.push({ ...hyb, promedio });
    });
    
    return result;
  });

  toggleSeleccion(hibridoInput: any) {
    const nombre = hibridoInput.hibrido_nombre || hibridoInput.hibrido || hibridoInput;
    const hibrido = this.groupedHibridos().find((h: any) => h.hibrido_nombre === nombre);
    if (!hibrido) return;

    const isFullySelected = hibrido.ciclos_detalle.every((c: any) => this.selectedCiclosIds().has(c.id));
    const current = new Set(this.selectedCiclosIds());

    hibrido.ciclos_detalle.forEach((c: any) => {
      if (isFullySelected) {
        current.delete(c.id);
      } else {
        current.add(c.id);
      }
    });
    
    this.selectedCiclosIds.set(current);
  }

  toggleRowExpansion(id: number, event: Event) {
    // Only expand if clicking outside of the checkbox column
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

  toggleRowSelection(id: number) {
    const selected = new Set(this.selectedCiclosIds());
    if (selected.has(id)) {
      selected.delete(id);
    } else {
      selected.add(id);
    }
    this.selectedCiclosIds.set(selected);
  }

  toggleHybridSelection(grouped: GroupedHibrido, event: Event) {
    const isChecked = (event.target as HTMLInputElement).checked;
    const currentSelected = new Set(this.selectedCiclosIds());
    
    grouped.ciclos_detalle.forEach(c => {
      if (isChecked) {
        currentSelected.add(c.id);
      } else {
        currentSelected.delete(c.id);
      }
    });
    
    this.selectedCiclosIds.set(currentSelected);
  }

  isHybridSelected(grouped: GroupedHibrido): boolean {
    if (grouped.ciclos_detalle.length === 0) return false;
    return grouped.ciclos_detalle.every(c => this.selectedCiclosIds().has(c.id));
  }

  isHybridExpanded(name: string): boolean {
    return this.expandedHybrids().has(name);
  }

  isRowExpanded(id: number): boolean {
    return this.expandedRows().has(id);
  }

  isRowSelected(id: number): boolean {
    return this.selectedCiclosIds().has(id);
  }

  toggleAllSelection(event: Event) {
    const isChecked = (event.target as HTMLInputElement).checked;
    const currentSelected = new Set(this.selectedCiclosIds());
    
    this.paginatedHibridos().forEach(h => {
      h.ciclos_detalle.forEach(c => {
        if (isChecked) {
          currentSelected.add(c.id);
        } else {
          currentSelected.delete(c.id);
        }
      });
    });
    
    this.selectedCiclosIds.set(currentSelected);
  }

  get isAllCurrentPageSelected(): boolean {
    const page = this.paginatedHibridos();
    if (page.length === 0) return false;
    return page.every(h => this.isHybridSelected(h));
  }

  // Pagination Methods
  get totalItems() {
    return this.groupedHibridos().length;
  }

  get totalPages() {
    return Math.ceil(this.totalItems / this.pageSize()) || 1;
  }

  nextPage() {
    if (this.currentPage() < this.totalPages) {
      this.currentPage.update(p => p + 1);
    }
  }

  prevPage() {
    if (this.currentPage() > 1) {
      this.currentPage.update(p => p - 1);
    }
  }
}
