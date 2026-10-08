import getpass
import json
import os
import time
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.ml.celdas import CELDAS_PATH

API = 'https://appeears.earthdatacloud.nasa.gov/api'

# SMAP L3 enhanced (misma versión con la que se entrenó el LSTM) y Daymet.
# El pase PM llena días sin dato AM; las banderas permiten filtrar por calidad.
CAPAS = [
    ('SPL3SMP_E.006', 'Soil_Moisture_Retrieval_Data_AM_soil_moisture'),
    ('SPL3SMP_E.006', 'Soil_Moisture_Retrieval_Data_AM_retrieval_qual_flag'),
    ('SPL3SMP_E.006', 'Soil_Moisture_Retrieval_Data_PM_soil_moisture_pm'),
    ('SPL3SMP_E.006', 'Soil_Moisture_Retrieval_Data_PM_retrieval_qual_flag_pm'),
    ('DAYMET.004', 'prcp'),
    ('DAYMET.004', 'tmax'),
    ('DAYMET.004', 'tmin'),
]

# AppEEARS limita los valores por solicitud (puntos x capas x días). Una solicitud de
# 8.55 millones se rechazó por exceder el máximo en 144.3 %, así que el límite ronda
# 3.5 millones; se usa 3 millones de margen.
MAX_VALORES = 3_000_000

DATA_DIR = Path(settings.BASE_DIR) / 'data'
TAREA_PATH = DATA_DIR / 'appeears_tarea.json'


def construir_tarea(celdas, inicio, fin, nombre, capas):
    """Solicitud de muestreo por puntos (una coordenada por celda) para la API de AppEEARS."""
    return {
        'task_type': 'point',
        'task_name': nombre,
        'params': {
            'dates': [{'startDate': inicio.strftime('%m-%d-%Y'), 'endDate': fin.strftime('%m-%d-%Y')}],
            'layers': [{'product': p, 'layer': capa} for p, capa in capas],
            'coordinates': [
                {'id': c['id'], 'category': 'altos', 'latitude': c['lat'], 'longitude': c['lon']}
                for c in celdas
            ],
        },
    }


def dividir_tareas(celdas, inicio, fin, nombre):
    """Una tarea por producto y tramo de fechas, cada una con a lo más MAX_VALORES valores."""
    tareas = []
    for producto in dict.fromkeys(p for p, _ in CAPAS):
        capas = [(p, c) for p, c in CAPAS if p == producto]
        dias = MAX_VALORES // (len(celdas) * len(capas))
        desde, parte = inicio, 1
        while desde <= fin:
            hasta = min(fin, desde + timedelta(days=dias - 1))
            tareas.append(construir_tarea(celdas, desde, hasta,
                                          f"{nombre}-{producto.split('.')[0]}-{parte}", capas))
            desde, parte = hasta + timedelta(days=1), parte + 1
    return tareas


def _clave_producto(nombre_archivo):
    """Parte del nombre de AppEEARS que identifica el producto en el CSV de resultados."""
    for clave in ('SPL3SMP-E-006', 'DAYMET-004'):
        if clave in nombre_archivo:
            return clave
    return None


