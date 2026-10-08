from django.test import SimpleTestCase, TestCase

from .models import Ciclo, ResultadoLaboratorio
from .serializers import CicloSerializer
from .utils.milk_calculator import calcular_metricas_milk2024, datos_milk2024


class Milk2024Tests(SimpleTestCase):
    def test_igual_a_la_hoja_oficial(self):
        # Muestras de MILK2024-Spreadsheet.xlsx (hoja MILK2024_Metric): fila, entradas C..K
        # (rend. Mg/ha, almidón, starchD 7h, EE, PC, NDFom, NDFDom 30h, uNDF240, ceniza) y
        # resultado AW (kg leche / t MS). Cada fila varía una entrada respecto a la 38.
        muestras = [
            (38, (10, 37.1, 76.8, 3.5, 7.4, 35.6, 64.2, 7.9, 3.8), 1625.7882),
            (46, (10, 37.1, 76.8, 3.5, 7.4, 35.6, 55, 7.9, 3.8), 1568.5695),
            (44, (10, 37.1, 76.8, 3.5, 7.4, 35.6, 75, 7.9, 3.8), 1717.2485),
            (40, (10, 37.1, 76.8, 3.5, 7.4, 39, 64.2, 7.9, 3.8), 1594.7453),
            (62, (10, 37.1, 76.8, 3.5, 7.4, 35.6, 64.2, 7.9, 5), 1599.8214),
            (54, (10, 37.1, 65, 3.5, 7.4, 35.6, 64.2, 7.9, 3.8), 1612.5387),
            (56, (10, 37.1, 76.8, 3, 7.4, 35.6, 64.2, 7.9, 3.8), 1614.5322),
            (50, (10, 33, 76.8, 3.5, 7.4, 35.6, 64.2, 7.9, 3.8), 1616.9469),
            (60, (10, 37.1, 76.8, 3.5, 6.5, 35.6, 64.2, 7.9, 3.8), 1620.5183),
        ]
        for fila, (rend, almidon, almidon_d, ee, pc, fdn, fdnd, undf, ceniza), leche_ton in muestras:
            with self.subTest(fila=fila):
                r = calcular_metricas_milk2024(dict(
                    yield_dm=rend, starch=almidon, starch_d=almidon_d, ee=ee, cp=pc,
                    ndf=fdn, ndfd=fdnd, undf240=undf, ash=ceniza,
                ))
                self.assertAlmostEqual(r['leche_ton'], leche_ton, delta=0.01)
                self.assertAlmostEqual(r['leche_ha'], leche_ton * rend, delta=0.1)

    def test_serializer_usa_el_mismo_calculo(self):
        # GC falta en 126 filas del dataset: debe caer al fallback, igual que en las vistas.
        ciclo = Ciclo()
        ResultadoLaboratorio(ciclo=ciclo, ms=40.0, pc=7.5, gc=None, cen=5.0, fdn=48.0, cnf=38.0, rms=21.0)
        esperado = calcular_metricas_milk2024(datos_milk2024(40.0, 7.5, None, 5.0, 48.0, 38.0, 21.0))
        self.assertEqual(datos_milk2024(40.0, 7.5, None, 5.0, 48.0, 38.0, 21.0)['ee'], 3.2)
        self.assertEqual(CicloSerializer().get_leche_ha(ciclo), esperado['leche_ha'])
        self.assertIsNone(CicloSerializer().get_leche_ha(Ciclo()))

    def test_almidon_no_supera_cnf(self):
        # 163 de 965 muestras tienen CNF < 30 %: el almidón no puede exceder los CNF.
        self.assertEqual(datos_milk2024(40, 7, 2, 5, 60, 25.0, 20)['starch'], 25.0)
        self.assertEqual(datos_milk2024(40, 7, 2, 5, 45, 40.0, 20)['starch'], 30.0)
        self.assertEqual(datos_milk2024(40, 7, 2, 5, 45, None, 20)['starch'], 30.0)


