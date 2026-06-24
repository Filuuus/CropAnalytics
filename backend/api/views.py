from django.shortcuts import render

# Create your views here.
from django.contrib.auth import get_user_model
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
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
    TerrenoGeoSerializer,
    UserRoleUpdateSerializer,
    UserSerializer,
)

User = get_user_model()


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
        if user.role == User.Role.JEFE and active_jefe_count(exclude_user=user) == 0:
            return Response(
                {'detail': 'No se puede eliminar al ultimo JEFE activo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.pk == request.user.pk and user.role == User.Role.JEFE and active_jefe_count(exclude_user=user) == 0:
            return Response(
                {'detail': 'No puedes eliminarte si eso deja el sistema sin JEFE.'},
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
    serializer_class = TerrenoGeoSerializer

class CicloViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve los ciclos agrícolas.
    Optimizado con select_related para cargar híbrido y laboratorio en una sola consulta.
    """
    permission_classes = [AllowAny]
    serializer_class = CicloSerializer

    def get_queryset(self):
        # Cargamos hibrido y laboratorio de antemano para máxima velocidad
        queryset = Ciclo.objects.select_related('hibrido', 'laboratorio').all()
        
        # Permitir filtrar por ID de terreno desde la URL
        terreno_id = self.request.query_params.get('terreno', None)
        if terreno_id is not None:
            queryset = queryset.filter(terreno_id=terreno_id)
        return queryset

from django.db.models import Avg
from .utils.milk_calculator import calcular_metricas_milk2024
from .utils.geospatial_estimator import aplicar_ajuste_geoespacial
from .models import Hibrido, ResultadoLaboratorio, Terreno

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
            avg_fdn=Avg('fdn')
        )

        # Armar el payload para el calculador con fallbacks seguros
        datos = {
            'ms': averages['avg_ms'] or 35.0,
            'cp': averages['avg_pc'] or 8.5,
            'ee': averages['avg_gc'] or 3.2,
            'ash': averages['avg_cen'] or 4.0,
            'ndf': averages['avg_fdn'] or 42.0,
            'ndfd': 58.0,       # Fallbacks estándar de Wisconsin MILK2024
            'undf240': 15.0,
            'starch': 30.0,
            'starch_d': 75.0,
            'yield_dm': yield_dm,
        }

        # Calcular métricas MILK2024
        resultados = calcular_metricas_milk2024(datos)

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
            **resultados
        }, status=status.HTTP_200_OK)

class OptimizarSemillaView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        regimen_hidrico = request.data.get('regimen_hidrico')

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

        from django.db.models import Avg, F, ExpressionWrapper, fields, Value, FloatField, Min, Max, Case, When
        import datetime

        # Agrupar y promediar en una sola consulta ORM de alto rendimiento
        ciclos_stats = Ciclo.objects.filter(condicion__iexact=regimen_hidrico) \
            .values('hibrido__id', 'hibrido__nombre', 'hibrido__marca') \
            .annotate(
                avg_ms=Avg('laboratorio__ms'),
                avg_cp=Avg('laboratorio__pc'),
                avg_ee=Avg('laboratorio__gc'),
                avg_ash=Avg('laboratorio__cen'),
                avg_ndf=Avg('laboratorio__fdn'),
                avg_dff=Avg('laboratorio__dff'),
                tasa_supervivencia=Avg(
                    Case(
                        When(laboratorio__pem__gt=0, then=ExpressionWrapper(F('laboratorio__ppc') * 1.0 / F('laboratorio__pem'), output_field=fields.FloatField())),
                        default=None,
                        output_field=fields.FloatField()
                    )
                ),
                rendimiento_promedio=Avg('laboratorio__rms'),
                # Constantes de fallbacks mockeadas como anotaciones Value del ORM
                avg_ndfd=Value(58.0, output_field=fields.FloatField()),
                avg_undf240=Value(15.0, output_field=fields.FloatField()),
                avg_starch=Value(30.0, output_field=fields.FloatField()),
                avg_starch_d=Value(75.0, output_field=fields.FloatField()),
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
            )

        ranking = []
        MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

        def format_date(d):
            return f"{d.day} de {MESES[d.month - 1]}"

        for item in ciclos_stats:
            avg_ms = item['avg_ms'] or 35.0
            avg_pc = item['avg_cp'] or 8.5
            avg_gc = item['avg_ee'] or 3.2
            avg_cen = item['avg_ash'] or 4.0
            avg_fdn = item['avg_ndf'] or 42.0
            avg_dff = item['avg_dff'] or 65.0
            tasa_supervivencia = item['tasa_supervivencia']
            rendimiento_promedio = item['rendimiento_promedio'] or 20.0

            if tasa_supervivencia is not None:
                factor_supervivencia = min(1.0, float(tasa_supervivencia))
            else:
                factor_supervivencia = 1.0

            # Calcular el rendimiento real esperado: promedio_historico * factor_supervivencia
            rendimiento_real_esperado = float(rendimiento_promedio) * factor_supervivencia
            
            avg_ndfd = item['avg_ndfd']
            avg_undf240 = item['avg_undf240']
            avg_starch = item['avg_starch']
            avg_starch_d = item['avg_starch_d']

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

            # Preparar payload para MILK2024
            datos = {
                'ms': avg_ms,
                'cp': avg_pc,
                'ee': avg_gc,
                'ash': avg_cen,
                'ndf': avg_fdn,
                'ndfd': avg_ndfd,
                'undf240': avg_undf240,
                'starch': avg_starch,
                'starch_d': avg_starch_d,
                'yield_dm': rendimiento_real_esperado,
            }

            # Calcular métricas MILK2024
            resultados = calcular_metricas_milk2024(datos)

            ranking.append({
                'hibrido': {
                    'id': item['hibrido__id'],
                    'nombre': item['hibrido__nombre'],
                    'marca': item['hibrido__marca']
                },
                'valores_bromatologicos_promedio': {
                    'ms': round(avg_ms, 2),
                    'cp': round(avg_pc, 2),
                    'ee': round(avg_gc, 2),
                    'ash': round(avg_cen, 2),
                    'ndf': round(avg_fdn, 2),
                    'ndfd': avg_ndfd,
                    'undf240': avg_undf240,
                    'starch': avg_starch,
                    'starch_d': avg_starch_d
                },
                'dff_promedio': round(avg_dff, 1),
                'duracion_ciclo_promedio': duracion_promedio,
                'ventana_siembra': ventana_siembra,
                'ventana_cosecha': ventana_cosecha,
                'regimen_hidrico': regimen_hidrico,
                'factor_supervivencia': round(factor_supervivencia, 4),
                'rendimiento_real_esperado': round(rendimiento_real_esperado, 2),
                **resultados
            })

        # Ordenar ranking por leche_ha descendente
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
            avg_fdn=Avg('fdn')
        )

        # Preparar datos para el calculador
        datos = {
            'ms': averages['avg_ms'] or 35.0,
            'cp': averages['avg_pc'] or 8.5,
            'ee': averages['avg_gc'] or 3.2,
            'ash': averages['avg_cen'] or 4.0,
            'ndf': averages['avg_fdn'] or 42.0,
            'ndfd': 58.0,
            'undf240': 15.0,
            'starch': 30.0,
            'starch_d': 75.0,
            'yield_dm': yield_dm,
        }

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
