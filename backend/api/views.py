from django.shortcuts import render

# Create your views here.
from django.contrib.auth import get_user_model
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Terreno, Ciclo
from .auth_utils import active_jefe_count, is_initial_jefe
from .permissions import IsJefeOrSadmin
from .serializers import (
    AdminUserSerializer,
    CicloSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    RegisterSerializer,
    TerrenoSerializer,
    UserRoleUpdateSerializer,
    UserSerializer,
)

User = get_user_model()


def _precios_mercado(request):
    """Precios del request con defaults (MXN); 400 si alguno no es numérico."""
    defaults = {
        'precio_ensilaje': ('ensilaje_ton_ms', 2800.0),
        'precio_leche': ('leche_litro', 10.50),
        'costo_produccion': ('costo_produccion', 1800.0),
        'costo_transporte': ('transporte', 150.0),
    }
    precios = {}
    for campo, (clave, default) in defaults.items():
        try:
            precios[clave] = float(request.data.get(campo, default))
        except (TypeError, ValueError):
            raise ValidationError({campo: 'Debe ser un número válido.'})
    return precios


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializer.to_representation(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializer.to_representation(user))


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            return Response({'detail': 'Refresh token requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({'detail': 'Refresh token invalido.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserAdminViewSet(viewsets.ModelViewSet):
    serializer_class = AdminUserSerializer
    permission_classes = [IsJefeOrSadmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'email']
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = User.objects.exclude(role=User.Role.SADMIN).order_by('-date_joined')
        role = self.request.query_params.get('role')
        is_active = self.request.query_params.get('is_active')
        if role in {User.Role.JEFE, User.Role.INVESTIGADOR}:
            queryset = queryset.filter(role=role)
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        return queryset

    def update(self, request, *args, **kwargs):
        return Response({'detail': 'Usa endpoints especificos para administrar usuarios.'}, status=405)

    def partial_update(self, request, *args, **kwargs):
        return Response({'detail': 'Usa endpoints especificos para administrar usuarios.'}, status=405)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if is_initial_jefe(user):
            return Response(
                {'detail': 'El primer JEFE del sistema no puede eliminarse.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.role == User.Role.JEFE and active_jefe_count(exclude_user=user) == 0:
            return Response(
                {'detail': 'No se puede eliminar al ultimo JEFE activo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], url_path='role')
    def set_role(self, request, pk=None):
        user = self.get_object()
        serializer = UserRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data['role']
        if is_initial_jefe(user) and new_role == User.Role.INVESTIGADOR:
            return Response(
                {'detail': 'El primer JEFE del sistema no puede cambiarse a INVESTIGADOR.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.role == User.Role.JEFE and new_role == User.Role.INVESTIGADOR and active_jefe_count(exclude_user=user) == 0:
            return Response(
                {'detail': 'No se puede degradar al ultimo JEFE activo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.role = new_role
        user.es_investigador = new_role == User.Role.INVESTIGADOR
        user.save(update_fields=['role', 'es_investigador'])
        return Response(AdminUserSerializer(user).data)

    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response(AdminUserSerializer(user).data)

    @action(detail=True, methods=['patch'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.role == User.Role.JEFE and active_jefe_count(exclude_user=user) == 0:
            return Response(
                {'detail': 'No se puede inhabilitar al ultimo JEFE activo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(AdminUserSerializer(user).data)

class TerrenoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve la lista de terrenos.
    Optimizado con select_related para evitar N+1 queries al cargar municipio y estado.
    """
    permission_classes = [AllowAny]
    queryset = Terreno.objects.select_related('municipio__estado').all()
    serializer_class = TerrenoSerializer

class CicloViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve los ciclos agrícolas.
    Optimizado con select_related para cargar híbrido y laboratorio en una sola consulta.
    """
    permission_classes = [AllowAny]
    serializer_class = CicloSerializer

    def get_queryset(self):
        # Cargamos hibrido, laboratorio y datos del terreno (municipio y estado) para máxima velocidad
        queryset = Ciclo.objects.select_related(
            'hibrido',
            'laboratorio',
            'terreno__municipio__estado'
        ).all()
        
        # Permitir filtrar por ID de terreno desde la URL
        terreno_id = self.request.query_params.get('terreno', None)
        if terreno_id is not None:
            queryset = queryset.filter(terreno_id=terreno_id)
        return queryset

from django.db.models import Avg, Count, Sum
from .utils.milk_calculator import calcular_metricas_milk2024, calcular_valor_ensilaje, datos_milk2024
from .utils.geospatial_estimator import aplicar_ajuste_geoespacial
from .utils.location_recommender import (
    calcular_relevancia_regional,
    aplicar_relevancia_regional_a_confianza,
    obtener_ubicacion_desde_municipio
)
from .models import Hibrido, ResultadoLaboratorio, Terreno, Estado, Municipio

class CalcularProductorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        hibrido_id = request.data.get('hibrido_id')
        yield_dm = request.data.get('yield_dm')

        if not hibrido_id or yield_dm is None:
            return Response(
                {'detail': 'hibrido_id y yield_dm son campos obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            yield_dm = float(yield_dm)
        except ValueError:
            return Response(
                {'detail': 'yield_dm debe ser un número válido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar el híbrido por ID o Nombre
        try:
            if isinstance(hibrido_id, int) or (isinstance(hibrido_id, str) and hibrido_id.isdigit()):
                hibrido = Hibrido.objects.get(id=int(hibrido_id))
            else:
                hibrido = Hibrido.objects.get(nombre__iexact=str(hibrido_id))
        except Hibrido.DoesNotExist:
            return Response(
                {'detail': f'Híbrido con ID o nombre "{hibrido_id}" no encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Realizar consulta ORM para traer los promedios químicos de ese híbrido
        averages = ResultadoLaboratorio.objects.filter(ciclo__hibrido=hibrido).aggregate(
            avg_ms=Avg('ms'),
            avg_pc=Avg('pc'),
            avg_gc=Avg('gc'),
            avg_cen=Avg('cen'),
            avg_fdn=Avg('fdn'),
            avg_cnf=Avg('cnf'),
        )

        datos = datos_milk2024(
            averages['avg_ms'], averages['avg_pc'], averages['avg_gc'],
            averages['avg_cen'], averages['avg_fdn'], averages['avg_cnf'], yield_dm,
        )

        # Calcular métricas MILK2024
        resultados = calcular_metricas_milk2024(datos)
        
        # Calcular valor económico del ensilaje (opcional, basado en parámetros del request)
        precios_mercado = _precios_mercado(request)
        
        analisis_economico = calcular_valor_ensilaje(datos, resultados, precios_mercado)

        return Response({
            'hibrido': {
                'id': hibrido.id,
                'nombre': hibrido.nombre,
                'marca': hibrido.marca
            },
            'valores_bromatologicos_promedio': {
                'ms': round(datos['ms'], 2),
                'cp': round(datos['cp'], 2),
                'ee': round(datos['ee'], 2),
                'ash': round(datos['ash'], 2),
                'ndf': round(datos['ndf'], 2),
                'ndfd': datos['ndfd'],
                'undf240': datos['undf240'],
                'starch': datos['starch'],
                'starch_d': datos['starch_d']
            },
            **resultados,
            'analisis_economico': analisis_economico
        }, status=status.HTTP_200_OK)

class OptimizarSemillaView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        regimen_hidrico = request.data.get('regimen_hidrico')
        
        # Parámetros de ubicación opcionales
        estado_id = request.data.get('estado_id')
        municipio_id = request.data.get('municipio_id')

        if not regimen_hidrico:
            return Response(
                {'detail': 'regimen_hidrico es un campo obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if regimen_hidrico not in ['Riego', 'Temporal']:
            return Response(
                {'detail': 'regimen_hidrico debe ser "Riego" o "Temporal".'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener coordenadas si se proporciona municipio
        latitud, longitud, altitud = None, None, None
        if municipio_id:
            try:
                latitud, longitud, altitud = obtener_ubicacion_desde_municipio(int(municipio_id))
            except Exception:
                pass

        from django.db.models import Avg, F, ExpressionWrapper, fields, Min, Max, Case, When, Count
        import datetime

        # Primero verificar si hay ciclos con el régimen hídrico solicitado
        ciclos_count = Ciclo.objects.filter(condicion__iexact=regimen_hidrico).count()
        
        if ciclos_count == 0:
            return Response(
                {'detail': f'No se encontraron ciclos con régimen hídrico "{regimen_hidrico}".'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Agrupar y promediar en una sola consulta ORM de alto rendimiento
        # Solo incluir ciclos que tengan resultados de laboratorio
        ciclos_stats = Ciclo.objects.filter(
            condicion__iexact=regimen_hidrico,
            laboratorio__isnull=False
        ).values('hibrido__id', 'hibrido__nombre', 'hibrido__marca') \
            .annotate(
                count_ciclos=Count('id'),
                avg_ms=Avg('laboratorio__ms'),
                avg_cp=Avg('laboratorio__pc'),
                avg_ee=Avg('laboratorio__gc'),
                avg_ash=Avg('laboratorio__cen'),
                avg_ndf=Avg('laboratorio__fdn'),
                avg_cnf=Avg('laboratorio__cnf'),
                avg_dff=Avg('laboratorio__dff'),
                tasa_supervivencia=Avg(
                    Case(
                        When(laboratorio__pem__gt=0, then=ExpressionWrapper(F('laboratorio__ppc') * 1.0 / F('laboratorio__pem'), output_field=fields.FloatField())),
                        default=None,
                        output_field=fields.FloatField()
                    )
                ),
                rendimiento_promedio=Avg('laboratorio__rms'),
                # Duración del ciclo en la base de datos
                avg_duracion=Avg(
                    ExpressionWrapper(
                        F('fecha_cosecha') - F('fecha_siembra'),
                        output_field=fields.DurationField()
                    )
                ),
                # Fechas extremas para calcular las ventanas
                min_siembra=Min('fecha_siembra'),
                max_siembra=Max('fecha_siembra')
            ).filter(count_ciclos__gt=0)

        # Verificar si hay híbridos con datos de laboratorio
        if not ciclos_stats.exists():
            return Response(
                {'detail': f'No se encontraron híbridos con resultados de laboratorio bajo el régimen hídrico "{regimen_hidrico}". Por favor, asegúrate de que existan ciclos con datos de laboratorio cargados.'},
                status=status.HTTP_404_NOT_FOUND
            )

        ranking = []
        MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

        def format_date(d):
            return f"{d.day} de {MESES[d.month - 1]}"

        for item in ciclos_stats:
            avg_dff = item['avg_dff'] or 65.0
            tasa_supervivencia = item['tasa_supervivencia']
            rendimiento_promedio = item['rendimiento_promedio'] or 20.0

            if tasa_supervivencia is not None:
                factor_supervivencia = min(1.0, float(tasa_supervivencia))
            else:
                factor_supervivencia = 1.0

            # RMS ya es el rendimiento medido a la cosecha (solo plantas cosechadas);
            # multiplicarlo por la supervivencia contaría dos veces las pérdidas.
            # factor_supervivencia se reporta solo como información.
            rendimiento_real_esperado = float(rendimiento_promedio)

            # Calcular duración del ciclo promedio con fallbacks según tipo de datos devuelto por la BD
            avg_dur = item['avg_duracion']
            if avg_dur is not None:
                if hasattr(avg_dur, 'days'):
                    duracion_promedio = avg_dur.days
                else:
                    try:
                        duracion_promedio = int(avg_dur.total_seconds() / 86400)
                    except Exception:
                        duracion_promedio = int(avg_dur)
            else:
                duracion_promedio = 140 if regimen_hidrico == 'Riego' else 120

            # Calcular ventanas de fechas
            min_siembra = item['min_siembra']
            max_siembra = item['max_siembra']

            if not min_siembra or not max_siembra:
                ref_siembra = datetime.date(2000, 5, 15) if regimen_hidrico == 'Riego' else datetime.date(2000, 6, 15)
                start_siembra = ref_siembra - datetime.timedelta(days=7)
                end_siembra = ref_siembra + datetime.timedelta(days=7)
            else:
                dummy_min = datetime.date(2000, min_siembra.month, min_siembra.day)
                dummy_max = datetime.date(2000, max_siembra.month, max_siembra.day)
                range_days = (dummy_max - dummy_min).days

                if range_days > 15:
                    start_siembra = dummy_min
                    end_siembra = dummy_max
                else:
                    start_siembra = dummy_min - datetime.timedelta(days=7)
                    end_siembra = dummy_min + datetime.timedelta(days=7)

            ventana_siembra = f"{format_date(start_siembra)} - {format_date(end_siembra)}"
            start_cosecha = start_siembra + datetime.timedelta(days=duracion_promedio)
            end_cosecha = end_siembra + datetime.timedelta(days=duracion_promedio)
            ventana_cosecha = f"{format_date(start_cosecha)} - {format_date(end_cosecha)}"

            datos = datos_milk2024(
                item['avg_ms'], item['avg_cp'], item['avg_ee'],
                item['avg_ash'], item['avg_ndf'], item['avg_cnf'], rendimiento_real_esperado,
            )

            # Calcular métricas MILK2024
            resultados = calcular_metricas_milk2024(datos)
            
            # Calcular relevancia regional si se proporcionó ubicación
            relevancia_regional = None
            if municipio_id or estado_id:
                relevancia_regional = calcular_relevancia_regional(
                    hibrido_id=item['hibrido__id'],
                    estado_id=int(estado_id) if estado_id else None,
                    municipio_id=int(municipio_id) if municipio_id else None,
                    latitud=latitud,
                    longitud=longitud,
                    altitud=altitud
                )
                
                # Ajustar confianza basada en relevancia regional
                if relevancia_regional and 'confianza' in resultados:
                    resultados['confianza'] = aplicar_relevancia_regional_a_confianza(
                        resultados['confianza'],
                        relevancia_regional
                    )
            
            # Calcular análisis económico del ensilaje
            precios_mercado = _precios_mercado(request)
            analisis_economico = calcular_valor_ensilaje(datos, resultados, precios_mercado)

            hibrido_data = {
                'hibrido': {
                    'id': item['hibrido__id'],
                    'nombre': item['hibrido__nombre'],
                    'marca': item['hibrido__marca']
                },
                'valores_bromatologicos_promedio': {
                    'ms': round(datos['ms'], 2),
                    'cp': round(datos['cp'], 2),
                    'ee': round(datos['ee'], 2),
                    'ash': round(datos['ash'], 2),
                    'ndf': round(datos['ndf'], 2),
                    'ndfd': datos['ndfd'],
                    'undf240': datos['undf240'],
                    'starch': datos['starch'],
                    'starch_d': datos['starch_d']
                },
                'dff_promedio': round(avg_dff, 1),
                'duracion_ciclo_promedio': duracion_promedio,
                'ventana_siembra': ventana_siembra,
                'ventana_cosecha': ventana_cosecha,
                'regimen_hidrico': regimen_hidrico,
                'factor_supervivencia': round(factor_supervivencia, 4),
                'rendimiento_real_esperado': round(rendimiento_real_esperado, 2),
                **resultados,
                'analisis_economico': analisis_economico
            }
            
            # Agregar relevancia regional si está disponible
            if relevancia_regional:
                hibrido_data['relevancia_regional'] = relevancia_regional
            
            ranking.append(hibrido_data)

        # Ordenar ranking por leche_ha descendente, considerando relevancia regional si está disponible
        if municipio_id or estado_id:
            # Ordenar por combinación de leche_ha y relevancia regional
            max_leche = max(r['leche_ha'] for r in ranking) or 1.0
            ranking.sort(
                key=lambda x: (
                    x.get('relevancia_regional', {}).get('score', 50) * 0.3 +  # 30% peso a relevancia
                    (x['leche_ha'] / max_leche * 100) * 0.7  # 70% peso a producción
                ),
                reverse=True
            )
        else:
            # Ordenar solo por leche_ha si no hay ubicación
            ranking.sort(key=lambda x: x['leche_ha'], reverse=True)

        return Response(ranking, status=status.HTTP_200_OK)

class CalcularProductorGeoView(APIView):
    """
    Endpoint mejorado que incluye ajustes geoespaciales basados en la ubicación del terreno.
    Permite al productor obtener estimaciones más precisas considerando factores geográficos.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        hibrido_id = request.data.get('hibrido_id')
        yield_dm = request.data.get('yield_dm')
        terreno_id = request.data.get('terreno_id')
        
        # Coordenadas opcionales si no se proporciona terreno_id
        latitud = request.data.get('latitud')
        longitud = request.data.get('longitud')
        altitud = request.data.get('altitud')

        if not hibrido_id or yield_dm is None:
            return Response(
                {'detail': 'hibrido_id y yield_dm son campos obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            yield_dm = float(yield_dm)
        except ValueError:
            return Response(
                {'detail': 'yield_dm debe ser un número válido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar el híbrido
        try:
            if isinstance(hibrido_id, int) or (isinstance(hibrido_id, str) and hibrido_id.isdigit()):
                hibrido = Hibrido.objects.get(id=int(hibrido_id))
            else:
                hibrido = Hibrido.objects.get(nombre__iexact=str(hibrido_id))
        except Hibrido.DoesNotExist:
            return Response(
                {'detail': f'Híbrido con ID o nombre "{hibrido_id}" no encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Obtener coordenadas del terreno o usar las proporcionadas
        if terreno_id:
            try:
                terreno = Terreno.objects.get(id=terreno_id)
                latitud = terreno.latitud_gps
                longitud = terreno.longitud_gps
                altitud = terreno.altitud
                ubicacion_info = {
                    'terreno_id': terreno.id,
                    'municipio': terreno.municipio.nombre,
                    'estado': terreno.municipio.estado.nombre
                }
            except Terreno.DoesNotExist:
                return Response(
                    {'detail': f'Terreno con ID {terreno_id} no encontrado.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif latitud is not None and longitud is not None:
            try:
                latitud = float(latitud)
                longitud = float(longitud)
                altitud = float(altitud) if altitud is not None else None
                ubicacion_info = {
                    'coordenadas_personalizadas': True,
                    'latitud': latitud,
                    'longitud': longitud,
                    'altitud': altitud
                }
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'Las coordenadas deben ser números válidos.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {'detail': 'Debe proporcionar terreno_id o coordenadas (latitud, longitud).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener promedios bromatológicos del híbrido
        averages = ResultadoLaboratorio.objects.filter(ciclo__hibrido=hibrido).aggregate(
            avg_ms=Avg('ms'),
            avg_pc=Avg('pc'),
            avg_gc=Avg('gc'),
            avg_cen=Avg('cen'),
            avg_fdn=Avg('fdn'),
            avg_cnf=Avg('cnf'),
        )

        datos = datos_milk2024(
            averages['avg_ms'], averages['avg_pc'], averages['avg_gc'],
            averages['avg_cen'], averages['avg_fdn'], averages['avg_cnf'], yield_dm,
        )

        # Calcular métricas MILK2024 base
        resultados_base = calcular_metricas_milk2024(datos)

        # Aplicar ajuste geoespacial
        ajuste_geo = aplicar_ajuste_geoespacial(
            rendimiento_base=yield_dm,
            latitud=latitud,
            longitud=longitud,
            altitud=altitud
        )

        # Recalcular con rendimiento ajustado
        datos_ajustados = datos.copy()
        datos_ajustados['yield_dm'] = ajuste_geo['rendimiento_ajustado']
        resultados_ajustados = calcular_metricas_milk2024(datos_ajustados)

        return Response({
            'hibrido': {
                'id': hibrido.id,
                'nombre': hibrido.nombre,
                'marca': hibrido.marca
            },
            'ubicacion': ubicacion_info,
            'valores_bromatologicos_promedio': {
                'ms': round(datos['ms'], 2),
                'cp': round(datos['cp'], 2),
                'ee': round(datos['ee'], 2),
                'ash': round(datos['ash'], 2),
                'ndf': round(datos['ndf'], 2),
                'ndfd': datos['ndfd'],
                'undf240': datos['undf240'],
                'starch': datos['starch'],
                'starch_d': datos['starch_d']
            },
            'estimacion_base': {
                **resultados_base,
                'yield_dm': yield_dm
            },
            'ajuste_geoespacial': ajuste_geo,
            'estimacion_ajustada': {
                **resultados_ajustados,
                'yield_dm': ajuste_geo['rendimiento_ajustado']
            }
        }, status=status.HTTP_200_OK)

class EstadoListView(APIView):
    """
    Lista todos los estados disponibles en la base de datos.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        estados = Estado.objects.all().order_by('nombre').values('id', 'nombre')
        return Response(list(estados), status=status.HTTP_200_OK)


class MunicipioListView(APIView):
    """
    Lista municipios filtrados por estado.
    Si no se proporciona estado_id, devuelve todos los municipios.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        estado_id = request.query_params.get('estado_id')
        
        if estado_id:
            municipios = Municipio.objects.filter(
                estado_id=estado_id
            ).order_by('nombre').values('id', 'nombre', 'estado_id')
        else:
            municipios = Municipio.objects.all().select_related('estado').order_by('estado__nombre', 'nombre')
            municipios = [
                {
                    'id': m.id,
                    'nombre': m.nombre,
                    'estado_id': m.estado_id,
                    'estado_nombre': m.estado.nombre
                }
                for m in municipios
            ]
            return Response(municipios, status=status.HTTP_200_OK)
        
        return Response(list(municipios), status=status.HTTP_200_OK)


class MapaEstadisticasView(APIView):
    """
    Endpoint para obtener estadísticas geográficas agregadas por municipio
    para visualización en mapa interactivo.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db.models import Q
        
        # Obtener parámetros de filtro opcionales
        year = request.query_params.get('year')
        marca = request.query_params.get('marca')
        condicion = request.query_params.get('condicion')
        
        # Construir queryset base
        queryset = Ciclo.objects.select_related(
            'terreno__municipio__estado',
            'hibrido',
            'laboratorio'
        ).all()
        
        # Aplicar filtros si existen
        if year:
            if not year.isdigit():
                raise ValidationError({'year': 'Debe ser un año numérico.'})
            queryset = queryset.filter(year=int(year))
        if marca:
            queryset = queryset.filter(hibrido__marca__iexact=marca)
        if condicion:
            queryset = queryset.filter(condicion__iexact=condicion)
        
        # Agrupar por municipio y calcular estadísticas
        municipios_stats = queryset.values(
            'terreno__municipio__id',
            'terreno__municipio__nombre',
            'terreno__municipio__estado__nombre'
        ).annotate(
            total_ciclos=Count('id'),
            avg_rms=Avg('laboratorio__rms'),
            avg_ms=Avg('laboratorio__ms'),
            avg_pc=Avg('laboratorio__pc'),
            avg_gc=Avg('laboratorio__gc'),
            avg_cen=Avg('laboratorio__cen'),
            avg_fdn=Avg('laboratorio__fdn'),
            avg_cnf=Avg('laboratorio__cnf'),
            # Calcular coordenadas promedio del municipio
            avg_lat=Avg('terreno__latitud_gps'),
            avg_lon=Avg('terreno__longitud_gps')
        ).filter(total_ciclos__gt=0)

        # Formatear respuesta para el mapa
        features = []
        for stat in municipios_stats:
            datos = datos_milk2024(
                stat['avg_ms'], stat['avg_pc'], stat['avg_gc'],
                stat['avg_cen'], stat['avg_fdn'], stat['avg_cnf'], stat['avg_rms'] or 0.0,
            )
            leche_ha = calcular_metricas_milk2024(datos)['leche_ha']

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        float(stat['avg_lon']) if stat['avg_lon'] else -103.5,
                        float(stat['avg_lat']) if stat['avg_lat'] else 20.7
                    ]
                },
                'properties': {
                    'municipio_id': stat['terreno__municipio__id'],
                    'municipio': stat['terreno__municipio__nombre'],
                    'estado': stat['terreno__municipio__estado__nombre'],
                    'total_ciclos': stat['total_ciclos'],
                    'avg_rms': round(float(stat['avg_rms'] or 0), 2),
                    'avg_ms': round(float(stat['avg_ms'] or 0), 2),
                    'avg_pc': round(float(stat['avg_pc'] or 0), 2),
                    'avg_fdn': round(float(stat['avg_fdn'] or 0), 2),
                    'leche_ha': round(leche_ha, 2)
                }
            }
            features.append(feature)
        
        # Retornar en formato GeoJSON
        return Response({
            'type': 'FeatureCollection',
            'features': features
        }, status=status.HTTP_200_OK)


# =============================================================================
# SOIL MOISTURE ML PIPELINE  (SMAP + Daymet → LSTM → Recommendation)
# =============================================================================
import json
import math
import os
from datetime import date

from django.conf import settings

from .ml.plot_registry import JALISCO_PLOTS, snap_to_nearest_plot
from .ml.ml_engine import SM_HUMEDO, SM_SECO, run_inference
from .models import SoilMoisturePlot


# ---------------------------------------------------------------------------
# Helper: build corn recommendation from moisture profile
# ---------------------------------------------------------------------------
def _corn_recommendation(mean_sm: float, dry_days: int, wet_days: int,
                          min_sm: float, max_sm: float) -> dict:
    """
    Baseline hybrid-corn advisory derived from the estimated annual
    soil-moisture profile. Uses the project thresholds SM_SECO / SM_HUMEDO
    (ml_engine); 0.20 marks the upper edge of the marginal band.
    """
    year_days = 366  # 2024 was a leap year

    stress_pct = round(dry_days / year_days * 100, 1)
    excess_pct = round(wet_days / year_days * 100, 1)

    # Irrigation scheduling advice
    if mean_sm < SM_SECO:
        irrigation = "Alto riesgo de estrés hídrico. Se recomienda riego suplementario cada 5–7 días durante fases vegetativas."
        regimen = "Riego"
    elif mean_sm < 0.20:
        irrigation = "Humedad marginal. Monitoreo semanal recomendado; activar riego si sm < 0.18 m³/m³."
        regimen = "Riego"
    elif mean_sm <= SM_HUMEDO:
        irrigation = "Humedad óptima para maíz. Riego de precisión en floración (R1-R3) únicamente."
        regimen = "Temporal"
    else:
        irrigation = "Exceso de humedad detectado. Verificar drenaje para prevenir anoxia radicular."
        regimen = "Temporal"

    # Hybrid selection guidance
    if dry_days > 90:
        hybrid_note = "Seleccionar híbridos con tolerancia a sequía (ej. H-567, DK-7088)."
    elif wet_days > 120:
        hybrid_note = "Preferir híbridos con resistencia a enfermedades foliares en condiciones húmedas (ej. P3553W)."
    else:
        hybrid_note = "Perfil hídrico equilibrado. Híbridos de alto potencial como DK-2038 o ASGROW-780."

    # Planting window
    if mean_sm > 0.22:
        planting_window = "15 Abril – 15 Mayo (humedad de siembra adecuada)"
    else:
        planting_window = "1 Mayo – 1 Junio (esperar inicio de lluvias para garantizar germinación)"

    return {
        "regimen_recomendado": regimen,
        "irrigacion": irrigation,
        "hibrido_sugerido": hybrid_note,
        "ventana_siembra": planting_window,
        "alerta_estres_hidrico": stress_pct > 20,
        "alerta_exceso_humedad": excess_pct > 30,
        "dias_estres_pct": stress_pct,
        "dias_exceso_pct": excess_pct,
        "rango_optimo_pct": round(
            (year_days - dry_days - wet_days) / year_days * 100, 1
        ),
    }


class SoilMoistureAnalysisView(APIView):
    """
    POST /api/soil-moisture/
    -----------------------
    Accepts a user's GPS pin, snaps it to the nearest of the 11 pre-loaded
    Jalisco municipality plots, runs the LSTM inference pipeline, and returns
    a full soil-moisture time-series with a corn recommendation payload.

    Request body:
        { "lat": 20.65, "lon": -103.35 }

    Response 200:
        {
          "snapped_plot": { id, name, lat, lon, distance_km },
          "timeseries": [ { "date": "2024-01-01", "soil_moisture": 0.27 }, … ],
          "metrics": { mean_sm, min_sm, max_sm, dry_days, wet_days, model_backend },
          "recommendation": { … }
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # --- 1. Validate input ---
        try:
            user_lat = float(request.data.get("lat"))
            user_lon = float(request.data.get("lon"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Se requieren campos 'lat' y 'lon' numéricos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- 2. Spatial snap: nearest Jalisco plot via Haversine ---
        snapped = snap_to_nearest_plot(user_lat, user_lon)
        best_plot = snapped
        best_dist = snapped["distance_km"]

        # --- 3. Check day-level cache in DB ---
        today = date.today()
        cached = SoilMoisturePlot.objects.filter(
            plot_id=best_plot["id"], analysis_date=today
        ).first()

        if cached:
            ts = json.loads(cached.timeseries_json) if cached.timeseries_json else []
            metrics = {
                "mean_sm": cached.mean_sm,
                "min_sm":  cached.min_sm,
                "max_sm":  cached.max_sm,
                "dry_days":  cached.dry_days,
                "wet_days":  cached.wet_days,
                "model_backend": cached.model_backend,
            }
            recommendation = _corn_recommendation(
                cached.mean_sm or 0.25,
                cached.dry_days or 0,
                cached.wet_days or 0,
                cached.min_sm or 0.05,
                cached.max_sm or 0.55,
            )
            return Response({
                "snapped_plot": {
                    "id": best_plot["id"],
                    "name": best_plot["name"],
                    "lat": best_plot["lat"],
                    "lon": best_plot["lon"],
                    "distance_km": round(best_dist, 2),
                },
                "timeseries": ts,
                "metrics": metrics,
                "recommendation": recommendation,
                "cache": True,
            }, status=status.HTTP_200_OK)

        # --- 4. Resolve data file paths ---
        default_smap = os.path.join(
            settings.BASE_DIR, "data",
            "CropAnalytics-BOB-SMAP-2024-SPL3SMP-E-006-results.csv"
        )
        master_csv  = getattr(settings, "ML_SMAP_MASTER_CSV", default_smap)
        daymet_csv  = getattr(settings, "ML_DAYMET_CSV", None)

        try:
            result = run_inference(best_plot["smap_id"], master_csv, daymet_csv)
        except FileNotFoundError:
            return Response(
                {
                    "detail": (
                        f"Archivo CSV maestro SMAP no encontrado. "
                        f"Ruta esperada: {master_csv}"
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            return Response(
                {"detail": f"Error en el motor de inferencia: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --- 5. Build timeseries list (includes raw SMAP column) ---
        timeseries = [
            {
                "date": d,
                "soil_moisture": sm,
                "smap_raw": raw,
            }
            for d, sm, raw in zip(
                result["dates"], result["soil_moisture"], result["smap_raw"]
            )
        ]

        metrics = {
            "mean_sm":         result["mean_sm"],
            "min_sm":          result["min_sm"],
            "max_sm":          result["max_sm"],
            "dry_days":        result["dry_days"],
            "wet_days":        result["wet_days"],
            "valid_smap_days": result["valid_smap_days"],
            "has_daymet":      result["has_daymet"],
            "model_backend":   result["model_backend"],
        }

        recommendation = _corn_recommendation(
            result["mean_sm"],
            result["dry_days"],
            result["wet_days"],
            result["min_sm"],
            result["max_sm"],
        )

        # --- 6. Persist result (upsert on unique_together) ---
        SoilMoisturePlot.objects.update_or_create(
            plot_id=best_plot["id"],
            analysis_date=today,
            defaults={
                "plot_name": best_plot["name"],
                "latitude": best_plot["lat"],
                "longitude": best_plot["lon"],
                "mean_sm": result["mean_sm"],
                "min_sm":  result["min_sm"],
                "max_sm":  result["max_sm"],
                "dry_days":  result["dry_days"],
                "wet_days":  result["wet_days"],
                "model_backend": result["model_backend"],
                "timeseries_json": json.dumps(timeseries),
            },
        )

        return Response({
            "snapped_plot": {
                "id": best_plot["id"],
                "smap_id": best_plot["smap_id"],
                "name": best_plot["name"],
                "lat": best_plot["lat"],
                "lon": best_plot["lon"],
                "distance_km": round(best_dist, 2),
            },
            "timeseries": timeseries,
            "metrics": metrics,
            "recommendation": recommendation,
            "cache": False,
        }, status=status.HTTP_200_OK)


class PlotListView(APIView):
    """
    GET /api/soil-moisture/plots/
    Lists all 11 pre-loaded Jalisco municipality plots.
    Useful for frontend map initialisation.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(JALISCO_PLOTS, status=status.HTTP_200_OK)


# =============================================================================
# HYBRID RECOMMENDATION WITH SOIL MOISTURE CONTEXT
# =============================================================================
from .utils.hybrid_recommender import recomendar_hibridos


class RecomendacionHumedadView(APIView):
    """
    POST /api/recomendacion-humedad/
    --------------------------------
    Accepts user plot parameters and returns a ranked list of hybrid varieties
    scored against both MILK2024 performance and estimated soil moisture
    compatibility.

    Request body:
        {
          "lat":           20.74,           # GPS pin latitude
          "lon":           -102.83,         # GPS pin longitude
          "extension_ha":  5.0,             # plot size in hectares
          "has_irrigation": false,          # true = "Riego", false = "Temporal"
          "year":          2024,            # optional, default 2024
          "precio_ensilaje": 2800.0,        # optional market price overrides
          "precio_leche":    10.50,
          "costo_produccion": 1800.0,
          "costo_transporte": 150.0
        }

    Response 200:
        {
          "snapped_plot":    { id, smap_id, name, lat, lon, distance_km },
          "sm_profile":      { annual_mean_sm, growing_mean_sm, stress_index,
                               rainfed_suitability, is_real_data, model_backend },
          "sm_warning":      str | null,
          "condicion":       "Temporal" | "Riego",
          "year":            int,
          "extension_ha":    float,
          "ranking":         [
            {
              "hibrido":               { id, nombre, marca },
              "n_ciclos_historicos":   int,
              "rendimiento":           { historico_dm_ha, ajustado_sm_dm_ha,
                                         factor_ajuste_sm, total_dm_plot, avg_dff },
              "bromatologia":          { ms, cp, ee, ash, ndf },
              "milk2024":              { ... },
              "analisis_economico":    { ... },
              "score":                 float
            }, …
          ],
          "nota_proyeccion": str | null
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # --- Validate required inputs ---
        try:
            lat          = float(request.data.get("lat"))
            lon          = float(request.data.get("lon"))
            extension_ha = float(request.data.get("extension_ha", 1.0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Se requieren 'lat', 'lon' y 'extension_ha' numéricos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        has_irrigation = request.data.get("has_irrigation", False)
        if isinstance(has_irrigation, str):
            has_irrigation = has_irrigation.lower() in ("true", "1", "yes")
        has_irrigation = bool(has_irrigation)

        try:
            year = int(request.data.get("year", 2024))
        except (TypeError, ValueError):
            year = 2024

        if extension_ha <= 0:
            return Response(
                {"detail": "'extension_ha' debe ser mayor que cero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        precios = _precios_mercado(request)

        try:
            result = recomendar_hibridos(
                lat=lat,
                lon=lon,
                extension_ha=extension_ha,
                has_irrigation=has_irrigation,
                year=year,
                precios_mercado=precios,
            )
        except FileNotFoundError as exc:
            return Response(
                {"detail": f"Archivo de datos no encontrado: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            return Response(
                {"detail": f"Error en el motor de recomendación: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)
