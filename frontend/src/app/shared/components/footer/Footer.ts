import { Component, ChangeDetectionStrategy } from "@angular/core";

@Component({
  selector: "footer-1",

  imports: [],
  templateUrl: "./Footer.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class Footer {}
