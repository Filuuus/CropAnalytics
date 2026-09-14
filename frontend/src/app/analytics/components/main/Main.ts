import { Component, signal, computed, input, output, ChangeDetectionStrategy, ViewChild, viewChild, AfterViewInit, inject, ChangeDetectorRef, NgZone } from '@angular/core';
import { FormsModule } from '@angular/forms';


import { CommonModule } from '@angular/common';
import { PlotlyModule, PlotlyService } from 'angular-plotly.js';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as PlotlyJS from 'plotly.js-dist-min';

// Configuración de Plotly: En versiones recientes debemos usar PlotlyService
const plotlyLib = (PlotlyJS as any).default || PlotlyJS;
PlotlyService.setPlotly(plotlyLib);

import { BaseChartDirective } from 'ng2-charts';
import { ChartConfiguration, ChartData, ChartType, Chart } from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

import { toPng } from 'html-to-image';


Chart.register(annotationPlugin);


@Component({
  selector: 'main-1',
  imports: [CommonModule, BaseChartDirective, PlotlyModule, FormsModule],

  templateUrl: './Main.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[style.display]': "'contents'" },
})
export class Main implements AfterViewInit {
  private cdr = inject(ChangeDetectorRef);
  private zone = inject(NgZone);
  readonly chart = viewChild<HTMLCanvasElement>('dynamicChartCanvas');

  private lastHoveredPoint: any = null;
  private mouseDownPos = { x: 0, y: 0 };
  private mouseDownTime = 0;




  viewMode = signal<'productor' | 'investigador'>('productor');

  isMicroView = signal<boolean>(false);
  isLineGranular = signal<boolean>(false);


  // Signals para el Modo Investigador
  xAxis = signal<string>('rms');
  yAxis = signal<string>('cnf');
  zAxis = signal<string>('fdn');
  selectedMetrics = signal<string[]>(['ms']);
  metricsDropdownOpen = signal<boolean>(false);


  metricOptions = [
    { value: 'ms', label: 'Materia Seca (%)' },
    { value: 'pc', label: 'Proteína Cruda (%)' },
    { value: 'fdn', label: 'Fibra D.N. (%)' },
    { value: 'cnf', label: 'Almidón (CNF) (%)' },
    { value: 'gc', label: 'Grasa (GC) (%)' },
    { value: 'cen', label: 'Cenizas (CEN) (%)' },
    { value: 'pem', label: 'Peso Específico (PEM) (kg/hl)' },
    { value: 'pff', label: 'PFF' },
    { value: 'dff', label: 'DFF (%)' },
    { value: 'ucaff', label: 'UCAFF' },
    { value: 'npc', label: 'NPC' },
    { value: 'ppc', label: 'PPC (%)' },
    { value: 'rmf', label: 'RMF' },
    { value: 'rms', label: 'RMS' },
    { value: 'leche_ha', label: 'Producción Leche (kg/ha)' },
    { value: 'ingreso_ha', label: 'Ingreso Bruto ($/ha)' }
  ];

  availableMetricOptions = computed(() => {
    const cycles = this.filteredCiclos() || [];
    return this.metricOptions.filter(opt =>
      opt.value === 'leche_ha' ||
      opt.value === 'ingreso_ha' ||
      cycles.some(c => c.laboratorio_info?.[opt.value] != null)
    );
  });




  activeChartType = signal<ChartType>('radar');



  // Paleta de colores para híbridos y formas para condiciones
  private hybridColors: { [key: string]: string } = {
    'Dekalb': '#2563EB', 'Pioneer': '#0EA5E9', 'Nidera': '#16A34A', 'Stine': '#7C3AED', 'Desconocido': '#64748B'
  };
  private conditionShapes: { [key: string]: string } = {
    'Riego': 'rect', 'Temporal': 'circle', 'Secano': 'triangle'
  };

  private metricColors: { [key: string]: string } = {
    ms: '#2563EB', pc: '#0EA5E9', fdn: '#F59E0B', cnf: '#7C3AED',
    gc: '#DB2777', cen: '#475569', pem: '#EA580C', pff: '#0F766E',
    dff: '#16A34A', ucaff: '#65A30D', npc: '#D97706', ppc: '#92400E',
    rmf: '#8B5CF6', rms: '#0284C7',
    leche_ha: '#3B82F6', ingreso_ha: '#10B981'
  };

