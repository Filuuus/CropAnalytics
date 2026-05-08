import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Header } from '../../shared/components/header/Header';
import { Footer } from '../../shared/components/footer/Footer';
import { FormConfigService } from '../services/form-config.service';
import { AuthService } from '../../auth/services/auth.service';

@Component({
  selector: 'app-investigador',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, Header, Footer],
  templateUrl: './investigador.component.html',
  styleUrls: ['../styles_upload.css']
})
export class InvestigadorComponent implements OnInit {

  form!: FormGroup;
  fields: any[] = [];

  constructor(
    private fb: FormBuilder,
    private service: FormConfigService,
    private router: Router,
    public authService: AuthService
  ) {}

  ngOnInit(): void {
    this.service.config$.subscribe(config => {
      if (config) {
        this.fields = config.fields.filter(f => f.visible);
        this.buildForm();
      }
    });

    this.service.loadConfig('investigador');
  }

  switchToJefe() {
    this.router.navigate(['/captura/jefe']);
  }

  buildForm() {
    let group: any = {};

    this.fields.forEach(field => {
      group[field.key] = [
        '',
        field.required ? Validators.required : []
      ];
    });

    this.form = this.fb.group(group);
  }

  submit() {
    if (this.form.valid) {
      console.log("Datos a enviar:", this.form.value);
      this.service.saveRecord(this.form.value).subscribe({
        next: (res) => {
          console.log("Guardado:", res);
          alert("Registro guardado correctamente");
          this.form.reset();
        },
        error: (err) => {
          console.error("Error:", err);
          alert("Error al guardar");
        }
      });
    } else {
      this.form.markAllAsTouched();
    }
  }
}
