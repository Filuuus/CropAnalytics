import csv
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from api.ml.celdas import CELDAS_PATH, RADIO_MAX_KM, centro, fila_col, id_celda
from api.models import Terreno
from api.utils.geospatial_estimator import calcular_distancia_haversine

# Medio diagonal de un píxel de 9 km: con este margen, todo punto a menos de
# RADIO_MAX_KM de un ensayo cae en una celda incluida.
_MARGEN_KM = 6.5


class Command(BaseCommand):
    help = ('Genera las celdas SMAP de 9 km alrededor de los terrenos con ensayos '
            '(api/ml/celdas_altos.json) y el CSV de puntos para la solicitud en AppEEARS.')

    def handle(self, *args, **kwargs):
        ensayos = [(t.id, t.latitud_gps, t.longitud_gps)
                   for t in Terreno.objects.exclude(latitud_gps=0).exclude(longitud_gps=0)]
        if not ensayos:
            self.stderr.write('No hay terrenos con coordenadas.')
            return

        filas_cols = [fila_col(lat, lon) for _, lat, lon in ensayos]
        margen = int((RADIO_MAX_KM + _MARGEN_KM) // 9) + 1
        celdas = []
        for fila in range(min(f for f, _ in filas_cols) - margen, max(f for f, _ in filas_cols) + margen + 1):
            for col in range(min(c for _, c in filas_cols) - margen, max(c for _, c in filas_cols) + margen + 1):
                lat, lon = centro(fila, col)
                km, terreno_id = min((calcular_distancia_haversine(lat, lon, t_lat, t_lon), t_id)
                                     for t_id, t_lat, t_lon in ensayos)
                if km <= RADIO_MAX_KM + _MARGEN_KM:
                    celdas.append({'id': id_celda(fila, col), 'fila': fila, 'col': col,
                                   'lat': round(lat, 6), 'lon': round(lon, 6),
                                   'km_ensayo': round(km, 1), 'terreno_cercano': terreno_id})

        with open(CELDAS_PATH, 'w', encoding='utf-8') as fh:
            json.dump(celdas, fh, indent=1)

        puntos = settings.BASE_DIR / 'data' / 'appeears_puntos_altos.csv'
        with open(puntos, 'w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['ID', 'Category', 'Latitude', 'Longitude'])
            writer.writerows([c['id'], 'altos', c['lat'], c['lon']] for c in celdas)

        self.stdout.write(self.style.SUCCESS(
            f'{len(celdas)} celdas a partir de {len(ensayos)} terrenos -> {CELDAS_PATH.name} y {puntos.name}'
        ))
