def calcular_factor_confianza(datos: dict, resultados_intermedios: dict) -> dict:
    """
    Calcula el factor de confianza de las estimaciones basado en:
    1. Completitud de datos de entrada
    2. Coherencia de valores nutricionales
    3. Validez de rangos esperados para ensilaje de maíz
    
    Retorna un diccionario con el factor de confianza (0-100) y justificación detallada.
    """
    confianza_base = 100.0
    penalizaciones = []
    advertencias = []
    
    # Verificar completitud de datos críticos
    datos_criticos = ['ms', 'cp', 'ndf', 'starch']
    datos_faltantes = [k for k in datos_criticos if datos.get(k, 0.0) == 0.0]
    
    if datos_faltantes:
        penalizacion = len(datos_faltantes) * 10
        confianza_base -= penalizacion
        penalizaciones.append(f"Datos críticos faltantes o en cero: {', '.join(datos_faltantes)} (-{penalizacion}%)")
    
    # Validar rangos esperados para ensilaje de maíz de calidad
    ms = datos.get('ms', 0.0)
    cp = datos.get('cp', 0.0)
    ndf = datos.get('ndf', 0.0)
    starch = datos.get('starch', 0.0)
    
    # Materia Seca: rango óptimo 30-40%
    if ms > 0:
        if ms < 28 or ms > 45:
            confianza_base -= 8
            penalizaciones.append(f"MS fuera de rango óptimo (28-45%): {ms:.1f}% (-8%)")
        elif ms < 30 or ms > 40:
            confianza_base -= 3
            advertencias.append(f"MS en rango aceptable pero no óptimo: {ms:.1f}%")
    
    # Proteína Cruda: rango esperado 7-10%
    if cp > 0:
        if cp < 6 or cp > 12:
            confianza_base -= 7
            penalizaciones.append(f"CP fuera de rango esperado (6-12%): {cp:.1f}% (-7%)")
        elif cp < 7 or cp > 10:
            confianza_base -= 2
            advertencias.append(f"CP en rango aceptable: {cp:.1f}%")
    
    # Fibra NDF: rango esperado 35-50%
    if ndf > 0:
        if ndf < 30 or ndf > 55:
            confianza_base -= 7
            penalizaciones.append(f"NDF fuera de rango esperado (30-55%): {ndf:.1f}% (-7%)")
        elif ndf < 35 or ndf > 50:
            confianza_base -= 2
            advertencias.append(f"NDF en rango aceptable: {ndf:.1f}%")
    
    # Almidón: rango esperado 25-35%
    if starch > 0:
        if starch < 20 or starch > 40:
            confianza_base -= 7
            penalizaciones.append(f"Almidón fuera de rango esperado (20-40%): {starch:.1f}% (-7%)")
        elif starch < 25 or starch > 35:
            confianza_base -= 2
            advertencias.append(f"Almidón en rango aceptable: {starch:.1f}%")
    
    # Verificar uso de valores por defecto (fallbacks)
    fallbacks_usados = []
    if datos.get('ndfd', 0.0) == 58.0:
        fallbacks_usados.append('NDFD')
    if datos.get('undf240', 0.0) == 15.0:
        fallbacks_usados.append('uNDF240')
    if datos.get('starch_d', 0.0) == 75.0:
        fallbacks_usados.append('Digestibilidad de almidón')
    
    if fallbacks_usados:
        penalizacion = len(fallbacks_usados) * 5
        confianza_base -= penalizacion
        penalizaciones.append(f"Valores por defecto utilizados: {', '.join(fallbacks_usados)} (-{penalizacion}%)")
    
    # Validar coherencia energética
    nel = resultados_intermedios.get('nel', 0.0)
    if nel > 0:
        if nel < 1.3:
            confianza_base -= 5
            advertencias.append(f"NEL baja ({nel:.2f} Mcal/kg), puede indicar forraje de baja calidad")
        elif nel > 1.8:
            confianza_base -= 5
            advertencias.append(f"NEL alta ({nel:.2f} Mcal/kg), verificar datos de entrada")
    
    # Asegurar que la confianza no sea negativa
    confianza_final = max(0.0, min(100.0, confianza_base))
    
    # Determinar nivel de confianza
    if confianza_final >= 85:
        nivel = "Excelente"
        color = "green"
    elif confianza_final >= 70:
        nivel = "Buena"
        color = "blue"
    elif confianza_final >= 50:
        nivel = "Moderada"
        color = "yellow"
    else:
        nivel = "Baja"
        color = "red"
    
    return {
        'factor_confianza': round(confianza_final, 1),
        'nivel_confianza': nivel,
        'color_indicador': color,
        'penalizaciones': penalizaciones,
        'advertencias': advertencias,
        'justificacion': _generar_justificacion(confianza_final, nivel, penalizaciones, advertencias)
    }