  ngAfterViewInit() {
    // Triggers a layout recalculation on Plotly once the component views and CSS are fully rendered
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 150);
  }


  selectedCiclos = input<any[]>([]);
  filteredCiclos = input<any[]>([]); // Data for the static chart
  hibridosSeleccionados = input<any[]>([]);
  precioLeche = input<number>(10.50);

  hybridToggled = output<any>();
  clearSelection = output<void>();
  navigateHybrid = output<string>();

  // Ecuaciones de Wisconsin Milk2024 adaptadas al frontend de forma simple
  calcularLecheHa(ciclo: any): number {
    const lab = ciclo.laboratorio_info;
    if (!lab) return 0;
    
    const ms = lab.ms || 35.0;
    const cp = lab.pc || 8.5;
    const ee = lab.gc || 3.2;
    const ash = lab.cen || 4.0;
    const ndf = lab.fdn || 42.0;
    const starch = lab.cnf || 30.0;
    const rms = lab.rms || 20.0; // rms es el rendimiento de materia seca en t/ha
    
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

  // Group selected cycles by hybrid and compute consolidations
  selectedHybridsData = computed(() => {
    const selected = this.selectedCiclos() || [];
    if (selected.length === 0) return [];

    // Group selected cycles by hybrid name
    const groups = new Map<string, any[]>();
    selected.forEach(c => {
      const name = c.hibrido_nombre || 'Desconocido';
      const list = groups.get(name) || [];
      list.push(c);
      groups.set(name, list);
    });

    const result: any[] = [];
    groups.forEach((cycles, hibrido_nombre) => {
      let totalRms = 0;
      let totalLeche = 0;
      let validRmsCount = 0;
      let validLecheCount = 0;

      cycles.forEach(c => {
        const rms = c.laboratorio_info?.rms;
        if (rms != null && typeof rms === 'number') {
          totalRms += rms;
          validRmsCount++;
        }
        const leche = this.calcularLecheHa(c);
        if (leche != null && typeof leche === 'number') {
          totalLeche += leche;
          validLecheCount++;
        }
      });

      const avgRms = validRmsCount > 0 ? totalRms / validRmsCount : 0;
      const avgLeche = validLecheCount > 0 ? totalLeche / validLecheCount : 0;
      const rmsKg = avgRms * 1000;
      const ingreso = avgLeche * this.precioLeche();

      result.push({
        hibrido_nombre,
        rmsKg,
        leche: avgLeche,
        ingreso
      });
    });

    return result;
  });

  // Dynamic A/B comparison and opportunity cost engine
  comparison = computed(() => {
    const list = this.selectedHybridsData();
    const count = list.length;

    if (count === 0) {
      return {
        mode: 'empty',
        hibridoA: null,
        hibridoB: null,
        deltaRmsKg: 0,
        deltaLeche: 0,
        deltaIngreso: 0
      };
    }

    if (count === 1) {
      return {
        mode: 'single',
        hibridoA: list[0],
        hibridoB: null,
        deltaRmsKg: 0,
        deltaLeche: 0,
        deltaIngreso: 0
      };
    }

    let hibridoA: any;
    let hibridoB: any;
    let modeText = 'comparison';

    if (count === 2) {
      if (list[0].ingreso >= list[1].ingreso) {
        hibridoA = list[0];
        hibridoB = list[1];
      } else {
        hibridoA = list[1];
        hibridoB = list[0];
      }
      modeText = 'ab';
    } else {
      // Find Mejor and Peor by ingreso
      let mejor = list[0];
      let peor = list[0];

      list.forEach(h => {
        if (h.ingreso > mejor.ingreso) {
          mejor = h;
        }
        if (h.ingreso < peor.ingreso) {
          peor = h;
        }
      });

      hibridoA = mejor;
      hibridoB = peor;
      modeText = 'best_worst';
    }

    // Mathematical safety: force always positive delta (Ganador - Perdedor)
    const deltaRmsKg = Math.abs(hibridoA.rmsKg - hibridoB.rmsKg);
    const deltaLeche = Math.abs(hibridoA.leche - hibridoB.leche);
    const deltaIngreso = Math.abs(hibridoA.ingreso - hibridoB.ingreso);

    return {
      mode: modeText,
      hibridoA,
      hibridoB,
      deltaRmsKg,
      deltaLeche,
      deltaIngreso
    };
  });

  kpiList = [];

  showHeatmap = signal<boolean>(false);

  toggleHeatmap() {
    this.showHeatmap.update(v => !v);
  }

  toggleGranularity() {
    this.isMicroView.update(v => !v);
  }

  toggleMetric(value: string) {
    const current = this.selectedMetrics();
    if (current.includes(value)) {
      if (current.length > 1) {
        this.selectedMetrics.set(current.filter(m => m !== value));
      }
    } else {
      this.selectedMetrics.set([...current, value]);
    }
  }



  public scatterChartOptions = computed<ChartConfiguration['options']>(() => {
    const show = this.showHeatmap();
    return {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: {
            display: true,
            text: 'Rendimiento Materia Seca (RMS t/ha)',
            color: '#4B5563',
            font: { weight: 'bold' },
          },
          grid: { color: '#E5E7EB' },
          ticks: { color: '#6B7280' },
        },
        y: {
          title: {
            display: true,
            text: 'Carbohidratos No Fibrosos (CNF %)',
            color: '#4B5563',
            font: { weight: 'bold' },
          },
          grid: { color: '#E5E7EB' },
          ticks: { color: '#6B7280' },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            label: (context) => {
              const index = context.dataIndex;
              const dataPoint = context.dataset.data[index] as any;
              return `Híbrido: ${dataPoint.hibrido} | RMS: ${dataPoint.x} t/ha | CNF: ${dataPoint.y}%`;
            },
          },
        },
        annotation: show ? {
          annotations: {
            box1: {
              type: 'box',
              xMin: 20,
              yMin: 33,
              backgroundColor: 'rgba(76, 175, 80, 0.1)',
              borderWidth: 0,
            },
            box2: {
              type: 'box',
              xMax: 20,
              yMax: 33,
              backgroundColor: 'rgba(244, 67, 54, 0.1)',
              borderWidth: 0,
            },
            box3: {
              type: 'box',
              xMin: 20,
              yMax: 33,
              backgroundColor: 'rgba(255, 193, 7, 0.1)',
              borderWidth: 0,
            },
            box4: {
              type: 'box',
              xMax: 20,
              yMin: 33,
              backgroundColor: 'rgba(255, 152, 0, 0.1)',
              borderWidth: 0,
            }
          }
        } : undefined
      },
      interaction: {
        mode: 'nearest',
        axis: 'xy',
        intersect: false,
      },
      onClick: (e, elements, chart) => {
        if (elements && elements.length > 0) {
          const index = elements[0].index;
          const datasetIndex = elements[0].datasetIndex;
          const dataPoint = chart.data.datasets[datasetIndex].data[index] as any;
          if (dataPoint) {
            // Selección Granular: Si es micro, emitimos el ID de la entrada específica
            const selection = this.isMicroView() ? (dataPoint.id || dataPoint.hibrido) : dataPoint.hibrido;
            this.hybridToggled.emit(selection);
          }
        }
      },

    };
  });

  public scatterChartType: ChartType = 'scatter';

  public scatterChartData = computed<ChartData<'scatter'>>(() => {
    const ciclos = this.filteredCiclos() || [];
    const isMicro = this.isMicroView();
    let newData: any[] = [];
    const bgColors: string[] = [];
    const pointStyles: string[] = [];
    const pointRadii: number[] = [];

    if (isMicro) {
      // VISTA MICRO: Cada ciclo es un punto individual
      const selectedSet = new Set(this.selectedCiclos().map(c => c.id));
      ciclos.forEach(c => {
        const lab = c.laboratorio_info;
        if (lab?.rms != null && lab?.cnf != null) {
          newData.push({
            x: lab.rms,
            y: lab.cnf,
            hibrido: c.hibrido_nombre || 'Desconocido',
            id: c.id, // ID para selección granular específica
            condicion: c.condicion || 'Temporal'
          });
          const isSelected = selectedSet.has(c.id);
          const baseColor = this.hybridColors[c.hibrido_nombre] || '#2563EB';
          bgColors.push(isSelected ? '#EAB308' : baseColor);
          pointStyles.push(this.conditionShapes[c.condicion] || 'circle');
          pointRadii.push(isSelected ? 10 : 6);
        }
      });
    } else {
      // VISTA MACRO: Promedios por híbrido
      const selectedHybrids = new Set(this.selectedCiclos().map(c => c.hibrido_nombre));
      const stats = new Map<string, { rmsSum: number; cnfSum: number; count: number }>();
      ciclos.forEach(c => {
        const lab = c.laboratorio_info;
        if (lab?.rms != null && lab?.cnf != null) {
          const name = c.hibrido_nombre || 'Desconocido';
          const s = stats.get(name) || { rmsSum: 0, cnfSum: 0, count: 0 };
          s.rmsSum += lab.rms;
          s.cnfSum += lab.cnf;
          s.count++;
          stats.set(name, s);
        }
      });

      stats.forEach((s, name) => {
        newData.push({
          x: Number((s.rmsSum / s.count).toFixed(2)),
          y: Number((s.cnfSum / s.count).toFixed(2)),
          hibrido: name
        });
        const isSelected = selectedHybrids.has(name);
        const baseColor = this.hybridColors[name] || '#2563EB';
        bgColors.push(isSelected ? '#EAB308' : baseColor);
        pointStyles.push('circle');
        pointRadii.push(isSelected ? 12 : 8);
      });
    }

    return {
      datasets: [{
        data: newData,
        label: 'Híbridos',
        pointBackgroundColor: bgColors,
        pointStyle: pointStyles as any,
        pointRadius: pointRadii,
        pointHoverRadius: 12
      }]
    };
  });

  // Computed para el modo investigador (Plotly 3D)
  public plotlyData = computed(() => {
    const ciclos = this.filteredCiclos() || [];
    const selected = this.selectedCiclos() || [];
    const selectedIds = new Set(selected.map(c => c.id));
    const hasSelection = selectedIds.size > 0;

    const xKey = this.xAxis();
    const yKey = this.yAxis();
    const zKey = this.zAxis();

    const xData: number[] = [];
    const yData: number[] = [];
    const zData: number[] = [];
    const colors: string[] = [];
    const texts: string[] = [];
    const customData: any[] = [];

    ciclos.forEach(c => {
      const lab = c.laboratorio_info;
      if (lab) {
        const getVal = (key: string): number | null => {
          if (key === 'leche_ha') {
            return this.calcularLecheHa(c);
          }
          if (key === 'ingreso_ha') {
            return this.calcularLecheHa(c) * this.precioLeche();
          }
          return lab[key] !== undefined ? lab[key] : null;
        };

        const valX = getVal(xKey);
        const valY = getVal(yKey);
        const valZ = getVal(zKey);

        if (valX !== null && valY !== null && valZ !== null) {
          xData.push(valX);
          yData.push(valY);
          zData.push(valZ);

          const isSelected = selectedIds.has(c.id);
          const baseColor = this.hybridColors[c.hibrido_nombre] || '#2563EB';

          if (hasSelection) {
            colors.push(isSelected ? '#10B981' : 'rgba(74, 85, 104, 0.25)');
          } else {
            colors.push(baseColor);
          }

          texts.push(`${c.hibrido_nombre} (${c.year})`);
          customData.push(c.id);
        }
      }
    });

    return [{
      x: xData,
      y: yData,
      z: zData,
      text: texts,
      customdata: customData,
      mode: 'markers',
      type: 'scatter3d',
      marker: {
        size: 5,
        color: colors,
        opacity: 0.8
      }
    }];
  });

  public plotlyLayout = computed(() => {
    const xLabel = this.metricOptions.find(m => m.value === this.xAxis())?.label;
    const yLabel = this.metricOptions.find(m => m.value === this.yAxis())?.label;
    const zLabel = this.metricOptions.find(m => m.value === this.zAxis())?.label;

    return {
      autosize: true,
      margin: { t: 0, b: 0, l: 0, r: 0 },
      scene: {
        xaxis: { title: xLabel },
        yaxis: { title: yLabel },
        zaxis: { title: zLabel },
      },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#6B7280' }
    };
  });

  toggleRowSelection(id: number) {
    this.hybridToggled.emit(id);
  }

  onPlotlyClick(event: any) {
    if (event && event.points && event.points[0]) {
      const hibridoId = event.points[0].customdata;
      if (hibridoId !== undefined && hibridoId !== null) {
        this.zone.run(() => {
          this.toggleRowSelection(hibridoId);
        });
      }
    }
  }

  onPlotlyHover(event: any) {
    if (event && event.points && event.points[0]) {
      this.lastHoveredPoint = event.points[0];
    }
  }

  onPlotlyUnhover(event: any) {
    this.lastHoveredPoint = null;
  }

  onMouseDown(event: MouseEvent) {
    this.mouseDownPos = { x: event.clientX, y: event.clientY };
    this.mouseDownTime = performance.now();
  }

  onMouseUp(event: MouseEvent) {
    const timeDiff = performance.now() - this.mouseDownTime;
    const dx = event.clientX - this.mouseDownPos.x;
    const dy = event.clientY - this.mouseDownPos.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    // If mouse moved less than 6 pixels and released within 300ms, treat as click
    if (dist < 6 && timeDiff < 300) {
      if (this.lastHoveredPoint) {
        const hibridoId = this.lastHoveredPoint.customdata;
        if (hibridoId !== undefined && hibridoId !== null) {
          this.zone.run(() => {
            this.toggleRowSelection(hibridoId);
          });
        }
      }
    }
  }

  // Slot Dinámico 2D
  public dynamicChartData = computed<ChartData>(() => {
    const seleccionados = this.hibridosSeleccionados() || [];
    const type = this.activeChartType();

    if (type === 'radar') {
      const metrics = [
        { key: 'ms', label: 'M.S.' },
        { key: 'pc', label: 'P.C.' },
        { key: 'fdn', label: 'F.D.N.' },
        { key: 'cnf', label: 'CNF' },
        { key: 'gc', label: 'Grasa' },
        { key: 'cen', label: 'Cenizas' }
      ];

      const datasets = seleccionados.slice(0, 3).map(sel => ({
        label: sel.hibrido_nombre,
        data: metrics.map(m => sel.promedio[m.key] || 0),
        borderColor: this.hybridColors[sel.hibrido_nombre] || '#2563EB',
        backgroundColor: (this.hybridColors[sel.hibrido_nombre] || '#2563EB') + '33',
      }));
      return {
        labels: metrics.map(m => m.label),
        datasets
      };
    }

    if (type === 'line') {
      if (seleccionados.length === 0) return { labels: [], datasets: [] };

      const allCycles = (this.filteredCiclos() || []).filter(c =>
        seleccionados.some(s => s.hibrido_nombre === c.hibrido_nombre)
      );

      const isGranular = this.isLineGranular();
      let labels: string[] = [];

      if (isGranular) {
        // Vista Granular: Todos los ciclos ordenados cronológicamente (año) y por ID
        const sortedAll = [...allCycles].sort((a, b) => (a.year - b.year) || (a.id - b.id));
        // Generamos etiquetas únicas que incluyan el ID para evitar colisiones
        labels = sortedAll.map(c => `${c.year}-ID${c.id}`);
      } else {
        // Vista Promedio: Solo años únicos
        const uniqueYears = [...new Set(allCycles.map(c => c.year))].sort((a, b) => a - b);
        labels = uniqueYears.map(y => y.toString());
      }

      const metrics = this.selectedMetrics();
      const datasets: any[] = [];

      seleccionados.forEach(hyb => {
        const hybCycles = allCycles.filter(c => c.hibrido_nombre === hyb.hibrido_nombre);

        metrics.forEach(m => {
          const opt = this.metricOptions.find(o => o.value === m);
          const color = metrics.length > 1 ? (this.metricColors[m] || '#64748B') : (this.hybridColors[hyb.hibrido_nombre] || '#2563EB');

          let data: (number | null)[] = [];

          if (isGranular) {
            data = labels.map(label => {
              const id = parseInt(label.split('-ID')[1]);
              const match = hybCycles.find(c => c.id === id);
              if (!match) return null;
              if (m === 'leche_ha') {
                return this.calcularLecheHa(match);
              }
              if (m === 'ingreso_ha') {
                return this.calcularLecheHa(match) * this.precioLeche();
              }
              return match?.laboratorio_info?.[m] ?? null;
            });
          } else {
            data = labels.map(yearStr => {
              const year = parseInt(yearStr);
              const matches = hybCycles.filter(c => c.year === year);
              if (matches.length === 0) return null;
              const validValues = matches
                .map(c => {
                  if (m === 'leche_ha') {
                    return this.calcularLecheHa(c);
                  }
                  if (m === 'ingreso_ha') {
                    return this.calcularLecheHa(c) * this.precioLeche();
                  }
                  return c.laboratorio_info?.[m];
                })
                .filter(v => v != null && typeof v === 'number');
              
              if (validValues.length === 0) return null;
              return validValues.reduce((a, b) => a + b, 0) / validValues.length;
            });
          }

          datasets.push({
            label: isGranular ? `${opt?.label || m} (${hyb.hibrido_nombre})` : `Prom. ${opt?.label || m} (${hyb.hibrido_nombre})`,
            data: data,
            borderColor: color,
            backgroundColor: color + '22',
            pointBackgroundColor: color,
            borderDash: seleccionados.indexOf(hyb) > 0 ? [5, 5] : [],
            tension: 0.3,
            fill: false,
            spanGaps: false,
            pointRadius: isGranular ? 4 : 6,
          });
        });
      });

      return { labels, datasets };
    }



    if (type === 'bar') {
      const metrics = this.selectedMetrics();

      return {
        labels: seleccionados.map(s => s.hibrido_nombre),
        datasets: metrics.map(m => {
          const opt = this.metricOptions.find(o => o.value === m);
          return {
            label: opt?.label || m,
            data: seleccionados.map(s => {
              if (m === 'leche_ha' || m === 'ingreso_ha') {
                const cycles = s.selected_ciclos || s.ciclos || [];
                if (cycles.length === 0) return null;
                const vals = cycles.map((c: any) => {
                  if (m === 'leche_ha') return this.calcularLecheHa(c);
                  return this.calcularLecheHa(c) * this.precioLeche();
                });
                return vals.reduce((a: number, b: number) => a + b, 0) / vals.length;
              }
              return s.promedio[m] !== '--' && s.promedio[m] !== undefined ? parseFloat(s.promedio[m]) : null;
            }),
            backgroundColor: this.metricColors[m] || '#9E9E9E'
          };
        })
      };
    }


    return { labels: [], datasets: [] };
  });


  public dynamicChartOptions = computed<ChartConfiguration['options']>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { usePointStyle: true } }
    },
    layout: {
      padding: {
        bottom: 45
      }
    },
    animation: false,
    scales: this.activeChartType() !== 'radar' ? {
      y: { beginAtZero: true },
      x: {
        type: 'category',
        ticks: {
          autoSkip: false,
          maxRotation: 45,
          minRotation: 45
        }
      }
    } : undefined
  }));


  descargarGrafica2D(canvasEl?: HTMLCanvasElement) {
    const canvas = canvasEl || document.querySelector('.vista-investigador canvas') as HTMLCanvasElement;
    if (!canvas) {
      console.warn('No se encontró el canvas de la gráfica 2D.');
      return;
    }

    const chartImg = this.procesarImagenFondoBlanco(canvas);
    const link = document.createElement('a');
    link.href = chartImg;
    link.download = `Sentineli_Analisis_${this.activeChartType()}.png`;
    link.click();
  }

  private procesarImagenFondoBlanco(canvas: HTMLCanvasElement): string {
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvas.width;
    tempCanvas.height = canvas.height;
    const ctx = tempCanvas.getContext('2d', { willReadFrequently: true });
    if (ctx) {
      ctx.fillStyle = '#ffffff'; // Blanco puro para reportes
      ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
      ctx.drawImage(canvas, 0, 0);
      return tempCanvas.toDataURL('image/png', 1.0);
    }
    return canvas.toDataURL('image/png', 1.0);
  }






  selectedLocation = input<any[]>([]);
  selectedYear = input<number[]>([]);
  selectedMarca = input<string[]>([]);
  selectedCondicion = input<string[]>([]);
  searchTerm = input<string>('');

  async exportarPDF(canvasEl?: HTMLCanvasElement) {
    // Capturamos el estado de la gráfica 2D de forma síncrona al inicio
    // para evitar que se limpie el buffer durante esperas asíncronas (como Plotly)
    const canvas = canvasEl || document.querySelector('.vista-investigador canvas') as HTMLCanvasElement;
    const chartImg2d = canvas ? this.procesarImagenFondoBlanco(canvas) : null;

    // 1. Configuración inicial del PDF (Landscape para espacio extra)
    const pdf = new jsPDF('l', 'mm', 'a4');
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();

    // 2. Cabecera y Título
    pdf.setFontSize(22);
    pdf.setTextColor(46, 125, 50); // Verde Sentineli
    pdf.text('Reporte Analítico Sentineli', 15, 20);

    // 3. Metadatos de Filtros (Contexto Analítico)
    pdf.setFontSize(9);
    pdf.setTextColor(100, 100, 100);
    
    const rawLoc = this.selectedLocation().map(l => l.label).join(', ');
    const rawYear = this.selectedYear().join(', ');
    const rawMarca = this.selectedMarca().join(', ');
    const rawCond = this.selectedCondicion().join(', ');
    
    const filtroUbicacion = rawLoc && rawLoc !== 'Todas' ? rawLoc : 'Todas';
    const filtroAnio = rawYear && rawYear !== 'Todos' ? rawYear : 'Todos';
    const filtroMarca = rawMarca && rawMarca !== 'Todas' ? rawMarca : 'Todas';
    const filtroCondicion = rawCond && rawCond !== 'Todas' ? rawCond : 'Todas';
    const textoBusqueda = this.searchTerm();

    const filterContext = [
      `Ubicación: ${filtroUbicacion}`,
      `Año: ${filtroAnio}`,
      `Marca: ${filtroMarca}`,
      `Condición: ${filtroCondicion}`,
      `Búsqueda: ${textoBusqueda || 'Ninguna'}`
    ];
    pdf.text(filterContext.join('  |  '), 15, 28, { maxWidth: pageWidth - 30 });

    pdf.setDrawColor(230, 230, 230);
    pdf.line(15, 33, pageWidth - 15, 33);

    // Formateadores financieros y numéricos
    const formatCurrency = (val: number) => {
      if (!val || isNaN(val)) return '$0 MXN';
      return `$${Math.round(val).toLocaleString('es-MX')} MXN`;
    };
    const formatNumber = (val: number) => {
      if (!val || isNaN(val)) return '0 kg/ha';
      return `${Math.round(val).toLocaleString('es-MX')} kg/ha`;
    };

    try {
      // 4. Cálculos Financieros del Modelo MILK2024
      const calculatedData = this.hibridosSeleccionados().map(h => {
        const cycles = h.ciclos_detalle || [];
        let avgLeche = 0;
        let avgIngreso = 0;
        if (cycles.length > 0) {
          const totalLeche = cycles.reduce((sum: number, c: any) => sum + this.calcularLecheHa(c), 0);
          avgLeche = totalLeche / cycles.length;
          avgIngreso = avgLeche * this.precioLeche();
        }
        return {
          hibrido: h,
          avgLeche,
          avgIngreso
        };
      });

      let topPerformer = { hibrido_nombre: 'N/A', avgIngreso: 0 };
      let promedioGeneralIngreso = 0;

      if (calculatedData.length > 0) {
        const sorted = [...calculatedData].sort((a, b) => b.avgIngreso - a.avgIngreso);
        topPerformer = {
          hibrido_nombre: sorted[0].hibrido.hibrido_nombre,
          avgIngreso: sorted[0].avgIngreso
        };
        const totalIngreso = calculatedData.reduce((sum, item) => sum + item.avgIngreso, 0);
        promedioGeneralIngreso = totalIngreso / calculatedData.length;
      }

      // Renderizado del Resumen Ejecutivo (Tarjeta Visual)
      pdf.setFillColor(248, 250, 252); // bg-slate-50
      pdf.setDrawColor(226, 232, 240); // border-slate-200
      pdf.roundedRect(15, 37, pageWidth - 30, 20, 2, 2, 'FD');

      pdf.setFontSize(10);
      pdf.setTextColor(30, 41, 59); // slate-800
      pdf.setFont('helvetica', 'bold');
      pdf.text('RESUMEN DE INTELIGENCIA FINANCIERA (MODELO MILK2024)', 20, 43);

      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(9);
      pdf.setTextColor(71, 85, 105); // slate-600
      pdf.text('Híbrido Líder Financiero:', 20, 51);
      pdf.setFont('helvetica', 'bold');
      pdf.setTextColor(16, 185, 129); // emerald-500
      pdf.text(`${topPerformer.hibrido_nombre} (${formatCurrency(topPerformer.avgIngreso)})`, 60, 51);

      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(71, 85, 105);
      pdf.text('Promedio de Ingreso General de la Selección:', 140, 51);
      pdf.setFont('helvetica', 'bold');
      pdf.setTextColor(30, 41, 59);
      pdf.text(formatCurrency(promedioGeneralIngreso), 208, 51);

      // Restablecer fuentes para el resto del reporte
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(50, 50, 50);

      // 5. Captura Nativa de Plotly (3D) y Chart.js (2D) colocados lado a lado
      const plotlyEl = document.querySelector('plotly-plot .js-plotly-plot') as any;
      if (plotlyEl) {
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Distribución Multidimensional (3D):', 15, 67);
        pdf.setFont('helvetica', 'normal');

        const plotlyImg = await PlotlyJS.toImage(plotlyEl, {
          format: 'png',
          width: 1000,
          height: 750
        });
        pdf.addImage(plotlyImg, 'PNG', 15, 72, 125, 85);
        
        const labelX = this.metricOptions.find(m => m.value === this.xAxis())?.label || this.xAxis();
        const labelY = this.metricOptions.find(m => m.value === this.yAxis())?.label || this.yAxis();
        const labelZ = this.metricOptions.find(m => m.value === this.zAxis())?.label || this.zAxis();
        pdf.setFontSize(8.5);
        pdf.setTextColor(100, 100, 100);
        pdf.text(`Ejes 3D -> X: ${labelX} | Y: ${labelY} | Z: ${labelZ}`, 15, 162);
      }

      if (chartImg2d) {
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Análisis de Perfil Nutricional (2D):', 150, 67);
        pdf.setFont('helvetica', 'normal');
        pdf.addImage(chartImg2d, 'PNG', 150, 72, 132, 85);
      }

      // 6. Tabla de Datos Detallada (Página 2)
      pdf.addPage();
      pdf.setFontSize(18);
      pdf.setTextColor(46, 125, 50);
      pdf.text('Desglose de Datos Seleccionados', 15, 20);

      const rows = calculatedData.map(item => [
        item.hibrido.hibrido_nombre,
        item.hibrido.promedio.rms,
        item.hibrido.promedio.fdn + '%',
        item.hibrido.promedio.cnf + '%',
        formatNumber(item.avgLeche),
        formatCurrency(item.avgIngreso)
      ]);

      autoTable(pdf, {
        startY: 28,
        head: [['Híbrido', 'RMS (t/ha)', 'Fibra (FDN)', 'Almidón (CNF)', 'Leche (kg/ha)', 'Ingreso Bruto']],
        body: rows,
        theme: 'striped',
        headStyles: { fillColor: [30, 41, 59], halign: 'center' }, // Color gris pizarra corporativo
        columnStyles: {
          0: { fontStyle: 'bold' },
          1: { halign: 'center' },
          2: { halign: 'center' },
          3: { halign: 'center' },
          4: { halign: 'right' },
          5: { halign: 'right', fontStyle: 'bold', textColor: [16, 185, 129] } // Resaltado verde para Ingreso
        }
      });

      // 7. Pie de página y Guardado
      pdf.setFontSize(8);
      pdf.setTextColor(150, 150, 150);
      pdf.text('Sentineli Biological Intelligence - Confidencial', 15, pdf.internal.pageSize.getHeight() - 10);

      pdf.save('Sentineli_Reporte_Analitico.pdf');

    } catch (error) {
      console.error('Error detallado en exportarPDF:', error);
    }
  }
}