class ValidacionPreciosTests(SimpleTestCase):
    def test_precio_no_numerico_da_400(self):
        from rest_framework.test import APIRequestFactory
        from .views import RecomendacionHumedadView
        req = APIRequestFactory().post(
            '/api/recomendacion-humedad/', {'lat': 20.7, 'lon': -102.8, 'precio_leche': 'abc'}, format='json'
        )
        resp = RecomendacionHumedadView.as_view()(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('precio_leche', resp.data)


class EconomiaEnsilajeTests(SimpleTestCase):
    def test_escenarios_con_precios_por_defecto(self):
        from .utils.milk_calculator import calcular_valor_ensilaje
        # 20 t MS/ha, 30 000 kg leche/ha; precios por defecto (MXN): ensilaje 2800/t,
        # costo 1800/t, leche 10.50, transporte 150/t, costo lechería 3.5 por litro.
        r = calcular_valor_ensilaje({'yield_dm': 20.0}, {'leche_ha': 30000.0, 'leche_ton': 1500.0})
        self.assertEqual(r['escenario_venta']['utilidad_neta_ha'], 20000.0)        # 56000 - 36000
        self.assertEqual(r['escenario_uso_propio']['utilidad_neta_ha'], 174000.0)  # 315000 - 36000 - 105000
        self.assertEqual(r['escenario_compra']['utilidad_neta_ha'], 151000.0)      # 315000 - 59000 - 105000
        self.assertEqual(r['recomendacion']['mejor_opcion'], 'uso_propio')


class PuntuacionHibridosTests(SimpleTestCase):
    @staticmethod
    def candidato(nombre, leche_ton, rendimiento):
        return {'hibrido': {'nombre': nombre}, '_leche_ton': leche_ton, '_adj_yield': rendimiento,
                '_ndf': 45.0, '_consistency': 0.8}

    def orden(self, suitability, riego):
        from .utils.hybrid_recommender import _puntuar
        # A rinde más, B tiene mejor calidad nutricional; NDF y consistencia iguales.
        ranking = _puntuar([self.candidato('A', 1300, 25), self.candidato('B', 1500, 18)], suitability, riego)
        return [h['hibrido']['nombre'] for h in ranking]

    def test_pesos_por_banda_de_humedad(self):
        self.assertEqual(self.orden(40, riego=False), ['B', 'A'])  # sequía: calidad 0.40 > rendimiento 0.20
        self.assertEqual(self.orden(70, riego=False), ['A', 'B'])  # buena humedad: rendimiento 0.45 > 0.25
        self.assertEqual(self.orden(40, riego=True), ['A', 'B'])   # con riego: pesos base 0.35 > 0.30

    def test_mejor_en_todo_obtiene_puntaje_maximo(self):
        from .utils.hybrid_recommender import _puntuar
        for suitability in (40, 50, 70):
            mejor = dict(self.candidato('M', 1500, 25), _ndf=40.0, _consistency=0.9)
            ranking = _puntuar([mejor, self.candidato('P', 1300, 18)], suitability, False)
            self.assertEqual(ranking[0]['score'], 10000.0)  # los pesos de cada banda suman 1
            self.assertEqual(ranking[1]['score'], 0.0)


class GestionUsuariosTests(TestCase):
    def test_registro_nuevo_es_investigador(self):
        from .auth_utils import create_user
        self.assertEqual(create_user(name='Ana', email='Ana@Ejemplo.mx', password='x').role, 'INVESTIGADOR')

    def test_primer_jefe_no_se_puede_eliminar(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        User = get_user_model()
        primero = User.objects.create(username='a@x.mx', email='a@x.mx', role='JEFE')
        otro = User.objects.create(username='b@x.mx', email='b@x.mx', role='JEFE')
        client = APIClient()
        client.force_authenticate(User.objects.get(role='SADMIN'))
        self.assertEqual(client.delete(f'/api/users/{primero.pk}/').status_code, 400)
        self.assertEqual(client.delete(f'/api/users/{otro.pk}/').status_code, 204)


class LstmBatchTests(SimpleTestCase):
    def test_batch_igual_a_un_dia_a_la_vez(self):
        import numpy as np
        from .ml import ml_engine as E
        if not E._TORCH:
            self.skipTest('torch no instalado')
        import torch
        torch.manual_seed(0)
        model = E._SoilMoistureLSTM().eval()
        X = np.random.default_rng(0).random((30, E.N_FEATURES), dtype=np.float32)
        esperado = []
        with torch.no_grad():
            for t in range(len(X)):  # los 14 días ANTERIORES a t (como en el entrenamiento), ceros al inicio
                w = np.vstack([np.zeros((E.LOOKBACK, E.N_FEATURES), np.float32), X[:t]])[-E.LOOKBACK:]
                esperado.append(float(model(torch.from_numpy(w)[None])[0, -1, 0]) * 0.31 + 0.04)
        np.testing.assert_allclose(E._lstm_predict(model, X, None), np.clip(esperado, 0.01, 0.70), atol=1e-6)


class CeldasEaseGridTests(SimpleTestCase):
    def test_pixel_igual_al_de_appeears(self):
        from .ml.celdas import centro, fila_col
        # (lat, lon) -> (Line_Y, Sample_X) que reportó AppEEARS para SPL3SMP_E 9 km en 2024
        referencia = [
            (20.740333, -102.834666, 524, 826), (21.479897, -102.280986, 514, 832),
            (21.131055, -102.454666, 519, 830), (21.2645, -102.036666, 517, 835),
            (21.393667, -102.341833, 515, 831), (20.951, -102.168, 521, 833),
            (21.042833, -102.949666, 520, 825), (20.876222, -102.715194, 522, 827),
            (21.047, -102.623333, 520, 828), (20.753597, -103.113566, 524, 823),
            (20.6945, -102.5865, 525, 829),
        ]
        for lat, lon, fila, col in referencia:
            self.assertEqual(fila_col(lat, lon), (fila, col))
            self.assertEqual(fila_col(*centro(fila, col)), (fila, col))


class SolicitudAppeearsTests(SimpleTestCase):
    def test_formato_de_la_solicitud(self):
        from datetime import date
        from .management.commands.solicitar_appeears import CAPAS, construir_tarea
        celdas = [{'id': 'M09_524_826', 'lat': 20.739166, 'lon': -102.837137}]
        t = construir_tarea(celdas, date(2015, 4, 1), date(2025, 12, 31), 'prueba')
        self.assertEqual(t['task_type'], 'point')
        self.assertEqual(t['params']['dates'], [{'startDate': '04-01-2015', 'endDate': '12-31-2025'}])  # MM-DD-AAAA
        self.assertEqual(len(t['params']['layers']), len(CAPAS))
        self.assertEqual(t['params']['coordinates'][0],
                         {'id': 'M09_524_826', 'category': 'altos', 'latitude': 20.739166, 'longitude': -102.837137})


class PanoramaTests(SimpleTestCase):
    def test_inicio_de_lluvias_y_racha_seca(self):
        from datetime import date, timedelta
        import numpy as np
        from .ml.panorama import resumir_celda
        # Tres años secos (0.10) que se humedecen (0.30) desde una fecha conocida hasta el 31 oct;
        # en 2018 una racha seca de 12 días cae en la floración (inicio + 75 días).
        humedo_desde = {2017: date(2017, 6, 20), 2018: date(2018, 7, 1), 2019: date(2019, 6, 25)}
        fechas = [date(2017, 1, 1) + timedelta(days=i) for i in range(365 * 3)]
        sm = np.array([0.30 if humedo_desde[f.year] <= f <= date(f.year, 10, 31) else 0.10 for f in fechas])
        sequia = date(2018, 7, 4) + timedelta(days=70)
        sm[[i for i, f in enumerate(fechas) if sequia <= f < sequia + timedelta(days=12)]] = 0.10

        r = resumir_celda(fechas, sm)
        # La media de 7 días cruza 50 al 4.º día húmedo
        self.assertEqual(r['inicio_lluvias']['por_anio'], {'2017': '2017-06-23', '2018': '2018-07-04', '2019': '2019-06-28'})
        self.assertEqual((r['inicio_lluvias']['temprana'], r['inicio_lluvias']['tardia']), ('06-23', '07-04'))
        self.assertEqual(r['sequia_floracion']['por_anio'], {'2017': False, '2018': True, '2019': False})
        self.assertEqual(r['sequia_floracion']['probabilidad'], 0.33)
        self.assertEqual(r['bandas']['p50'][date(2017, 8, 15).timetuple().tm_yday - 1], 100.0)  # agosto: húmedo
        self.assertEqual(r['bandas']['p50'][14], 0.0)                                           # enero: seco
