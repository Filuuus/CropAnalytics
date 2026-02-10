import { Component, input, ChangeDetectionStrategy } from "@angular/core";
import { CommonModule } from "@angular/common";

@Component({
  selector: "container1",

  imports: [CommonModule],
  templateUrl: "./Container1.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Container1 {
  /** Value props */
  averageYield = input<string>("");
  kgha = input<string>("");
  prop = input<string>("");
  prop1 = input<string>("");
  /** Style props */
  averageYieldFontSize = input<string | number | undefined>("");
  haFontSize = input<string | number | undefined>("");
  bFontSize = input<string | number | undefined>("");
  marginMinWidth = input<string | number | undefined>("");
  bFontSize1 = input<string | number | undefined>("");
  marginMinWidth1 = input<string | number | undefined>("");
  backgroundWidth = input<string | number | undefined>("");
  backgroundRight = input<string | number | undefined>("");
}
