from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CicloViewSet,
    GoogleLoginView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    TerrenoViewSet,
    UserAdminViewSet,
)

# El Router de DRF crea automáticamente las URLs para listar y ver detalles
router = DefaultRouter()
router.register(r'terrenos', TerrenoViewSet, basename='terreno')
router.register(r'ciclos', CicloViewSet, basename='ciclo')
router.register(r'users', UserAdminViewSet, basename='user-admin')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/google/', GoogleLoginView.as_view(), name='auth-google'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('', include(router.urls)),
]
