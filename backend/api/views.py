from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import Terreno, Ciclo
from .serializers import TerrenoGeoSerializer, CicloSerializer

class TerrenoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve la lista de terrenos.
    Gracias al TerrenoGeoSerializer, la salida será automáticamente en formato GeoJSON,
    perfecto para que tu compañero de frontend lo pinte en OpenLayers o Leaflet.
    """
    queryset = Terreno.objects.all()
    serializer_class = TerrenoGeoSerializer

class CicloViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve los ciclos agrícolas.
    Incluye un filtro para buscar los ciclos de un terreno específico.
    Ejemplo: /api/ciclos/?terreno=5
    """
    serializer_class = CicloSerializer

    def get_queryset(self):
        queryset = Ciclo.objects.all()
        # Permitir filtrar por ID de terreno desde la URL
        terreno_id = self.request.query_params.get('terreno', None)
        if terreno_id is not None:
            queryset = queryset.filter(terreno_id=terreno_id)
        return queryset