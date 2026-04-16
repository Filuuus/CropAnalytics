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

  // Signals para el Modo Investigador
  xAxis = signal<string>('ms');
  yAxis = signal<string>('pc');
  zAxis = signal<string>('fdn');
  barChartMetric = signal<string>('ms');

  metricOptions = [
    { value: 'ms', label: 'Materia Seca (%)' },
    { value: 'pc', label: 'Proteína Cruda (%)' },
    { value: 'fdn', label: 'Fibra D.N. (%)' },
    { value: 'cnf', label: 'Almidón (CNF) (%)' },
    { value: 'gc', label: 'Grasa (GC) (%)' },
    { value: 'cen', label: 'Cenizas (CEN) (%)' },
    { value: 'ppc', label: 'PPC (%)' }
  ];



  activeChartType = signal<ChartType>('radar');



  // Paleta de colores para híbridos y formas para condiciones
  private hybridColors: { [key: string]: string } = {
    'Dekalb': '#2E7D32', 'Pioneer': '#1976D2', 'Nidera': '#F57C00', 'Stine': '#7B1FA2', 'Desconocido': '#9E9E9E'
  };
  private conditionShapes: { [key: string]: string } = {
    'Riego': 'rect', 'Temporal': 'circle', 'Secano': 'triangle'
  };

  selectedCiclos = input<any[]>([]);

  filteredCiclos = input<any[]>([]); // Data for the static chart
  hibridosSeleccionados = input<any[]>([]);

  hybridToggled = output<any>();
  clearSelection = output<void>();
  navigateHybrid = output<string>();

  kpiList = [
    { key: 'ms', label: 'Rendimiento Seco (MS)', unit: '%' },
    { key: 'pc', label: 'Proteína Cruda (PC)', unit: '%' },
    { key: 'fdn', label: 'Fibra D.N. (FDN)', unit: '%' },
    { key: 'cnf', label: 'Carbohidratos (CNF)', unit: '%' }
  ];

  showHeatmap = signal<boolean>(false);

  toggleHeatmap() {
    this.showHeatmap.update(v => !v);
  }

  toggleGranularity() {
    this.isMicroView.update(v => !v);
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
            text: 'Rendimiento Seco (ms %)',
            color: '#4B5563',
            font: { weight: 'bold' },
          },
          grid: { color: '#E5E7EB' },
          ticks: { color: '#6B7280' },
        },
        y: {
          title: {
            display: true,
            text: 'Proteína Cruda (pc %)',
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
              return `Híbrido: ${dataPoint.hibrido} | MS: ${dataPoint.x}% | PC: ${dataPoint.y}%`;
            },
          },
        },
        annotation: show ? {
          annotations: {
            box1: {
              type: 'box',
              xMin: 40,
              yMin: 6.5,
              backgroundColor: 'rgba(76, 175, 80, 0.1)',
              borderWidth: 0,
            },
            box2: {
              type: 'box',
              xMax: 40,
              yMax: 6.5,
              backgroundColor: 'rgba(244, 67, 54, 0.1)',
              borderWidth: 0,
            },
            box3: {
              type: 'box',
              xMin: 40,
              yMax: 6.5,
              backgroundColor: 'rgba(255, 193, 7, 0.1)',
              borderWidth: 0,
            },
            box4: {
              type: 'box',
              xMax: 40,
              yMin: 6.5,
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
      ciclos.forEach(c => {
        const lab = c.laboratorio_info;
        if (lab?.ms != null && lab?.pc != null) {
          newData.push({
            x: lab.ms,
            y: lab.pc,
            hibrido: c.hibrido_nombre || 'Desconocido',
            id: c.id, // ID para selección granular específica
            condicion: c.condicion || 'Temporal'
          });
          bgColors.push(this.hybridColors[c.hibrido_nombre] || '#2E7D32');
          pointStyles.push(this.conditionShapes[c.condicion] || 'circle');
          pointRadii.push(6);
        }
      });
    } else {

      // VISTA MACRO: Promedios por híbrido
      const stats = new Map<string, { msSum: number; pcSum: number; count: number }>();
      ciclos.forEach(c => {
        const lab = c.laboratorio_info;
        if (lab?.ms != null && lab?.pc != null) {
          const name = c.hibrido_nombre || 'Desconocido';
          const s = stats.get(name) || { msSum: 0, pcSum: 0, count: 0 };
          s.msSum += lab.ms;
          s.pcSum += lab.pc;
          s.count++;
          stats.set(name, s);
        }
      });

      stats.forEach((s, name) => {
        newData.push({
          x: Number((s.msSum / s.count).toFixed(2)),
          y: Number((s.pcSum / s.count).toFixed(2)),
          hibrido: name
        });
        bgColors.push(this.hybridColors[name] || '#2E7D32');
        pointStyles.push('circle');
        pointRadii.push(8);
      });
    }

    return {
      datasets: [{
        data: newData,
        label: 'Híbridos',
        pointBackgroundColor: bgColors,
        pointStyle: pointStyles as any,
        pointRadius: pointRadii,
        pointHoverRadius: 10
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
        colors.push(this.hybridColors[c.hibrido_nombre] || '#2E7D32');
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
        borderColor: this.hybridColors[sel.hibrido_nombre] || '#2E7D32',
        backgroundColor: (this.hybridColors[sel.hibrido_nombre] || '#2E7D32') + '33',
      }));
      return {
        labels: metrics.map(m => m.label),
        datasets
      };
    }


    if (type === 'line') {
      const first = seleccionados[0];
      if (!first) return { labels: [], datasets: [] };

      const history = (this.filteredCiclos() || [])
        .filter(c => c.hibrido_nombre === first.hibrido_nombre)
        .sort((a, b) => a.year - b.year);

      const metric = this.barChartMetric();
      const metricLabel = this.metricOptions.find(o => o.value === metric)?.label || metric;

      return {
        labels: history.map(c => c.year.toString()),
        datasets: [{
          label: `${first.hibrido_nombre} - ${metricLabel}`,
          data: history.map(c => c.laboratorio_info?.[metric]),
          borderColor: this.hybridColors[first.hibrido_nombre] || '#1976D2',
          tension: 0.3,
          fill: true,
          backgroundColor: (this.hybridColors[first.hibrido_nombre] || '#1976D2') + '22'
        }]
      };
    }

    if (type === 'bar') {
      const metric = this.barChartMetric();
      const metricLabel = this.metricOptions.find(o => o.value === metric)?.label || metric;

      return {
        labels: seleccionados.map(s => s.hibrido_nombre),
        datasets: [{
          label: metricLabel,
          data: seleccionados.map(s => s.promedio[metric] || 0),
          backgroundColor: seleccionados.map(s => this.hybridColors[s.hibrido_nombre] || '#2E7D32')
        }]
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


