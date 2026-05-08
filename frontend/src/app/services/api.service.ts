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
}
