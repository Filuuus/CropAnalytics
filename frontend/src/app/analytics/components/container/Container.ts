import { Component, input, ChangeDetectionStrategy } from "@angular/core";

@Component({
  selector: "container",

  imports: [],
  templateUrl: "./Container.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Container {
  /** Value props */
  plotA = input<string>("");
  northFieldAMaizeXG2 = input<string>("");
}
