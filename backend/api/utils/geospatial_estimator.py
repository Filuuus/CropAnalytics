"""
Módulo de Estimación Geoespacial para Sentineli
Proporciona ajustes de rendimiento basados en ubicación geográfica del campo.
"""
import math
from typing import Dict, Tuple, Optional, Any


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia en kilómetros entre dos puntos geográficos usando la fórmula de Haversine.
    
    Args:
        lat1, lon1: Coordenadas del primer punto (grados)
        lat2, lon2: Coordenadas del segundo punto (grados)
    
    Returns:
        Distancia en kilómetros
    """
    R = 6371  # Radio de la Tierra en km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def clasificar_zona_climatica(latitud: float, altitud: Optional[float] = None) -> Dict[str, Any]:
    """
    Clasifica la zona climática basada en latitud y altitud.
    
    Args:
        latitud: Latitud en grados
        altitud: Altitud en metros sobre el nivel del mar (opcional)
    
    Returns:
        Diccionario con clasificación climática y factores de ajuste
    """
    lat_abs = abs(latitud)
    
    # Clasificación por latitud (México está entre 14°N y 32°N)
    if lat_abs < 18:
        zona_lat = "Tropical"
        factor_lat = 0.92  # Menor rendimiento por calor excesivo
    elif lat_abs < 24:
        zona_lat = "Subtropical"
        factor_lat = 1.00  # Zona óptima
    elif lat_abs < 28:
        zona_lat = "Templada"
        factor_lat = 1.05  # Ligeramente mejor por temperaturas moderadas
    else:
        zona_lat = "Templada-Fría"
        factor_lat = 0.95  # Menor rendimiento por temperaturas más bajas
    
    # Ajuste por altitud si está disponible
    factor_alt = 1.0
    zona_alt = "No especificada"
    
    if altitud is not None:
        if altitud < 500:
            zona_alt = "Tierras bajas"
            factor_alt = 0.95  # Calor excesivo puede afectar
        elif altitud < 1500:
            zona_alt = "Tierras medias"
            factor_alt = 1.05  # Zona óptima para maíz
        elif altitud < 2500:
            zona_alt = "Tierras altas"
            factor_alt = 1.00  # Buena zona
        else:
            zona_alt = "Tierras muy altas"
            factor_alt = 0.90  # Temperaturas bajas limitan crecimiento
    
    # Factor combinado
    factor_combinado = factor_lat * factor_alt
    
    return {
        'zona_latitud': zona_lat,
        'zona_altitud': zona_alt,
        'factor_latitud': round(factor_lat, 3),
        'factor_altitud': round(factor_alt, 3),
        'factor_combinado': round(factor_combinado, 3),
        'descripcion': f"Zona {zona_lat}" + (f" - {zona_alt}" if altitud else "")
    }


def estimar_ajuste_regional(latitud: float, longitud: float, altitud: Optional[float] = None) -> Dict[str, Any]:
    """
    Estima ajustes de rendimiento basados en la ubicación geográfica del campo.
    Utiliza datos históricos de zonas productoras de maíz en México.
    
    Args:
        latitud: Latitud del campo (grados)
        longitud: Longitud del campo (grados)
        altitud: Altitud del campo en msnm (opcional)
    
    Returns:
        Diccionario con factores de ajuste y recomendaciones
    """
    # Zonas de referencia de alta producción en México
    zonas_referencia = {
        'Sinaloa': {'lat': 25.0, 'lon': -107.5, 'rendimiento_ref': 1.10},
        'Jalisco': {'lat': 20.5, 'lon': -103.5, 'rendimiento_ref': 1.05},
        'Michoacán': {'lat': 19.5, 'lon': -101.5, 'rendimiento_ref': 1.03},
        'Guanajuato': {'lat': 21.0, 'lon': -101.0, 'rendimiento_ref': 1.02},
        'Estado de México': {'lat': 19.5, 'lon': -99.5, 'rendimiento_ref': 1.00},
    }
    
    # Encontrar la zona de referencia más cercana
    zona_cercana = "Estado de México"  # Default
    distancia_minima = float('inf')
    factor_regional = 1.0  # Default
    
    for nombre, zona in zonas_referencia.items():
        distancia = calcular_distancia_haversine(latitud, longitud, zona['lat'], zona['lon'])
        if distancia < distancia_minima:
            distancia_minima = distancia
            zona_cercana = nombre
            factor_regional = zona['rendimiento_ref']
    
    # Ajustar factor según distancia a zona de referencia
    # Cada 100 km de distancia reduce el factor en 1%
    ajuste_distancia = max(0.85, 1.0 - (distancia_minima / 10000))
    factor_regional_ajustado = factor_regional * ajuste_distancia
    
    # Clasificación climática
    clasificacion = clasificar_zona_climatica(latitud, altitud)
    
    # Factor de ajuste final combinando región y clima
    factor_final = (factor_regional_ajustado + clasificacion['factor_combinado']) / 2
    
    # Determinar nivel de confianza geoespacial
    if distancia_minima < 100:
        confianza_geo = "Alta"
        confianza_valor = 95
    elif distancia_minima < 300:
        confianza_geo = "Media-Alta"
        confianza_valor = 85
    elif distancia_minima < 500:
        confianza_geo = "Media"
        confianza_valor = 75
    else:
        confianza_geo = "Baja"
        confianza_valor = 60
    
    # Generar recomendaciones
    recomendaciones = []
    
    if clasificacion['zona_latitud'] == "Tropical":
        recomendaciones.append("Considerar híbridos tolerantes a calor")
    elif clasificacion['zona_latitud'] == "Templada-Fría":
        recomendaciones.append("Seleccionar híbridos de ciclo corto")
    
    if altitud and altitud > 2000:
        recomendaciones.append("Monitorear heladas tempranas")
    elif altitud and altitud < 500:
        recomendaciones.append("Implementar riego eficiente por altas temperaturas")
    
    if distancia_minima > 300:
        recomendaciones.append("Validar con datos locales de la región")
    
    return {
        'factor_ajuste_geoespacial': round(factor_final, 3),
        'zona_referencia_cercana': zona_cercana,
        'distancia_zona_referencia_km': round(distancia_minima, 1),
        'clasificacion_climatica': clasificacion,
        'confianza_geoespacial': confianza_geo,
        'confianza_geoespacial_valor': confianza_valor,
        'recomendaciones': recomendaciones,
        'coordenadas': {
            'latitud': round(latitud, 6),
            'longitud': round(longitud, 6),
            'altitud_msnm': altitud if altitud else 'No especificada'
        }
    }


def aplicar_ajuste_geoespacial(rendimiento_base: float, latitud: float, longitud: float, 
                                altitud: Optional[float] = None) -> Dict[str, Any]:
    """
    Aplica ajustes geoespaciales al rendimiento base estimado.
    
    Args:
        rendimiento_base: Rendimiento estimado sin ajuste geoespacial (ton/ha)
        latitud: Latitud del campo
        longitud: Longitud del campo
        altitud: Altitud del campo (opcional)
    
    Returns:
        Diccionario con rendimiento ajustado y detalles del ajuste
    """
    ajuste_info = estimar_ajuste_regional(latitud, longitud, altitud)
    factor = ajuste_info['factor_ajuste_geoespacial']
    
    rendimiento_ajustado = rendimiento_base * factor
    diferencia = rendimiento_ajustado - rendimiento_base
    porcentaje_cambio = ((rendimiento_ajustado / rendimiento_base) - 1) * 100 if rendimiento_base > 0 else 0
    
    return {
        'rendimiento_base': round(rendimiento_base, 2),
        'rendimiento_ajustado': round(rendimiento_ajustado, 2),
        'diferencia_ton_ha': round(diferencia, 2),
        'porcentaje_ajuste': round(porcentaje_cambio, 1),
        'factor_aplicado': factor,
        'detalles_geoespaciales': ajuste_info
    }

# Made with Bob
