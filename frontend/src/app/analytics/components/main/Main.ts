import { Component, signal, ChangeDetectionStrategy } from "@angular/core";
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
  container1Items = signal([
    {
      averageYield: "Average Yield",
      averageYieldFontSize: "0.831rem" as const,
      kgha: "kg/ha",
      haFontSize: "0.694rem" as const,
      prop: "85.2",
      bFontSize: "0.881rem" as const,
      marginMinWidth: "17.938rem" as const,
      prop1: "78.6",
      bFontSize1: "0.906rem" as const,
      marginMinWidth1: "17.875rem" as const,
      backgroundWidth: "92.25%" as const,
      backgroundRight: "7.75%" as const,
    },
    {
      averageYield: "Water Efficiency",
      averageYieldFontSize: "0.813rem" as const,
      kgha: "%",
      haFontSize: "0.75rem" as const,
      prop: "92.1",
      bFontSize: "0.975rem" as const,
      marginMinWidth: undefined,
      prop1: "88.3",
      bFontSize1: "0.875rem" as const,
      marginMinWidth1: undefined,
      backgroundWidth: "95.88%" as const,
      backgroundRight: "4.12%" as const,
    },
    {
      averageYield: "Growth Rate",
      averageYieldFontSize: undefined,
      kgha: "cm/day",
      haFontSize: "0.681rem" as const,
      prop: "1.2",
      bFontSize: "1rem" as const,
      marginMinWidth: "18.25rem" as const,
      prop1: "0.8",
      bFontSize1: "0.881rem" as const,
      marginMinWidth1: "18.25rem" as const,
      backgroundWidth: "66.67%" as const,
      backgroundRight: "33.33%" as const,
    },
  ]);
}