def _generar_justificacion(confianza: float, nivel: str, penalizaciones: list, advertencias: list) -> str:
    """Genera una justificación textual del factor de confianza."""
    justificacion = f"Confianza {nivel} ({confianza:.1f}%): "
    
    if confianza >= 85:
        justificacion += "Datos completos y dentro de rangos óptimos. Estimaciones altamente confiables basadas en el modelo Wisconsin MILK2024."
    elif confianza >= 70:
        justificacion += "Datos suficientes con valores en rangos aceptables. Estimaciones confiables con algunas consideraciones menores."
    elif confianza >= 50:
        justificacion += "Datos parciales o con valores fuera de rangos óptimos. Estimaciones orientativas, se recomienda validación adicional."
    else:
        justificacion += "Datos insuficientes o con valores significativamente fuera de rango. Estimaciones preliminares, requieren verificación."
    
    if penalizaciones:
        justificacion += f" Factores de ajuste: {'; '.join(penalizaciones[:3])}."
    
    return justificacion

def calcular_metricas_milk2024(datos: dict) -> dict:
    """
    Motor de cálculo oficial del modelo MILK2024 (Universidad de Wisconsin / NASEM 2021).
    Estima con precisión científica el valor energético y rendimiento lechero para ensilaje de maíz.
    Todos los inputs nutricionales deben estar en base a % de Materia Seca (DM).
    
    Incluye factor de confianza para evaluar la calidad de las estimaciones.
    """
    # 1. Extracción de Entradas con fallback seguro a 0.0
    ms: float = max(0.0, float(datos.get('ms', 0.0)))
    cp: float = max(0.0, float(datos.get('cp', 0.0)))
    ee: float = max(0.0, float(datos.get('ee', 0.0)))
    ash: float = max(0.0, float(datos.get('ash', 0.0)))
    ndf: float = max(0.0, float(datos.get('ndf', 0.0)))
    ndfd: float = max(0.0, float(datos.get('ndfd', 0.0)))
    undf240: float = max(0.0, float(datos.get('undf240', 0.0)))
    starch: float = max(0.0, float(datos.get('starch', 0.0)))
    starch_d: float = max(0.0, float(datos.get('starch_d', 0.0)))
    yield_dm: float = max(0.0, float(datos.get('yield_dm', 0.0))) # Toneladas MS / Hectárea

    # 2. Ecuaciones Oficiales de Fracciones Nutricionales Digestibles

    # Ácidos Grasos (FA) - Ecuación heredada de MILK2006 optimizada por NASEM 2021
    fa: float = max(0.0, ee - 1.0)
    d_fa: float = fa * 0.73 # Digestibilidad estandarizada del 73%

    # Materia Orgánica Residual (ROM) - Reemplaza al carbohidrato no fibroso (NFC) de MILK2006
    rom: float = max(0.0, 100.0 - (ash + ndf + starch + fa + cp))
    d_rom: float = rom * 0.91 # Digestibilidad estandarizada del 91% (Tebbe et al., 2017)

    # Proteína Cruda Digestible (dCP) - Coeficiente NASEM para ensilajes
    d_cp: float = cp * 0.70

    # Almidón Digestible (dStarch) - Basado en la desaparición enzimática ruminal a las 7h
    d_starch: float = starch * (starch_d / 100.0)

    # Fibra Digestible (dNDF) - Corrección del modelo mecanicista de dos piscinas (Rumen + Hindgut 10%)
    d_ndf_rumen: float = ndf * (ndfd / 100.0)
    remanente_fibra_digestible: float = max(0.0, ndf - d_ndf_rumen - undf240)
    d_ndf: float = d_ndf_rumen + (remanente_fibra_digestible * 0.10)

    # 3. Balance Energético NASEM 2021 / MILK2024

    # Nutrientes Digestibles Totales (% TDN) - Factor multiplicador de 2.25 para la densidad grasa
    tdn: float = d_cp + d_rom + (d_fa * 2.25) + d_starch + d_ndf

    # Energía Digestible (DE Mcal/kg)
    de: float = (tdn / 100.0) * 4.409

    # Energía Neta de Lactancia (NEL Mcal/kg)
    nel: float = max(0.0, (0.703 * de) - 0.19)

    # 4. Proyecciones Biológicas del Modelo Predictivo de Wisconsin

    # Leche por Tonelada de Materia Seca (kg de leche / Ton DM)
    leche_ton: float = (nel * 311.4) + 120.0

    # Leche por Hectárea (kg de leche / ha)
    leche_ha: float = leche_ton * yield_dm

    # Preparar resultados intermedios para el cálculo de confianza
    resultados_intermedios = {
        'fa': fa,
        'rom': rom,
        'd_cp': d_cp,
        'd_rom': d_rom,
        'd_fa': d_fa,
        'd_starch': d_starch,
        'd_ndf': d_ndf,
        'tdn': tdn,
        'de': de,
        'nel': nel,
        'leche_ton': leche_ton,
        'leche_ha': leche_ha
    }
    
    # Calcular factor de confianza
    confianza_info = calcular_factor_confianza(datos, resultados_intermedios)

    return {
        'fa': round(fa, 3),
        'rom': round(rom, 3),
        'd_cp': round(d_cp, 3),
        'd_rom': round(d_rom, 3),
        'd_fa': round(d_fa, 3),
        'd_starch': round(d_starch, 3),
        'd_ndf': round(d_ndf, 3),
        'tdn': round(tdn, 2),
        'de': round(de, 3),
        'nel': round(nel, 3),
        'leche_ton': round(leche_ton, 2),
        'leche_ha': round(leche_ha, 2),
        'confianza': confianza_info
    }