import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
    providedIn: 'root'
})
export class ApiService {
    private http = inject(HttpClient);

    private baseUrl = 'http://127.0.0.1:8000/api';

    getTerrenos(): Observable<any> {
        return this.http.get(`${this.baseUrl}/terrenos/`);
    }

    getCiclos(): Observable<any> {
        return this.http.get(`${this.baseUrl}/ciclos/`);
    }
}
