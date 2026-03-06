from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import Terreno, Ciclo, ResultadoLaboratorio, DatoClimatico, Municipio, Hibrido

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

class CicloSerializer(serializers.ModelSerializer):
    hibrido_nombre = serializers.CharField(source='hibrido.nombre', read_only=True)
    
    class Meta:
        model = Ciclo
        fields = '__all__'