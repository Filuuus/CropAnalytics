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
from .models import Hibrido, ResultadoLaboratorio

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
        yield_dm = request.data.get('yield_dm')
        regimen_hidrico = request.data.get('regimen_hidrico')

        if yield_dm is None or not regimen_hidrico:
            return Response(
                {'detail': 'yield_dm y regimen_hidrico son campos obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            yield_dm = float(yield_dm)
        except ValueError:
            return Response(
                {'detail': 'yield_dm debe ser un número válido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if regimen_hidrico not in ['Riego', 'Temporal']:
            return Response(
                {'detail': 'regimen_hidrico debe ser "Riego" o "Temporal".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar todos los híbridos
        hybrids = Hibrido.objects.all()
        ranking = []

        for h in hybrids:
            # Filtrar los ciclos de este híbrido por el régimen hídrico
            ciclos_hibrido = Ciclo.objects.filter(hibrido=h, condicion__iexact=regimen_hidrico)
            if not ciclos_hibrido.exists():
                continue

            # Obtener promedios químicos y fenológicos (DFF)
            averages = ResultadoLaboratorio.objects.filter(ciclo__in=ciclos_hibrido).aggregate(
                avg_ms=Avg('ms'),
                avg_pc=Avg('pc'),
                avg_gc=Avg('gc'),
                avg_cen=Avg('cen'),
                avg_fdn=Avg('fdn'),
                avg_dff=Avg('dff')
            )

            # Si no hay resultados de laboratorio para este híbrido en este régimen, usar fallbacks
            avg_ms = averages['avg_ms'] or 35.0
            avg_pc = averages['avg_pc'] or 8.5
            avg_gc = averages['avg_gc'] or 3.2
            avg_cen = averages['avg_cen'] or 4.0
            avg_fdn = averages['avg_fdn'] or 42.0
            avg_dff = averages['avg_dff'] or 65.0  # promedio de días a floración femenina

            # Duración del ciclo (fecha_cosecha - fecha_siembra)
            durations = []
            for c in ciclos_hibrido:
                if c.fecha_cosecha and c.fecha_siembra:
                    diff = (c.fecha_cosecha - c.fecha_siembra).days
                    if diff > 0:
                        durations.append(diff)
            
            duracion_promedio = int(sum(durations) / len(durations)) if durations else (140 if regimen_hidrico == 'Riego' else 120)

            # Lógica de procesamiento de fechas de siembra y cosecha con tolerancia
            import datetime

            fecha_siembra_list = [c.fecha_siembra for c in ciclos_hibrido if c.fecha_siembra]
            
            MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            def format_date(d):
                return f"{d.day} de {MESES[d.month - 1]}"

            if not fecha_siembra_list:
                # Fallback por si no hay fechas históricas registradas
                ref_siembra = datetime.date(2000, 5, 15) if regimen_hidrico == 'Riego' else datetime.date(2000, 6, 15)
                start_siembra = ref_siembra - datetime.timedelta(days=7)
                end_siembra = ref_siembra + datetime.timedelta(days=7)
            else:
                # Convertir todas las fechas a un año bisiesto común (2000) para ignorar el año
                dummy_dates = [datetime.date(2000, d.month, d.day) for d in fecha_siembra_list]
                
                # Encontrar el rango de fechas en el año dummy
                min_date = min(dummy_dates)
                max_date = max(dummy_dates)
                range_days = (max_date - min_date).days
                
                if range_days > 15:
                    # Usar el rango histórico real
                    start_siembra = min_date
                    end_siembra = max_date
                else:
                    # Rango menor o igual a 15 días o un solo registro: calcular promedio y aplicar buffer de +/- 7 días
                    day_of_year_list = [(d - datetime.date(2000, 1, 1)).days for d in dummy_dates]
                    avg_day = sum(day_of_year_list) / len(day_of_year_list)
                    avg_date = datetime.date(2000, 1, 1) + datetime.timedelta(days=int(avg_day))
                    
                    start_siembra = avg_date - datetime.timedelta(days=7)
                    end_siembra = avg_date + datetime.timedelta(days=7)

            # Ventana de Siembra Formateada
            ventana_siembra = f"{format_date(start_siembra)} - {format_date(end_siembra)}"

            # Ventana de Cosecha Dinámica: sumar la duración promedio del ciclo a los límites de siembra
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
                'ndfd': 58.0,       # Fallbacks estándar de Wisconsin
                'undf240': 15.0,
                'starch': 30.0,
                'starch_d': 75.0,
                'yield_dm': yield_dm,
            }

            # Calcular métricas MILK2024
            resultados = calcular_metricas_milk2024(datos)

            ranking.append({
                'hibrido': {
                    'id': h.id,
                    'nombre': h.nombre,
                    'marca': h.marca
                },
                'valores_bromatologicos_promedio': {
                    'ms': round(avg_ms, 2),
                    'cp': round(avg_pc, 2),
                    'ee': round(avg_gc, 2),
                    'ash': round(avg_cen, 2),
                    'ndf': round(avg_fdn, 2),
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
                **resultados
            })

        # Ordenar ranking por leche_ha descendente
        ranking.sort(key=lambda x: x['leche_ha'], reverse=True)

        return Response(ranking, status=status.HTTP_200_OK)
