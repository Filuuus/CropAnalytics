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
