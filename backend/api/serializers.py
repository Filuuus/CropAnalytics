from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import Terreno, Ciclo, ResultadoLaboratorio, DatoClimatico, Municipio, Hibrido
from .auth_utils import create_user_with_auto_role, is_initial_jefe

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='first_name')

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'provider', 'avatar', 'is_active', 'date_joined']
        read_only_fields = fields


def auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
        'role': user.role,
    }


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, min_length=2)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def create(self, validated_data):
        return create_user_with_auto_role(
            name=validated_data['name'],
            email=validated_data['email'],
            password=validated_data['password'],
            provider=User.Provider.LOCAL,
        )

    def to_representation(self, instance):
        return auth_payload(instance)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        user = User.objects.filter(email__iexact=email).first()
        if user and not user.is_active:
            raise serializers.ValidationError('La cuenta esta inhabilitada.')

        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=attrs['password'],
        )
        if not user:
            raise serializers.ValidationError('Correo o contrasena incorrectos.')
        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        return auth_payload(instance['user'])


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if not settings.GOOGLE_CLIENT_ID:
            raise serializers.ValidationError('GOOGLE_CLIENT_ID no esta configurado.')

        try:
            payload = id_token.verify_oauth2_token(
                attrs['credential'],
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as exc:
            raise serializers.ValidationError('Token de Google invalido.') from exc

        email = (payload.get('email') or '').lower().strip()
        if not email or not payload.get('email_verified'):
            raise serializers.ValidationError('Google no verifico este correo.')

        attrs['google_payload'] = payload
        attrs['email'] = email
        return attrs

    def save(self, **kwargs):
        payload = self.validated_data['google_payload']
        email = self.validated_data['email']
        user = User.objects.filter(email__iexact=email).first()
        if user:
            if not user.is_active:
                raise serializers.ValidationError('La cuenta esta inhabilitada.')
            changed = False
            if user.provider != User.Provider.GOOGLE:
                user.provider = User.Provider.GOOGLE
                changed = True
            picture = payload.get('picture')
            if picture and user.avatar != picture:
                user.avatar = picture
                changed = True
            if changed:
                user.save(update_fields=['provider', 'avatar'])
            return user

        return create_user_with_auto_role(
            name=payload.get('name') or email.split('@')[0],
            email=email,
            provider=User.Provider.GOOGLE,
            avatar=payload.get('picture'),
        )

    def to_representation(self, instance):
        return auth_payload(instance)


class AdminUserSerializer(UserSerializer):
    is_initial_jefe = serializers.SerializerMethodField()
    can_change_role = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['is_initial_jefe', 'can_change_role']

    def get_is_initial_jefe(self, obj):
        return is_initial_jefe(obj)

    def get_can_change_role(self, obj):
        return not is_initial_jefe(obj)


class UserRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[User.Role.JEFE, User.Role.INVESTIGADOR])

class MunicipioSerializer(serializers.ModelSerializer):
    estado_nombre = serializers.CharField(source='estado.nombre', read_only=True)

    class Meta:
        model = Municipio
        fields = ['id', 'nombre', 'estado_nombre']

# Este serializador especial convierte el Terreno en un GeoJSON perfecto para mapas
class TerrenoGeoSerializer(GeoFeatureModelSerializer):
    municipio_info = MunicipioSerializer(source='municipio', read_only=True)

    class Meta:
        model = Terreno
        geo_field = 'ubicacion_geo' # Le dice a DRF cuál es la coordenada
        fields = ['id', 'altitud', 'municipio_info']

class ResultadoLaboratorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultadoLaboratorio
        fields = '__all__'

class CicloSerializer(serializers.ModelSerializer):
    hibrido_nombre = serializers.CharField(source='hibrido.nombre', read_only=True)
    hibrido_marca = serializers.CharField(source='hibrido.marca', read_only=True)
    laboratorio_info = ResultadoLaboratorioSerializer(source='laboratorio', read_only=True)
    
    class Meta:
        model = Ciclo
        fields = '__all__'
