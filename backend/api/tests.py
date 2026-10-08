from django.test import SimpleTestCase

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
