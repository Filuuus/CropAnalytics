import { Component, signal, computed, input, ChangeDetectionStrategy } from "@angular/core";
import { Container } from "../container/Container";
import { Container1 } from "../container1/Container1";
import { CommonModule } from "@angular/common";

@Component({
  selector: "main-1",

  imports: [CommonModule, Container1],
  templateUrl: "./Main.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Main {
  selectedCiclos = input<any[]>([]);

  container1Items = computed(() => {
    const ciclos = this.selectedCiclos() || [];

    // Si no hay seleccionados, mostramos valores default ("--")
    if (ciclos.length === 0) {
      return [
        {
          averageYield: "Rendimiento Seco (ms)",
          averageYieldFontSize: "0.831rem" as const,
          kgha: "%",
          haFontSize: "0.694rem" as const,
          prop: "--",
          bFontSize: "0.881rem" as const,
          marginMinWidth: "17.938rem" as const,
          prop1: "--",
          bFontSize1: "0.906rem" as const,
          marginMinWidth1: "17.875rem" as const,
          backgroundWidth: "50%" as const,
          backgroundRight: "50%" as const,
        },
        {
          averageYield: "Proteína (pc)",
          averageYieldFontSize: "0.813rem" as const,
          kgha: "%",
          haFontSize: "0.75rem" as const,
          prop: "--",
          bFontSize: "0.975rem" as const,
          marginMinWidth: undefined,
          prop1: "--",
          bFontSize1: "0.875rem" as const,
          marginMinWidth1: undefined,
          backgroundWidth: "50%" as const,
          backgroundRight: "50%" as const,
        },
        {
          averageYield: "Extracto Etéreo (gc)",
          averageYieldFontSize: undefined,
          kgha: "%",
          haFontSize: "0.681rem" as const,
          prop: "--",
          bFontSize: "1rem" as const,
          marginMinWidth: "18.25rem" as const,
          prop1: "--",
          bFontSize1: "0.881rem" as const,
          marginMinWidth1: "18.25rem" as const,
          backgroundWidth: "50%" as const,
          backgroundRight: "50%" as const,
        },
      ];
    }

    // Calcular promedios
    let msSum = 0, pcSum = 0, gcSum = 0;
    let msCount = 0, pcCount = 0, gcCount = 0;

    ciclos.forEach(c => {
      const lab = c.laboratorio_info;
      if (lab) {
        if (lab.ms != null) { msSum += lab.ms; msCount++; }
        if (lab.pc != null) { pcSum += lab.pc; pcCount++; }
        if (lab.gc != null) { gcSum += lab.gc; gcCount++; }
      }
    });

    const avgMs = msCount > 0 ? (msSum / msCount).toFixed(2) : "--";
    const avgPc = pcCount > 0 ? (pcSum / pcCount).toFixed(2) : "--";
    const avgGc = gcCount > 0 ? (gcSum / gcCount).toFixed(2) : "--";

    return [
      {
        averageYield: "Rendimiento Seco (ms)",
        averageYieldFontSize: "0.831rem" as const,
        kgha: "%",
        haFontSize: "0.694rem" as const,
        prop: avgMs,
        bFontSize: "0.881rem" as const,
        marginMinWidth: "17.938rem" as const,
        prop1: msCount > 0 ? (msSum / msCount * 0.95).toFixed(2) : "--", // Simulado (benchmark)
        bFontSize1: "0.906rem" as const,
        marginMinWidth1: "17.875rem" as const,
        backgroundWidth: "92.25%" as const,
        backgroundRight: "7.75%" as const,
      },
      {
        averageYield: "Proteína Cruda (pc)",
        averageYieldFontSize: "0.813rem" as const,
        kgha: "%",
        haFontSize: "0.75rem" as const,
        prop: avgPc,
        bFontSize: "0.975rem" as const,
        marginMinWidth: undefined,
        prop1: pcCount > 0 ? (pcSum / pcCount * 0.88).toFixed(2) : "--", // Simulado (benchmark)
        bFontSize1: "0.875rem" as const,
        marginMinWidth1: undefined,
        backgroundWidth: "95.88%" as const,
        backgroundRight: "4.12%" as const,
      },
      {
        averageYield: "Grasa / Extracto Etéreo (gc)",
        averageYieldFontSize: undefined,
        kgha: "%",
        haFontSize: "0.681rem" as const,
        prop: avgGc,
        bFontSize: "1rem" as const,
        marginMinWidth: "18.25rem" as const,
        prop1: gcCount > 0 ? (gcSum / gcCount * 1.1).toFixed(2) : "--", // Simulado (benchmark)
        bFontSize1: "0.881rem" as const,
        marginMinWidth1: "18.25rem" as const,
        backgroundWidth: "66.67%" as const,
        backgroundRight: "33.33%" as const,
      },
    ];
  });
}
