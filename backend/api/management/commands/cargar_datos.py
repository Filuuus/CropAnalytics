import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from api.models import Estado, Municipio, Terreno, Hibrido, Ciclo, ResultadoLaboratorio, DatoClimatico

class Command(BaseCommand):
    help = 'Carga los datos de los CSVs de CropAnalytics a la base de datos'

    def handle(self, *args, **kwargs):
        base_dir = settings.BASE_DIR
        data_dir = os.path.join(base_dir, 'data')

        self.stdout.write(self.style.WARNING('Iniciando carga de datos...'))

        # Helper para limpiar números con comas
        def clean_float(value):
            if not value or value.strip() == '':
                return None
            try:
                # Quitamos comillas si hay y cambiamos coma por punto
                cleaned = str(value).replace('"', '').replace(',', '.')
                return float(cleaned)
            except ValueError:
                return None

        # Helper para fechas (de M/D/YYYY a YYYY-MM-DD)
        def clean_date(value):
            if not value or value.strip() == '':
                return None
            try:
                return datetime.strptime(value.strip(), '%m/%d/%Y').date()
            except ValueError:
                return None

        # 1. ESTADOS
        self.stdout.write('Cargando Estados...')
        with open(os.path.join(data_dir, 'Estados.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                Estado.objects.get_or_create(
                    id=row['id'],
                    defaults={'nombre': row['nombre']}
                )

        # 2. MUNICIPIOS
        self.stdout.write('Cargando Municipios...')
        with open(os.path.join(data_dir, 'Municipios.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    estado = Estado.objects.get(id=row['id_estado'])
                    Municipio.objects.get_or_create(
                        id=row['id'],
                        defaults={'estado': estado, 'nombre': row['nombre']}
                    )
                except Estado.DoesNotExist:
                    continue

        # 3. HÍBRIDOS
        self.stdout.write('Cargando Híbridos...')
        with open(os.path.join(data_dir, 'Hibridos.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                Hibrido.objects.get_or_create(
                    id=row['id'],
                    defaults={'marca': row['marca'], 'nombre': row['hibrido']}
                )

        # 4. TERRENOS
        self.stdout.write('Cargando Terrenos...')
        with open(os.path.join(data_dir, 'Terrenos.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    municipio = Municipio.objects.get(id=row['id_municipio'])
                    lat = clean_float(row['latitud_y_gps'])
                    lon = clean_float(row['longitud_x_gps'])
                    
                    # PostGIS usa Point(Longitud, Latitud) -> ¡Ojo, X primero, Y después!
                    ubicacion = Point(lon, lat, srid=4326) if lon and lat else None

                    Terreno.objects.get_or_create(
                        id=row['id'],
                        defaults={
                            'municipio': municipio,
                            'latitud_norte_dms': row['Latitud Norte (DMS)'],
                            'longitud_oeste_dms': row['Longitud Oeste (DMS)'],
                            'latitud_gps': lat or 0.0,
                            'longitud_gps': lon or 0.0,
                            'altitud': clean_float(row['altitud']),
                            'ubicacion_geo': ubicacion
                        }
                    )
                except Municipio.DoesNotExist:
                    continue

        # 5. CICLOS
        self.stdout.write('Cargando Ciclos...')
        with open(os.path.join(data_dir, 'Ciclos.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    terreno = Terreno.objects.get(id=row['id_terreno'])
                    hibrido = Hibrido.objects.get(id=row['id_hibrido'])
                    Ciclo.objects.get_or_create(
                        id=row['id'],
                        defaults={
                            'terreno': terreno,
                            'hibrido': hibrido,
                            'year': int(row['year']),
                            'fecha_siembra': clean_date(row['siembra']),
                            'fecha_cosecha': clean_date(row['cosecha']),
                            'condicion': row['condiciones']
                        }
                    )
                except (Terreno.DoesNotExist, Hibrido.DoesNotExist):
                    continue

        # 6. LABORATORIO
        self.stdout.write('Cargando Laboratorio...')
        with open(os.path.join(data_dir, 'Laboratorio.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ciclo = Ciclo.objects.get(id=row['id_ciclo'])
                    ResultadoLaboratorio.objects.get_or_create(
                        ciclo=ciclo,
                        defaults={
                            'metodologia': row.get('metodologia', ''),
                            'pem': clean_float(row.get('pem')),
                            'pff': clean_float(row.get('pff')),
                            'dff': clean_float(row.get('dff')),
                            'ucaff': clean_float(row.get('ucaff')),
                            'npc': clean_float(row.get('npc')),
                            'ppc': clean_float(row.get('ppc')),
                            'rmf': clean_float(row.get('rmf')),
                            'ms': clean_float(row.get('ms')),
                            'cen': clean_float(row.get('cen')),
                            'gc': clean_float(row.get('gc')),
                            'pc': clean_float(row.get('pc')),
                            'fdn': clean_float(row.get('fdn')),
                            'cnf': clean_float(row.get('cnf')),
                            'rms': clean_float(row.get('rms')),
                        }
                    )
                except Ciclo.DoesNotExist:
                    continue

        # 7. CLIMA (OpenMeteo)
        self.stdout.write('Cargando Clima...')
        with open(os.path.join(data_dir, 'OpenMeteo.csv'), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ciclo = Ciclo.objects.get(id=row['id_ciclo'])
                    DatoClimatico.objects.get_or_create(
                        ciclo=ciclo,
                        defaults={
                            'dco': clean_float(row.get('dco')),
                            'pp_anual': clean_float(row.get('ppanual')),
                            'pp_co': clean_float(row.get('ppco')),
                            'tm_anual': clean_float(row.get('tmanual')),
                            'tmax_anual': clean_float(row.get('tmaxanual')),
                            'tmin_anual': clean_float(row.get('tminanual')),
                            'tm_co': clean_float(row.get('tmco')),
                            'tmax_co': clean_float(row.get('tmaxco')),
                            'tmin_co': clean_float(row.get('tminco')),
                            'uca_co': clean_float(row.get('ucaco')),
                            'horas_calor_30': clean_float(row.get('htemp>30')),
                            'horas_frio_5': clean_float(row.get('htemp<5')),
                            'ghi': clean_float(row.get('ghi(mj/m2)')),
                            'ss': clean_float(row.get('ss')),
                        }
                    )
                except Ciclo.DoesNotExist:
                    continue

        self.stdout.write(self.style.SUCCESS('¡Datos cargados exitosamente!'))