class Command(BaseCommand):
    help = ('Envía a NASA AppEEARS la solicitud de SMAP + Daymet para las celdas de '
            'celdas_altos.json (dividida en tareas bajo el límite de AppEEARS) y descarga '
            'un CSV por producto a backend/data/. Necesita una cuenta de NASA Earthdata.')

    def add_arguments(self, parser):
        parser.add_argument('--inicio', default='2015-04-01', help='AAAA-MM-DD (SMAP inicia 2015-03-31)')
        parser.add_argument('--fin', default='2025-12-31', help='AAAA-MM-DD')
        parser.add_argument('--nombre', default='CropAnalytics-Altos-2015-2025')
        parser.add_argument('--prueba', action='store_true',
                            help='Valida capas y muestra las tareas sin pedir credenciales')
        parser.add_argument('--esperar', action='store_true',
                            help='Tras enviar, espera a que AppEEARS termine y descarga')
        parser.add_argument('--descargar', action='store_true',
                            help='Descarga las tareas guardadas en appeears_tarea.json')

    def handle(self, *args, **opts):
        if opts['descargar']:
            if not TAREA_PATH.exists():
                raise CommandError(f'No hay tareas guardadas en {TAREA_PATH}.')
            guardado = json.loads(TAREA_PATH.read_text(encoding='utf-8'))
            with self._sesion() as headers:
                self._esperar_y_descargar(guardado['tareas'], guardado['nombre'], headers)
            return

        celdas = json.loads(CELDAS_PATH.read_text(encoding='utf-8'))
        tareas = dividir_tareas(celdas, date.fromisoformat(opts['inicio']),
                                date.fromisoformat(opts['fin']), opts['nombre'])
        self._validar_capas()
        self.stdout.write(f"{len(celdas)} puntos, {len(CAPAS)} capas, {opts['inicio']} a {opts['fin']} "
                          f"-> {len(tareas)} tareas:")
        for t in tareas:
            fechas = t['params']['dates'][0]
            self.stdout.write(f"  {t['task_name']}: {fechas['startDate']} a {fechas['endDate']}")
        if opts['prueba']:
            self.stdout.write(self.style.SUCCESS('Capas válidas. Sin enviar (--prueba).'))
            return

        with self._sesion() as headers:
            ids = []
            for t in tareas:
                r = requests.post(f'{API}/task', json=t, headers=headers, timeout=120)
                if r.status_code >= 400:
                    raise CommandError(f"AppEEARS rechazó {t['task_name']} ({r.status_code}): {r.text[:500]}"
                                       + (f'. Ya enviadas: {ids}' if ids else ''))
                ids.append(r.json()['task_id'])
                TAREA_PATH.write_text(json.dumps({'nombre': opts['nombre'], 'tareas': ids}), encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'{len(ids)} tareas enviadas (guardadas en {TAREA_PATH.name})'))
            if opts['esperar']:
                self._esperar_y_descargar(ids, opts['nombre'], headers)
            else:
                self.stdout.write('Cuando AppEEARS termine: python manage.py solicitar_appeears --descargar')

    def _validar_capas(self):
        for producto in sorted({p for p, _ in CAPAS}):
            disponibles = requests.get(f'{API}/product/{producto}', timeout=60).json()
            faltan = [c for p, c in CAPAS if p == producto and c not in disponibles]
            if faltan:
                raise CommandError(f'{producto} ya no ofrece: {faltan}')

    @contextmanager
    def _sesion(self):
        usuario = os.environ.get('EARTHDATA_USERNAME') or input('Usuario de NASA Earthdata: ')
        clave = os.environ.get('EARTHDATA_PASSWORD') or getpass.getpass('Contraseña: ')
        r = requests.post(f'{API}/login', auth=(usuario, clave), timeout=60)
        if r.status_code != 200:
            raise CommandError(f'No se pudo iniciar sesión en AppEEARS ({r.status_code}).')
        headers = {'Authorization': f"Bearer {r.json()['token']}"}
        try:
            yield headers
        finally:
            requests.post(f'{API}/logout', headers=headers, timeout=60)
            self.stdout.write('Sesión de AppEEARS cerrada.')

    def _esperar(self, task_id, headers):
        estado_previo = None
        while True:
            estado = requests.get(f'{API}/task/{task_id}', headers=headers, timeout=60).json().get('status')
            if estado != estado_previo:
                self.stdout.write(f'[{time.strftime("%H:%M")}] {task_id}: {estado}')
                estado_previo = estado
            if estado == 'done':
                return
            if estado in ('error', 'deleted', None):
                raise CommandError(f'La tarea {task_id} terminó con estado {estado!r}; revísala en AppEEARS.')
            time.sleep(60)

    def _esperar_y_descargar(self, task_ids, nombre, headers):
        for task_id in task_ids:
            self._esperar(task_id, headers)

        # Une las partes de cada producto en un solo CSV (encabezado una sola vez)
        destinos = {}
        parte = DATA_DIR / '.appeears_parte.csv'
        for task_id in task_ids:
            bundle = requests.get(f'{API}/bundle/{task_id}', headers=headers, timeout=60).json()
            for f in bundle['files']:
                clave = _clave_producto(Path(f['file_name']).name)
                if not (clave and f['file_name'].endswith('-results.csv')):
                    continue
                with requests.get(f"{API}/bundle/{task_id}/{f['file_id']}", headers=headers,
                                  stream=True, allow_redirects=True, timeout=600) as r:
                    r.raise_for_status()
                    with open(parte, 'wb') as fh:
                        for bloque in r.iter_content(chunk_size=1 << 20):
                            fh.write(bloque)
                destino = DATA_DIR / f'{nombre}-{clave}-results.csv'
                primera = destino not in destinos
                destinos[destino] = destinos.get(destino, 0) + 1
                with open(parte, 'rb') as src, open(destino, 'wb' if primera else 'ab') as dst:
                    if not primera:
                        src.readline()  # encabezado repetido
                    for linea in src:
                        dst.write(linea)
                self.stdout.write(f'  {task_id} -> {destino.name}')
        parte.unlink(missing_ok=True)
        for destino, partes in destinos.items():
            self.stdout.write(f'{destino.name}: {partes} partes, {destino.stat().st_size / 1e6:.1f} MB')
        self.stdout.write(self.style.SUCCESS('Listo.'))
