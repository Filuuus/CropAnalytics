import { Component, ChangeDetectionStrategy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Header } from "../../../shared/components/header/Header";
import { Footer } from "../../../shared/components/footer/Footer";

@Component({
  selector: "about",
  standalone: true,
  imports: [CommonModule, Header, Footer],
  templateUrl: "./About.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { "[style.display]": "'contents'" },
})
export class About {}
