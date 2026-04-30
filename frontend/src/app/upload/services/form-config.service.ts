import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';

export interface Field {
  key: string;
  label: string;
  type: string;
  visible: boolean;
  required: boolean;
}

export interface Config {
  id: string;
  fields: Field[];
}

@Injectable({
  providedIn: 'root'
})
export class FormConfigService {
  private configSubject = new BehaviorSubject<Config | null>(null);
  config$ = this.configSubject.asObservable();

  constructor() {}

  getConfig(role: string): Observable<Config[]> {
    return of([]);
  }

  setConfig(config: Config): void {
    this.configSubject.next(config);
  }

  updateConfig(config: Config): Observable<any> {
    return of({});
  }

  loadConfig(role: string): void {
    // Mock load
  }

  saveRecord(data: any): Observable<any> {
    return of({ success: true });
  }
}
