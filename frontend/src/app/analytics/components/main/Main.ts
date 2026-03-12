import { Component, signal, computed, input, output, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BaseChartDirective } from 'ng2-charts';
import { ChartConfiguration, ChartData, ChartType } from 'chart.js';

@Component({
  selector: 'main-1',
  imports: [CommonModule, BaseChartDirective],
  templateUrl: './Main.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[style.display]': "'contents'" },
})
export class Main {
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

  public scatterChartOptions: ChartConfiguration['options'] = {
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
        display: false, // Using custom title/header instead
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
        if (dataPoint && dataPoint.hibrido) {
          this.hybridToggled.emit(dataPoint.hibrido);
        }
      }
    },
  };

  public scatterChartType: ChartType = 'scatter';

  public scatterChartData = computed<ChartData<'scatter'>>(() => {
    const ciclos = this.filteredCiclos() || [];
    const hibridoStats = new Map<string, { msSum: number; pcSum: number; count: number }>();

    // 1. Agreegate valid values to calculate averages per Hybrid
    ciclos.forEach(c => {
      const lab = c.laboratorio_info;
      if (lab && lab.ms != null && lab.pc != null) {
        const name = c.hibrido_nombre || 'Desconocido';
        if (!hibridoStats.has(name)) {
          hibridoStats.set(name, { msSum: 0, pcSum: 0, count: 0 });
        }
        const stats = hibridoStats.get(name)!;
        stats.msSum += lab.ms;
        stats.pcSum += lab.pc;
        stats.count++;
      }
    });

    // 2. Generate Data Points
    const newData: { x: number; y: number; hibrido: string }[] = [];
    hibridoStats.forEach((stats, name) => {
      if (stats.count > 0) {
        newData.push({
          x: Number((stats.msSum / stats.count).toFixed(2)),
          y: Number((stats.pcSum / stats.count).toFixed(2)),
          hibrido: name
        });
      }
    });

    const seleccionados = this.hibridosSeleccionados() || [];
    const seleccionadosNombres = new Set(seleccionados.map(s => s.hibrido_nombre));

    const bgColors: string[] = [];
    const borderColors: string[] = [];
    const pointRadii: number[] = [];

    newData.forEach(point => {
      if (seleccionadosNombres.has(point.hibrido)) {
        bgColors.push('#FF5252');
        borderColors.push('#FF5252');
        pointRadii.push(8); // slightly larger when selected
      } else {
        bgColors.push('#2E7D32');
        borderColors.push('#fff');
        pointRadii.push(6);
      }
    });

    return {
      datasets: [
        {
          data: newData,
          label: 'Híbridos',
          pointBackgroundColor: bgColors,
          pointBorderColor: borderColors,
          pointHoverBackgroundColor: '#fff',
          pointHoverBorderColor: bgColors,
          pointRadius: pointRadii,
          pointHoverRadius: 9
        }
      ]
    };
  });
}
