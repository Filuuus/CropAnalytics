import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
    providedIn: 'root'
})
export class ApiService {
    private http = inject(HttpClient);

    private baseUrl = environment.apiUrl;

    getTerrenos(): Observable<any> {
        return this.http.get(`${this.baseUrl}/terrenos/`);
    }

    getCiclos(): Observable<any> {
        return this.http.get(`${this.baseUrl}/ciclos/`);
    }

    calcularMilk2024(datos: any): Observable<any> {
        return this.http.post(`${this.baseUrl}/calcular-milk2024/`, datos);
    }

    calcularProductor(datos: any): Observable<any> {
        return this.http.post(`${this.baseUrl}/calcular-productor/`, datos);
    }

    optimizarSemilla(datos: any): Observable<any> {
        return this.http.post(`${this.baseUrl}/optimizar-semilla/`, datos);
    }
}
