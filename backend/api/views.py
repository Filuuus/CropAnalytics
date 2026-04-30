from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import Terreno, Ciclo
from .serializers import TerrenoGeoSerializer, CicloSerializer

class TerrenoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve la lista de terrenos.
    Optimizado con select_related para evitar N+1 queries al cargar municipio y estado.
    """
    queryset = Terreno.objects.select_related('municipio__estado').all()
    serializer_class = TerrenoGeoSerializer

class CicloViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Devuelve los ciclos agrícolas.
    Optimizado con select_related para cargar híbrido y laboratorio en una sola consulta.
    """
    serializer_class = CicloSerializer

    def get_queryset(self):
        # Cargamos hibrido y laboratorio de antemano para máxima velocidad
        queryset = Ciclo.objects.select_related('hibrido', 'laboratorio').all()
        
        # Permitir filtrar por ID de terreno desde la URL
        terreno_id = self.request.query_params.get('terreno', None)
        if terreno_id is not None:
            queryset = queryset.filter(terreno_id=terreno_id)
        return queryset