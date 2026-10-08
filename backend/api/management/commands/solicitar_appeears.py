import getpass
import json
import os
import time
from contextlib import contextmanager
from datetime import date
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

DATA_DIR = Path(settings.BASE_DIR) / 'data'
TAREA_PATH = DATA_DIR / 'appeears_tarea.json'


def construir_tarea(celdas, inicio, fin, nombre):
    """Solicitud de muestreo por puntos (una coordenada por celda) para la API de AppEEARS."""
    return {
        'task_type': 'point',
        'task_name': nombre,
        'params': {
            'dates': [{'startDate': inicio.strftime('%m-%d-%Y'), 'endDate': fin.strftime('%m-%d-%Y')}],
            'layers': [{'product': p, 'layer': capa} for p, capa in CAPAS],
            'coordinates': [
                {'id': c['id'], 'category': 'altos', 'latitude': c['lat'], 'longitude': c['lon']}
                for c in celdas
            ],
        },
    }


class Command(BaseCommand):
    help = ('Envía a NASA AppEEARS la solicitud de SMAP + Daymet para las celdas de '
            'celdas_altos.json y descarga los CSV a backend/data/. Necesita una cuenta de '
            'NASA Earthdata (urs.earthdata.nasa.gov).')

    def add_arguments(self, parser):
        parser.add_argument('--inicio', default='2015-04-01', help='AAAA-MM-DD (SMAP inicia 2015-03-31)')
        parser.add_argument('--fin', default='2025-12-31', help='AAAA-MM-DD')
        parser.add_argument('--nombre', default='CropAnalytics-Altos-2015-2025')
        parser.add_argument('--prueba', action='store_true',
                            help='Valida capas y muestra la solicitud sin pedir credenciales')
        parser.add_argument('--esperar', action='store_true',
                            help='Tras enviar, espera a que AppEEARS termine y descarga')
        parser.add_argument('--descargar', metavar='TASK_ID', nargs='?', const='ultima',
                            help='Descarga una tarea ya enviada (sin valor: la última guardada)')

    def handle(self, *args, **opts):
        if opts['descargar']:
            task_id = self._task_id_guardado() if opts['descargar'] == 'ultima' else opts['descargar']
            with self._sesion() as headers:
                self._esperar_y_descargar(task_id, headers)
            return

        celdas = json.loads(CELDAS_PATH.read_text(encoding='utf-8'))
        tarea = construir_tarea(celdas, date.fromisoformat(opts['inicio']),
                                date.fromisoformat(opts['fin']), opts['nombre'])
        self._validar_capas()
        self.stdout.write(f"{len(celdas)} puntos, {len(CAPAS)} capas, {opts['inicio']} a {opts['fin']}")
        if opts['prueba']:
            self.stdout.write(self.style.SUCCESS('Capas válidas. Sin enviar (--prueba).'))
            return

        with self._sesion() as headers:
            r = requests.post(f'{API}/task', json=tarea, headers=headers, timeout=120)
            if r.status_code >= 400:
                raise CommandError(f'AppEEARS rechazó la solicitud ({r.status_code}): {r.text[:500]}')
            task_id = r.json()['task_id']
            TAREA_PATH.write_text(json.dumps({'task_id': task_id, 'nombre': opts['nombre']}), encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'Solicitud enviada: {task_id} (guardada en {TAREA_PATH.name})'))
            if opts['esperar']:
                self._esperar_y_descargar(task_id, headers)
            else:
                self.stdout.write('Cuando AppEEARS termine: python manage.py solicitar_appeears --descargar')

    def _validar_capas(self):
        for producto in sorted({p for p, _ in CAPAS}):
            disponibles = requests.get(f'{API}/product/{producto}', timeout=60).json()
            faltan = [c for p, c in CAPAS if p == producto and c not in disponibles]
            if faltan:
                raise CommandError(f'{producto} ya no ofrece: {faltan}')

    def _task_id_guardado(self):
        if not TAREA_PATH.exists():
            raise CommandError(f'No hay tarea guardada en {TAREA_PATH}; pasa el TASK_ID.')
        return json.loads(TAREA_PATH.read_text(encoding='utf-8'))['task_id']

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

    def _esperar_y_descargar(self, task_id, headers):
        estado_previo = None
        while True:
            estado = requests.get(f'{API}/task/{task_id}', headers=headers, timeout=60).json().get('status')
            if estado != estado_previo:
                self.stdout.write(f'[{time.strftime("%H:%M")}] {task_id}: {estado}')
                estado_previo = estado
            if estado == 'done':
                break
            if estado in ('error', 'deleted', None):
                raise CommandError(f'La tarea terminó con estado {estado!r}; revísala en el sitio de AppEEARS.')
            time.sleep(60)

        bundle = requests.get(f'{API}/bundle/{task_id}', headers=headers, timeout=60).json()
        for f in bundle['files']:
            nombre = Path(f['file_name']).name
            if nombre.endswith('-results.csv'):
                destino = DATA_DIR / nombre
            elif nombre.endswith('-request.json'):
                destino = DATA_DIR / 'appeears_solicitud.json'
            else:
                continue
            with requests.get(f"{API}/bundle/{task_id}/{f['file_id']}", headers=headers,
                              stream=True, allow_redirects=True, timeout=600) as r:
                r.raise_for_status()
                with open(destino, 'wb') as fh:
                    for bloque in r.iter_content(chunk_size=1 << 20):
                        fh.write(bloque)
            self.stdout.write(f'  descargado {destino.name} ({destino.stat().st_size / 1e6:.1f} MB)')
        self.stdout.write(self.style.SUCCESS('Listo.'))
