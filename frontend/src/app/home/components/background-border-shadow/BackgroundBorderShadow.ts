import { Component, input, ChangeDetectionStrategy } from "@angular/core";
import { CommonModule } from "@angular/common";

@Component({
  selector: "background-border-shadow",

  imports: [CommonModule],
  templateUrl: "./BackgroundBorderShadow.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class BackgroundBorderShadow {
  /** Value props */
  container = input<string>("");
  interactiveMapAnalysis = input<string>("");
  visualizeAndSelectCropPlots = input<string>("");
  /** Style props */
  containerHeight = input<string | number | undefined>("");
  containerPadding = input<string | number | undefined>("");
  frameDivGap = input<string | number | undefined>("");
  interactiveMapAnalysisFontSize = input<string | number | undefined>("");
  containerWidth = input<string | number | undefined>("");
  visualizeAndSelectFontSize = input<string | number | undefined>("");
}
