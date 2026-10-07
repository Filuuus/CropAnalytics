"""
Sistema de Recomendación de Híbridos Basado en Ubicación Geográfica
Integra datos históricos regionales con el sistema de confianza MILK2024
"""
from typing import Dict, List, Optional, Any, Tuple
from django.db.models import Count, Avg, Q
from .geospatial_estimator import calcular_distancia_haversine, clasificar_zona_climatica


def calcular_relevancia_regional(
    hibrido_id: int,
    estado_id: Optional[int] = None,
    municipio_id: Optional[int] = None,
    latitud: Optional[float] = None,
    longitud: Optional[float] = None,
    altitud: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calcula la relevancia regional de un híbrido para una ubicación específica.
    
    Factores de ponderación:
    - Rendimiento histórico en región seleccionada (40%)
    - Rendimiento en regiones cercanas (30%)
    - Similitud climática (20%)
    - Compatibilidad de altitud (10%)
    
    Args:
        hibrido_id: ID del híbrido a evaluar
        estado_id: ID del estado (opcional)
        municipio_id: ID del municipio (opcional)
        latitud: Latitud del terreno (opcional)
        longitud: Longitud del terreno (opcional)
        altitud: Altitud del terreno en msnm (opcional)
    
    Returns:
        Diccionario con score de relevancia regional y detalles
    """
    from ..models import Ciclo, Terreno, Municipio, Estado
    
    # Inicializar scores
    score_local = 0.0
    score_regional = 0.0
    score_climatico = 0.0
    score_altitud = 0.0
    
    muestras_locales = 0
    muestras_regionales = 0
    distancia_promedio_km = None
    
    # 1. ANÁLISIS LOCAL (40%) - Mismo municipio
    if municipio_id:
        ciclos_locales = Ciclo.objects.filter(
            hibrido_id=hibrido_id,
            terreno__municipio_id=municipio_id
        ).select_related('laboratorio')
        
        muestras_locales = ciclos_locales.count()
        
        if muestras_locales > 0:
            # Calcular rendimiento promedio local
            rendimiento_local = ciclos_locales.aggregate(
                avg_rms=Avg('laboratorio__rms')
            )['avg_rms'] or 0.0
            
            # Score basado en cantidad de muestras y rendimiento
            # Más muestras = mayor confianza
            if muestras_locales >= 10:
                score_local = 100.0
            elif muestras_locales >= 5:
                score_local = 85.0
            elif muestras_locales >= 3:
                score_local = 70.0
            else:
                score_local = 50.0
            
            # Ajustar por rendimiento relativo
            if rendimiento_local > 22.0:  # Excelente
                score_local = min(100.0, score_local * 1.1)
            elif rendimiento_local < 15.0:  # Bajo
                score_local *= 0.9
    
    # 2. ANÁLISIS REGIONAL (30%) - Mismo estado o estados cercanos
    if estado_id:
        # Ciclos en el mismo estado
        ciclos_estado = Ciclo.objects.filter(
            hibrido_id=hibrido_id,
            terreno__municipio__estado_id=estado_id
        ).exclude(
            terreno__municipio_id=municipio_id if municipio_id else None
        ).select_related('laboratorio', 'terreno')
        
        muestras_estado = ciclos_estado.count()
        muestras_regionales = muestras_estado
        
        if muestras_estado > 0:
            rendimiento_estado = ciclos_estado.aggregate(
                avg_rms=Avg('laboratorio__rms')
            )['avg_rms'] or 0.0
            
            # Score basado en muestras regionales
            if muestras_estado >= 20:
                score_regional = 100.0
            elif muestras_estado >= 10:
                score_regional = 85.0
            elif muestras_estado >= 5:
                score_regional = 70.0
            else:
                score_regional = 50.0
            
            # Ajustar por rendimiento
            if rendimiento_estado > 22.0:
                score_regional = min(100.0, score_regional * 1.1)
            elif rendimiento_estado < 15.0:
                score_regional *= 0.9
            
            # Calcular distancia promedio si tenemos coordenadas
            if latitud and longitud:
                distancias = []
                for ciclo in ciclos_estado[:20]:  # Limitar a 20 para performance
                    if ciclo.terreno.latitud_gps and ciclo.terreno.longitud_gps:
                        dist = calcular_distancia_haversine(
                            latitud, longitud,
                            ciclo.terreno.latitud_gps, ciclo.terreno.longitud_gps
                        )
                        distancias.append(dist)
                
                if distancias:
                    distancia_promedio_km = sum(distancias) / len(distancias)
                    
                    # Ajustar score por proximidad
                    if distancia_promedio_km < 50:
                        score_regional = min(100.0, score_regional * 1.15)
                    elif distancia_promedio_km > 200:
                        score_regional *= 0.85
    
    # 3. ANÁLISIS CLIMÁTICO (20%) - Similitud de zona climática
    if latitud and altitud:
        clasificacion = clasificar_zona_climatica(latitud, altitud)
        
        # Obtener zonas climáticas de ciclos históricos del híbrido
        ciclos_hibrido = Ciclo.objects.filter(
            hibrido_id=hibrido_id
        ).select_related('terreno')[:50]
        
        zonas_compatibles = 0
        total_zonas = 0
        
        for ciclo in ciclos_hibrido:
            if ciclo.terreno.latitud_gps and ciclo.terreno.altitud:
                total_zonas += 1
                clasificacion_ciclo = clasificar_zona_climatica(
                    ciclo.terreno.latitud_gps,
                    ciclo.terreno.altitud
                )
                
                # Comparar zonas
                if clasificacion['zona_latitud'] == clasificacion_ciclo['zona_latitud']:
                    zonas_compatibles += 1
                if clasificacion['zona_altitud'] == clasificacion_ciclo['zona_altitud']:
                    zonas_compatibles += 0.5
        
        if total_zonas > 0:
            compatibilidad = (zonas_compatibles / (total_zonas * 1.5)) * 100
            score_climatico = min(100.0, compatibilidad)
        else:
            score_climatico = 50.0  # Neutral si no hay datos
    else:
        score_climatico = 50.0  # Neutral sin datos de ubicación
    
    # 4. ANÁLISIS DE ALTITUD (10%) - Compatibilidad de altitud
    if altitud:
        # Obtener rango de altitudes donde el híbrido ha sido probado
        altitudes_hibrido = Ciclo.objects.filter(
            hibrido_id=hibrido_id,
            terreno__altitud__isnull=False
        ).values_list('terreno__altitud', flat=True)
        
        if altitudes_hibrido:
            altitudes_list = list(altitudes_hibrido)
            alt_min = min(altitudes_list)
            alt_max = max(altitudes_list)
            alt_promedio = sum(altitudes_list) / len(altitudes_list)
            
            # Calcular compatibilidad
            if alt_min <= altitud <= alt_max:
                # Dentro del rango probado
                diferencia_promedio = abs(altitud - alt_promedio)
                if diferencia_promedio < 200:
                    score_altitud = 100.0
                elif diferencia_promedio < 500:
                    score_altitud = 85.0
                else:
                    score_altitud = 70.0
            else:
                # Fuera del rango probado
                if altitud < alt_min:
                    diferencia = alt_min - altitud
                else:
                    diferencia = altitud - alt_max
                
                if diferencia < 300:
                    score_altitud = 60.0
                elif diferencia < 600:
                    score_altitud = 40.0
                else:
                    score_altitud = 20.0
        else:
            score_altitud = 50.0  # Neutral sin datos
    else:
        score_altitud = 50.0  # Neutral sin datos de altitud
    
    # CALCULAR SCORE FINAL PONDERADO
    score_final = (
        score_local * 0.40 +
        score_regional * 0.30 +
        score_climatico * 0.20 +
        score_altitud * 0.10
    )
    
    # Determinar nivel de relevancia
    if score_final >= 85:
        nivel = "Alta"
    elif score_final >= 70:
        nivel = "Media-Alta"
    elif score_final >= 50:
        nivel = "Media"
    elif score_final >= 30:
        nivel = "Media-Baja"
    else:
        nivel = "Baja"
    
    # Calcular ajuste de confianza para el sistema MILK2024
    # Más datos locales = mayor confianza
    ajuste_confianza = 0.0
    
    if muestras_locales >= 10:
        ajuste_confianza = +8.0
    elif muestras_locales >= 5:
        ajuste_confianza = +5.0
    elif muestras_locales >= 3:
        ajuste_confianza = +3.0
    elif muestras_locales > 0:
        ajuste_confianza = +1.0
    
    if muestras_regionales >= 20:
        ajuste_confianza += 4.0
    elif muestras_regionales >= 10:
        ajuste_confianza += 2.0
    elif muestras_regionales >= 5:
        ajuste_confianza += 1.0
    
    # Penalizar si no hay datos locales ni regionales
    if muestras_locales == 0 and muestras_regionales == 0:
        ajuste_confianza = -10.0
    elif muestras_locales == 0 and muestras_regionales < 5:
        ajuste_confianza = -5.0
    
    # Limitar ajuste a ±15%
    ajuste_confianza = max(-15.0, min(15.0, ajuste_confianza))
    
    return {
        'score': round(score_final, 1),
        'nivel': nivel,
        'muestras_locales': muestras_locales,
        'muestras_regionales': muestras_regionales,
        'distancia_promedio_km': round(distancia_promedio_km, 1) if distancia_promedio_km else None,
        'ajuste_confianza': round(ajuste_confianza, 1),
        'desglose_scores': {
            'local': round(score_local, 1),
            'regional': round(score_regional, 1),
            'climatico': round(score_climatico, 1),
            'altitud': round(score_altitud, 1)
        }
    }


def aplicar_relevancia_regional_a_confianza(
    confianza_base: Dict[str, Any],
    relevancia_regional: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ajusta el factor de confianza MILK2024 basado en la relevancia regional.
    
    Args:
        confianza_base: Diccionario de confianza del sistema MILK2024
        relevancia_regional: Diccionario de relevancia regional
    
    Returns:
        Diccionario de confianza ajustado
    """
    factor_base = confianza_base.get('factor_confianza', 50.0)
    ajuste = relevancia_regional.get('ajuste_confianza', 0.0)
    
    # Aplicar ajuste
    factor_ajustado = factor_base + ajuste
    factor_ajustado = max(0.0, min(100.0, factor_ajustado))
    
    # Actualizar nivel si cambió significativamente
    if factor_ajustado >= 85:
        nivel = "Excelente"
        color = "green"
    elif factor_ajustado >= 70:
        nivel = "Buena"
        color = "blue"
    elif factor_ajustado >= 50:
        nivel = "Moderada"
        color = "yellow"
    else:
        nivel = "Baja"
        color = "red"
    
    # Generar justificación del ajuste geográfico
    muestras_locales = relevancia_regional.get('muestras_locales', 0)
    muestras_regionales = relevancia_regional.get('muestras_regionales', 0)
    
    if ajuste > 0:
        if muestras_locales >= 5:
            ajuste_geografico = f"+{ajuste:.1f}% por {muestras_locales} muestras locales"
        elif muestras_regionales >= 10:
            ajuste_geografico = f"+{ajuste:.1f}% por {muestras_regionales} muestras regionales"
        else:
            ajuste_geografico = f"+{ajuste:.1f}% por datos regionales disponibles"
    elif ajuste < 0:
        ajuste_geografico = f"{ajuste:.1f}% por falta de datos locales/regionales"
    else:
        ajuste_geografico = "Sin ajuste geográfico"
    
    return {
        'factor_confianza': round(factor_ajustado, 1),
        'nivel_confianza': nivel,
        'color_indicador': color,
        'penalizaciones': confianza_base.get('penalizaciones', []),
        'advertencias': confianza_base.get('advertencias', []),
        'justificacion': confianza_base.get('justificacion', ''),
        'ajuste_geografico': ajuste_geografico,
        'factor_confianza_original': round(factor_base, 1)
    }


def obtener_ubicacion_desde_municipio(municipio_id: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Obtiene coordenadas representativas de un municipio basándose en terrenos existentes.
    
    Args:
        municipio_id: ID del municipio
    
    Returns:
        Tupla (latitud, longitud, altitud) o (None, None, None)
    """
    from ..models import Terreno
    
    # Obtener promedio de coordenadas de terrenos en el municipio
    terrenos = Terreno.objects.filter(municipio_id=municipio_id)
    
    if terrenos.exists():
        stats = terrenos.aggregate(
            avg_lat=Avg('latitud_gps'),
            avg_lon=Avg('longitud_gps'),
            avg_alt=Avg('altitud')
        )
        
        return (
            stats['avg_lat'],
            stats['avg_lon'],
            stats['avg_alt']
        )
    
    return (None, None, None)

# Made with Bob
