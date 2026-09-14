import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Header } from '../../shared/components/header/Header';
import { Footer } from '../../shared/components/footer/Footer';
import { FormConfigService, Config, Field } from '../services/form-config.service';

@Component({
  selector: 'app-jefe',
  standalone: true,
  imports: [CommonModule, Header, Footer],
  templateUrl: './jefe.component.html',
  styleUrls: ['../styles_upload.css']
})
export class JefeComponent implements OnInit {

  config!: Config;

  constructor(
    private service: FormConfigService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.service.getConfig('investigador').subscribe(res => {
      if (res && res.length > 0) {
        this.config = res[0];
        this.service.setConfig(this.config);
      }
    });
  }

  switchToInvestigador() {
    this.router.navigate(['/captura/investigador']);
  }

  toggle(field: Field) {
    field.visible = !field.visible;
    this.save();
  }

  save() {
    this.service.updateConfig(this.config).subscribe(() => {
      this.service.setConfig(this.config);
    });
  }
}
