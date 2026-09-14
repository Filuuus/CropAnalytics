import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from django.db import transaction
from api.models import Estado, Municipio, Terreno, Hibrido, Ciclo, ResultadoLaboratorio, DatoClimatico

class Command(BaseCommand):
    help = 'Carga los datos de los CSVs de CropAnalytics a la base de datos (Optimizado)'

    def handle(self, *args, **kwargs):
        base_dir = settings.BASE_DIR
        data_dir = os.path.join(base_dir, 'data')

        self.stdout.write(self.style.WARNING('Iniciando carga de datos optimizada...'))

        def clean_float(value):
            if not value or str(value).strip() == '':
                return None
            try:
                cleaned = str(value).replace('"', '').replace(',', '.')
                return float(cleaned)
            except ValueError:
                return None

        def clean_date(value):
            if not value or str(value).strip() == '':
                return None
            try:
                return datetime.strptime(value.strip(), '%m/%d/%Y').date()
            except ValueError:
                return None

        with transaction.atomic():
            # 1. ESTADOS
            self.stdout.write('Cargando Estados...')
            with open(os.path.join(data_dir, 'Estados.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    Estado.objects.get_or_create(
                        id=int(row['id']),
                        defaults={'nombre': row['nombre']}
                    )
            
            # Map for foreign keys
            estados_dict = {e.id: e for e in Estado.objects.all()}

            # 2. MUNICIPIOS
            self.stdout.write('Cargando Municipios...')
            municipios_to_create = []
            seen_municipio_ids = set(Municipio.objects.values_list('id', flat=True))
            
            with open(os.path.join(data_dir, 'Municipios.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    m_id = int(row['id'])
                    if m_id in seen_municipio_ids:
                        continue
                    
                    estado = estados_dict.get(int(row['id_estado']))
                    if estado:
                        municipios_to_create.append(Municipio(id=m_id, estado=estado, nombre=row['nombre']))
                        seen_municipio_ids.add(m_id)
            
            if municipios_to_create:
                Municipio.objects.bulk_create(municipios_to_create)
                self.stdout.write(f'  Creados {len(municipios_to_create)} municipios.')

            # Update map
            municipios_dict = {m.id: m for m in Municipio.objects.all()}

            # 3. HÍBRIDOS
            self.stdout.write('Cargando Híbridos...')
            hibridos_to_create = []
            seen_hibrido_ids = set(Hibrido.objects.values_list('id', flat=True))

            with open(os.path.join(data_dir, 'Hibridos.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    h_id = int(row['id'])
                    if h_id in seen_hibrido_ids:
                        continue
                    
                    hibridos_to_create.append(Hibrido(id=h_id, marca=row['marca'], nombre=row['hibrido']))
                    seen_hibrido_ids.add(h_id)
            
            if hibridos_to_create:
                Hibrido.objects.bulk_create(hibridos_to_create)
                self.stdout.write(f'  Creados {len(hibridos_to_create)} híbridos.')

            # Update map
            hibridos_dict = {h.id: h for h in Hibrido.objects.all()}

            # 4. TERRENOS
            self.stdout.write('Cargando Terrenos...')
            terrenos_to_create = []
            seen_terreno_ids = set(Terreno.objects.values_list('id', flat=True))

            with open(os.path.join(data_dir, 'Terrenos.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t_id = int(row['id'])
                    if t_id in seen_terreno_ids:
                        continue
                        
                    municipio = municipios_dict.get(int(row['id_municipio']))
                    if municipio:
                        lat = clean_float(row['latitud_y_gps'])
                        lon = clean_float(row['longitud_x_gps'])
                        ubicacion = Point(lon, lat, srid=4326) if lon and lat else None
                        
                        terrenos_to_create.append(Terreno(
                            id=t_id,
                            municipio=municipio,
                            latitud_norte_dms=row['Latitud Norte (DMS)'],
                            longitud_oeste_dms=row['Longitud Oeste (DMS)'],
                            latitud_gps=lat or 0.0,
                            longitud_gps=lon or 0.0,
                            altitud=clean_float(row['altitud']),
                            ubicacion_geo=ubicacion
                        ))
                        seen_terreno_ids.add(t_id)

            if terrenos_to_create:
                Terreno.objects.bulk_create(terrenos_to_create)
                self.stdout.write(f'  Creados {len(terrenos_to_create)} terrenos.')

            # Update map
            terrenos_dict = {t.id: t for t in Terreno.objects.all()}

            # 5. CICLOS
            self.stdout.write('Cargando Ciclos...')
            ciclos_to_create = []
            seen_ciclo_ids = set(Ciclo.objects.values_list('id', flat=True))

            with open(os.path.join(data_dir, 'Ciclos.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c_id = int(row['id'])
                    if c_id in seen_ciclo_ids:
                        continue
                        
                    terreno = terrenos_dict.get(int(row['id_terreno']))
                    hibrido = hibridos_dict.get(int(row['id_hibrido']))
                    if terreno and hibrido:
                        ciclos_to_create.append(Ciclo(
                            id=c_id,
                            terreno=terreno,
                            hibrido=hibrido,
                            year=int(row['year']),
                            fecha_siembra=clean_date(row['siembra']),
                            fecha_cosecha=clean_date(row['cosecha']),
                            condicion=row['condiciones']
                        ))
                        seen_ciclo_ids.add(c_id)

            if ciclos_to_create:
                Ciclo.objects.bulk_create(ciclos_to_create)
                self.stdout.write(f'  Creados {len(ciclos_to_create)} ciclos.')

            # Update map
            ciclos_dict = {c.id: c for c in Ciclo.objects.all()}

            # 6. LABORATORIO
            self.stdout.write('Cargando Laboratorio...')
            lab_to_create = []
            existing_lab_ciclos = set(ResultadoLaboratorio.objects.values_list('ciclo_id', flat=True))

            with open(os.path.join(data_dir, 'Laboratorio.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ciclo_id = int(row['id_ciclo'])
                    if ciclo_id in existing_lab_ciclos:
                        continue
                    
                    ciclo = ciclos_dict.get(ciclo_id)
                    if ciclo:
                        lab_to_create.append(ResultadoLaboratorio(
                            ciclo=ciclo,
                            metodologia=row.get('metodologia', ''),
                            pem=clean_float(row.get('pem')),
                            pff=clean_float(row.get('pff')),
                            dff=clean_float(row.get('dff')),
                            ucaff=clean_float(row.get('ucaff')),
                            npc=clean_float(row.get('npc')),
                            ppc=clean_float(row.get('ppc')),
                            rmf=clean_float(row.get('rmf')),
                            ms=clean_float(row.get('ms')),
                            cen=clean_float(row.get('cen')),
                            gc=clean_float(row.get('gc')),
                            pc=clean_float(row.get('pc')),
                            fdn=clean_float(row.get('fdn')),
                            cnf=clean_float(row.get('cnf')),
                            rms=clean_float(row.get('rms')),
                        ))
                        existing_lab_ciclos.add(ciclo_id)
            
            if lab_to_create:
                ResultadoLaboratorio.objects.bulk_create(lab_to_create)
                self.stdout.write(f'  Creados {len(lab_to_create)} registros de laboratorio.')

            # 7. CLIMA
            self.stdout.write('Cargando Clima...')
            clima_to_create = []
            existing_clima_ciclos = set(DatoClimatico.objects.values_list('ciclo_id', flat=True))

            with open(os.path.join(data_dir, 'OpenMeteo.csv'), encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ciclo_id = int(row['id_ciclo'])
                    if ciclo_id in existing_clima_ciclos:
                        continue
                    
                    ciclo = ciclos_dict.get(ciclo_id)
                    if ciclo:
                        clima_to_create.append(DatoClimatico(
                            ciclo=ciclo,
                            dco=clean_float(row.get('dco')),
                            pp_anual=clean_float(row.get('ppanual')),
                            pp_co=clean_float(row.get('ppco')),
                            tm_anual=clean_float(row.get('tmanual')),
                            tmax_anual=clean_float(row.get('tmaxanual')),
                            tmin_anual=clean_float(row.get('tminanual')),
                            tm_co=clean_float(row.get('tmco')),
                            tmax_co=clean_float(row.get('tmaxco')),
                            tmin_co=clean_float(row.get('tminco')),
                            uca_co=clean_float(row.get('ucaco')),
                            horas_calor_30=clean_float(row.get('htemp>30')),
                            horas_frio_5=clean_float(row.get('htemp<5')),
                            ghi=clean_float(row.get('ghi(mj/m2)')),
                            ss=clean_float(row.get('ss')),
                        ))
                        existing_clima_ciclos.add(ciclo_id)

            if clima_to_create:
                DatoClimatico.objects.bulk_create(clima_to_create)
                self.stdout.write(f'  Creados {len(clima_to_create)} registros climáticos.')

        self.stdout.write(self.style.SUCCESS('¡Datos cargados exitosamente!'))
