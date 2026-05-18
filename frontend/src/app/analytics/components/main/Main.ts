import { Component, signal, computed, input, output, ChangeDetectionStrategy, ViewChild, viewChild } from '@angular/core';


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
  imports: [CommonModule, BaseChartDirective, PlotlyModule],

  templateUrl: './Main.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[style.display]': "'contents'" },
})
export class Main {
  readonly chart = viewChild<HTMLCanvasElement>('dynamicChartCanvas');




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
    { value: 'rms', label: 'RMS' }
  ];

  availableMetricOptions = computed(() => {
    const cycles = this.filteredCiclos() || [];
    return this.metricOptions.filter(opt =>
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
    rmf: '#8B5CF6', rms: '#0284C7'
  };


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
    const xKey = this.xAxis();
    const yKey = this.yAxis();
    const zKey = this.zAxis();

    const xData: number[] = [];
    const yData: number[] = [];
    const zData: number[] = [];
    const colors: string[] = [];
    const texts: string[] = [];

    ciclos.forEach(c => {
      const lab = c.laboratorio_info;
      if (lab && lab[xKey] != null && lab[yKey] != null && lab[zKey] != null) {
        xData.push(lab[xKey]);
        yData.push(lab[yKey]);
        zData.push(lab[zKey]);
        colors.push(this.hybridColors[c.hibrido_nombre] || '#2563EB');
        texts.push(`${c.hibrido_nombre} (${c.year})`);
      }
    });

    return [{
      x: xData,
      y: yData,
      z: zData,
      text: texts,
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
      height: 600,
      margin: { l: 0, r: 0, b: 0, t: 0 },
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
              return match?.laboratorio_info?.[m] ?? null;
            });
          } else {
            data = labels.map(yearStr => {
              const year = parseInt(yearStr);
              const matches = hybCycles.filter(c => c.year === year);
              if (matches.length === 0) return null;
              const validValues = matches
                .map(c => c.laboratorio_info?.[m])
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
            data: seleccionados.map(s => s.promedio[m] !== '--' ? parseFloat(s.promedio[m]) : null),
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
    animation: false,
    scales: this.activeChartType() !== 'radar' ? { y: { beginAtZero: true } } : undefined
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

    // 1. Configuración inicial del PDF (Portrait)

    const pdf = new jsPDF('p', 'mm', 'a4');
    const pageWidth = pdf.internal.pageSize.getWidth();

    // 2. Cabecera y Título
    pdf.setFontSize(22);
    pdf.setTextColor(46, 125, 50); // Verde Sentineli
    pdf.text('Reporte Analítico Sentineli', 15, 20);

    // 3. Metadatos de Filtros (Contexto Analítico)
    pdf.setFontSize(9);
    pdf.setTextColor(100, 100, 100);
    const filterContext = [
      `Ubicación: ${this.selectedLocation().map(l => l.label).join(', ') || 'Todas'}`,
      `Año: ${this.selectedYear().join(', ') || 'Todos'}`,
      `Marca: ${this.selectedMarca().join(', ') || 'Todas'}`,
      `Condición: ${this.selectedCondicion().join(', ') || 'Todas'}`,
      `Búsqueda: ${this.searchTerm() || 'Ninguna'}`
    ];
    pdf.text(filterContext.join('  |  '), 15, 28, { maxWidth: pageWidth - 30 });

    pdf.setDrawColor(230, 230, 230);
    pdf.line(15, 33, pageWidth - 15, 33);

    try {
      // 4. Captura Nativa de Plotly (3D)
      const plotlyEl = document.querySelector('plotly-plot .js-plotly-plot') as any;
      if (plotlyEl) {
        pdf.setFontSize(13);
        pdf.setTextColor(50, 50, 50);
        pdf.text('Distribución Multidimensional (3D):', 15, 42);

        const plotlyImg = await PlotlyJS.toImage(plotlyEl, {
          format: 'png',
          width: 1000,
          height: 750
        });
        pdf.addImage(plotlyImg, 'PNG', 15, 47, 180, 95);
      }

      // 5. Captura Segura de Chart.js (2D)
      if (chartImg2d) {
        pdf.text('Análisis de Perfil Nutricional (2D):', 15, 155);
        pdf.addImage(chartImg2d, 'PNG', 15, 160, 180, 90);
      }







      // 6. Tabla de Datos Detallada (Página 2)
      pdf.addPage();
      pdf.setFontSize(18);
      pdf.setTextColor(46, 125, 50);
      pdf.text('Desglose de Datos Seleccionados', 15, 20);

      const rows = this.hibridosSeleccionados().map(h => [
        h.hibrido_nombre,
        h.promedio.ms + '%',
        h.promedio.pc + '%',
        h.promedio.fdn + '%',
        h.promedio.cnf + '%'
      ]);

      autoTable(pdf, {
        startY: 30,
        head: [['Híbrido', 'MS', 'PC', 'FDN', 'Almidón (CNF)']],
        body: rows,
        theme: 'striped',
        headStyles: { fillColor: [46, 125, 50], halign: 'center' },
        columnStyles: {
          0: { fontStyle: 'bold' },
          1: { halign: 'center' }, 2: { halign: 'center' }, 3: { halign: 'center' }, 4: { halign: 'center' }
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

