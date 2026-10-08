import json
from datetime import date

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.ml.celdas import cargar_celdas
from api.ml.ml_engine import _read_daymet_all, _read_smap_csv, estimar_humedad
from api.ml.panorama import resumir_celda
from api.models import PanoramaCelda


def _mas_reciente(patron):
    archivos = sorted((settings.BASE_DIR / 'data').glob(patron), key=lambda p: p.stat().st_mtime)
    return archivos[-1] if archivos else None


class Command(BaseCommand):
    help = ('Calcula el panorama de humedad de cada celda con los CSV de AppEEARS '
            '(SMAP + Daymet) y lo guarda en PanoramaCelda.')

    def add_arguments(self, parser):
        parser.add_argument('--smap', help='CSV de SMAP (por defecto el más reciente *SPL3SMP-E-006-results.csv en data/)')
        parser.add_argument('--daymet', help='CSV de Daymet (por defecto el más reciente *DAYMET-004-results.csv en data/)')
        parser.add_argument('--vista-previa', metavar='JSON',
                            help='No escribe en la base de datos; guarda el resultado en este archivo')

    def handle(self, *args, **opts):
        smap_path = opts['smap'] or _mas_reciente('*SPL3SMP-E-006-results.csv')
        daymet_path = opts['daymet'] or _mas_reciente('*DAYMET-004-results.csv')
        if not smap_path or not daymet_path:
            raise CommandError('Faltan los CSV de AppEEARS en backend/data/ (corre solicitar_appeears --descargar).')
        self.stdout.write(f'SMAP: {smap_path}\nDaymet: {daymet_path}')

        # ponytail: carga ambos CSV completos en memoria (~0.5 GB para 311 celdas x 11 años);
        # leer por bloques si el área crece mucho.
        smap = _read_smap_csv(str(smap_path))
        daymet = _read_daymet_all(str(daymet_path))
        celdas = cargar_celdas()

        resultados = {}
        for i, (celda_id, filas) in enumerate(sorted(smap.items()), 1):
            fechas_txt = [d for d, _ in filas]
            sm, modelo = estimar_humedad(fechas_txt, np.array([v for _, v in filas], dtype=np.float64),
                                         daymet.get(celda_id, {}))
            fechas = [date.fromisoformat(d) for d in fechas_txt]
            resultados[celda_id] = {
                'anio_inicio': fechas[0].year, 'anio_fin': fechas[-1].year, 'modelo': modelo,
                'resumen': resumir_celda(fechas, sm),
            }
            if i % 50 == 0:
                self.stdout.write(f'  {i}/{len(smap)} celdas')

        if opts['vista_previa']:
            with open(opts['vista_previa'], 'w', encoding='utf-8') as fh:
                json.dump(resultados, fh)
            self.stdout.write(self.style.SUCCESS(f'{len(resultados)} series -> {opts["vista_previa"]} (sin tocar la BD)'))
            return

        desconocidas = sorted(set(resultados) - set(celdas))
        if desconocidas:
            self.stderr.write(f'Se omiten {len(desconocidas)} IDs que no son celdas: {desconocidas[:5]}...')
        for celda_id in sorted(set(resultados) & set(celdas)):
            PanoramaCelda.objects.update_or_create(celda_id=celda_id, defaults=resultados[celda_id])
        self.stdout.write(self.style.SUCCESS(f'{len(set(resultados) & set(celdas))} celdas guardadas en PanoramaCelda.'))
