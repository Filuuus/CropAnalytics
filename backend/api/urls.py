from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TerrenoViewSet, CicloViewSet

# El Router de DRF crea automáticamente las URLs para listar y ver detalles
router = DefaultRouter()
router.register(r'terrenos', TerrenoViewSet, basename='terreno')
router.register(r'ciclos', CicloViewSet, basename='ciclo')

urlpatterns = [
    path('', include(router.urls)),
]