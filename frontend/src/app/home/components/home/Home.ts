import { Component, signal, ChangeDetectionStrategy } from "@angular/core";
import { Router } from "@angular/router";
import { Header } from "../../../shared/components/header/Header";
import { BackgroundBorderShadow } from "../background-border-shadow/BackgroundBorderShadow";
import { Footer } from "../../../shared/components/footer/Footer";
import { CommonModule } from "@angular/common";

@Component({
  selector: "home",

  imports: [CommonModule, Header, BackgroundBorderShadow, Footer],
  templateUrl: "./Home.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Home {
  constructor(private router: Router) { }



  onGoToDashboardClick() {
    this.router.navigate(["/dashboard"]);
  }
  backgroundBorderShadowItems = signal([
    {
      containerHeight: "12.594rem" as const,
      containerPadding: "1.5rem 1.5rem 1.506rem" as const,
      container: "assets/images/Container.svg",
      frameDivGap: "0.462rem" as const,
      interactiveMapAnalysis: "Interactive Map Analysis",
      interactiveMapAnalysisFontSize: "1.081rem" as const,
      containerWidth: undefined,
      visualizeAndSelectCropPlots:
        "Visualize and select crop plots directly on an\ninteractive map interface for intuitive data exploration.",
      visualizeAndSelectFontSize: "0.8rem" as const,
    },
    {
      containerHeight: "14.019rem" as const,
      containerPadding: "1.5rem" as const,
      container: "assets/images/Container1.svg",
      frameDivGap: "0.456rem" as const,
      interactiveMapAnalysis: "Automated Calculations",
      interactiveMapAnalysisFontSize: undefined,
      containerWidth: "20.875rem" as const,
      visualizeAndSelectCropPlots:
        "Upload raw data and receive instant performance\nmetrics with advanced algorithms and real-time\nprocessing.",
      visualizeAndSelectFontSize: "0.813rem" as const,
    },
    {
      containerHeight: "14.019rem" as const,
      containerPadding: "1.5rem" as const,
      container: "assets/images/Container2.svg",
      frameDivGap: "0.456rem" as const,
      interactiveMapAnalysis: "Comparative Analytics",
      interactiveMapAnalysisFontSize: "1.088rem" as const,
      containerWidth: undefined,
      visualizeAndSelectCropPlots:
        "Generate comprehensive graphs to compare different\nseeds and plots side-by-side for informed decision\nmaking.",
      visualizeAndSelectFontSize: "0.813rem" as const,
    },
  ]);
}
