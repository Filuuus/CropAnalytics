import math


def calcular_factor_confianza(datos: dict) -> dict:
    """
    Calcula el factor de confianza de las estimaciones basado en:
    1. Completitud de datos de entrada (y uso de valores por defecto)
    2. Validez de rangos esperados para ensilaje de maíz
    
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

# Valores estándar de Wisconsin para lo que el laboratorio no mide (o viene vacío).
# ndfd, undf240, starch y starch_d nunca vienen en nuestros datos de laboratorio.
FALLBACKS_MILK2024 = {
    'ms': 35.0,
    'cp': 8.5,
    'ee': 3.2,
    'ash': 4.0,
    'ndf': 42.0,
    'ndfd': 58.0,
    'undf240': 15.0,
    'starch': 30.0,
    'starch_d': 75.0,
}


def datos_milk2024(ms, pc, gc, cen, fdn, cnf, yield_dm) -> dict:
    """
    Única forma de armar la entrada de MILK2024 a partir de columnas de
    ResultadoLaboratorio (% de MS). Valores None o 0 se reemplazan por FALLBACKS_MILK2024.

    El almidón no se mide: se usa el estándar de 30 %, pero nunca mayor que los
    CNF de la muestra (el almidón es parte de los carbohidratos no fibrosos).
    """
    medidos = {'ms': ms, 'cp': pc, 'ee': gc, 'ash': cen, 'ndf': fdn}
    datos = {k: medidos.get(k) or v for k, v in FALLBACKS_MILK2024.items()}
    if cnf:
        datos['starch'] = min(datos['starch'], cnf)
    datos['yield_dm'] = yield_dm
    return datos


# Dieta basal fija de la hoja MILK2024_Metric (filas 11-34). Son entradas de la hoja,
# no de cada muestra; si se cambia la dieta basal hay que volver a copiarlas.
_BASAL_NDF = 26.302827108433732      # F22
_BASAL_NDFD = 44.72756746987951      # G22
_BASAL_CP = 20.796848192771083       # J22
_BASAL_RDP = 12.341358837349397      # L22
_BASAL_DRUP = 6.740797047168674      # M22
_BASAL_FA = 5.068452590361446        # U17
_BASAL_DE_CORREGIDA = 2.4670242929741555  # U32 (DE basal × 70 % de inclusión)
_INCLUSION_CS = 0.30                 # AA10: ensilaje = 30 % de la MS de la dieta
_DIETA_ADF = 19.0                    # AU10
_PRODUCCION_LECHE = 52.0             # AU13 (kg/d)
_NEL_MANTENIMIENTO = 14.33           # AN11 (Mcal/d)
_NEL_GANANCIA_PESO = 2.8             # AN14 (Mcal/d)
_NEL_POR_KG_LECHE = 0.74             # AR20 (Mcal/kg)


def calcular_metricas_milk2024(datos: dict) -> dict:
    """
    MILK2024 (Universidad de Wisconsin), copia celda por celda de la hoja
    MILK2024_Metric (fila 38) con NDFD a 30 h y valores ya corregidos por ceniza.
    Entradas en % de MS; yield_dm en t MS/ha (= Mg/ha). Validado contra las 89
    muestras de ejemplo de la hoja en api/tests.py.
    """
    starch = float(datos['starch'])      # D
    starch_d = float(datos['starch_d'])  # E (7 h, % del almidón)
    ee = float(datos['ee'])              # F
    cp = float(datos['cp'])              # G
    ndf = float(datos['ndf'])            # H (NDFom)
    ndfd = float(datos['ndfd'])          # I (30 h, % NDFom)
    undf240 = float(datos['undf240'])    # J (% MS)
    ash = float(datos['ash'])            # K
    yield_dm = max(0.0, float(datos.get('yield_dm') or 0.0))  # C

    # Almidón: tasa de degradación desde starchD 7 h y digestibilidad total (Ferraretto 2013)
    starch_kd = 100 * ((math.log(100 - starch_d) - 4.6052) / -6)        # L
    tt_starch_d = 82.224 + 0.185 * (100 * (starch_kd / (starch_kd + 12)))  # M

    # FDN: modelo de dos pozas con uNDF240 como fracción indigestible (+10 % en intestino grueso)
    undf_pct_ndf = undf240 / (ndf / 100)                                   # N
    if ndfd + undf_pct_ndf >= 100:                                         # O
        undf_pct_ndf = 99.9 - ndfd
    ndf_kd = 100 * ((math.log((100 - undf_pct_ndf) - ndfd) - 4.6052) / -27)  # P
    tt_ndfd = (100 - undf_pct_ndf) * (1.1 * (ndf_kd / (ndf_kd + 3.36)))    # Q

    rdp = cp * 0.77                                                        # S
    drup = (cp * 0.33) * 0.7                                               # T
    fa = ee - 1                                                            # U
    rom = 100 - ash - starch - ndf - fa - cp                               # V

    # Consumo de MS (NASEM 2021, efectos de la ración); FDN y NDFD de la dieta
    ndf_dieta = _BASAL_NDF * 0.7 + ndf * 0.3
    ndfd_dieta = _BASAL_NDFD * 0.7 + ndfd * 0.3
    dmi = (12 - 0.107 * ndf_dieta + 8.17 * (_DIETA_ADF / ndf_dieta)
           + 0.0253 * ndfd_dieta
           - 0.328 * ((_DIETA_ADF / ndf_dieta) - 0.602) * (ndfd_dieta - 48.3)
           + 0.225 * _PRODUCCION_LECHE
           + 0.0039 * (ndfd_dieta - 48.3) * (_PRODUCCION_LECHE - 33.1))      # AT

    cp_consumo = ((cp * 0.3 + _BASAL_CP * 0.7) / 100) * dmi                # W
    rdp_consumo = ((rdp * 0.3 + _BASAL_RDP * 0.7) / 100) * dmi             # X
    drup_consumo = ((drup * 0.3 + _BASAL_DRUP * 0.7) / 100) * dmi          # Y

    # Energía digestible del ensilaje (calores de combustión NASEM 2021)
    d_ndf = ndf * (tt_ndfd / 100)
    d_starch = starch * (tt_starch_d / 100)
    d_fa = fa * 0.73
    d_cp = rdp + drup
    d_rom = rom * 0.91
    de_cs = 0.042 * d_ndf + 0.0423 * d_starch + 0.094 * d_fa + 0.0565 * d_cp + 0.04 * d_rom  # Z
    de_cs_corregida = de_cs * _INCLUSION_CS                                # AA
    de_dieta = de_cs_corregida + _BASAL_DE_CORREGIDA                       # AB

    # Pérdidas endógenas fecales, urinarias y de metano -> ME -> NEL (NASEM 2021)
    fmcp = (300 * 0.2) / dmi                                               # AC
    mfcp = 11.62 + 0.134 * ndf_dieta                                       # AD
    de_neta = de_dieta - 0.00565 * mfcp - 0.00565 * fmcp - 0.004 * 34.3   # AE
    adcp = ((rdp_consumo + drup_consumo) - (mfcp * dmi / 1000 + fmcp * dmi / 1000)) / cp_consumo  # AH
    un = (((cp_consumo * adcp) - 1.65) * 1000) / 6.25                      # AI
    energia_orina = (0.0146 * un) / dmi                                    # AJ
    energia_gas = (0.294 * dmi - 0.347 * (fa * 0.3 + _BASAL_FA * 0.7) + 0.0409 * ndf_dieta) / dmi  # AK
    me = de_neta - energia_gas - energia_orina                             # AL
    nel_dieta = 0.66 * me                                                  # AM
    nel_leche = nel_dieta * dmi - _NEL_MANTENIMIENTO - _NEL_GANANCIA_PESO  # AN

    # Parte de la NEL para leche que aporta el ensilaje
    nel_cs = nel_leche * (de_cs_corregida / de_dieta)                      # AP (Mcal/d)
    leche_cs = nel_cs / _NEL_POR_KG_LECHE                                  # AR (kg/d)
    dmi_cs = dmi * _INCLUSION_CS                                           # AV
    leche_ton = leche_cs / dmi_cs * 1000                                   # AW (kg leche / t MS)
    leche_ha = yield_dm * leche_ton                                        # AX
    nel = nel_cs / dmi_cs  # Mcal NEL por kg de MS de ensilaje (la hoja no lo reporta así)

    confianza_info = calcular_factor_confianza(datos)

    return {
        'fa': round(fa, 3),
        'rom': round(rom, 3),
        'd_cp': round(d_cp, 3),
        'd_rom': round(d_rom, 3),
        'd_fa': round(d_fa, 3),
        'd_starch': round(d_starch, 3),
        'd_ndf': round(d_ndf, 3),
        'de': round(de_cs, 3),
        'nel': round(nel, 3),
        'dmi': round(dmi, 2),
        'leche_ton': round(leche_ton, 2),
        'leche_ha': round(leche_ha, 2),
        'confianza': confianza_info
    }

def calcular_valor_ensilaje(datos: dict, resultados_milk: dict, precios: dict = None) -> dict:
    """
    Calcula el valor económico del ensilaje para diferentes escenarios de producción:
    1. Venta de ensilaje (precio por tonelada de materia seca)
    2. Uso propio para producción lechera (valor basado en leche producida)
    3. Compra de ensilaje para alimentación (costo de adquisición)
    
    Args:
        datos: Datos nutricionales y de rendimiento
        resultados_milk: Resultados del cálculo MILK2024
        precios: Diccionario con precios de mercado (opcional)
    
    Returns:
        Diccionario con análisis económico por escenario
    """
    # Precios por defecto (MXN)
    if precios is None:
        precios = {}
    
    precio_ensilaje_ton_ms = precios.get('ensilaje_ton_ms', 2800.0)  # MXN por tonelada MS
    precio_leche_litro = precios.get('leche_litro', 10.50)  # MXN por litro
    costo_produccion_ensilaje = precios.get('costo_produccion', 1800.0)  # MXN/ton MS
    costo_transporte_ton = precios.get('transporte', 150.0)  # MXN por tonelada
    
    yield_dm = datos.get('yield_dm', 0.0)  # Toneladas MS por hectárea
    leche_ha = resultados_milk.get('leche_ha', 0.0)  # kg leche por hectárea
    leche_ton = resultados_milk.get('leche_ton', 0.0)  # kg leche por tonelada MS
    nel = resultados_milk.get('nel', 0.0)  # Mcal/kg
    
    # ESCENARIO 1: Productor que VENDE ensilaje
    ingreso_venta_bruto = yield_dm * precio_ensilaje_ton_ms
    costo_produccion_total = yield_dm * costo_produccion_ensilaje
    utilidad_venta = ingreso_venta_bruto - costo_produccion_total
    margen_venta = (utilidad_venta / ingreso_venta_bruto * 100) if ingreso_venta_bruto > 0 else 0
    
    escenario_venta = {
        'descripcion': 'Productor que vende ensilaje',
        'rendimiento_ms_ha': round(yield_dm, 2),
        'precio_venta_ton_ms': precio_ensilaje_ton_ms,
        'ingreso_bruto_ha': round(ingreso_venta_bruto, 2),
        'costo_produccion_ha': round(costo_produccion_total, 2),
        'utilidad_neta_ha': round(utilidad_venta, 2),
        'margen_utilidad': round(margen_venta, 2),
        'roi': round((utilidad_venta / costo_produccion_total * 100) if costo_produccion_total > 0 else 0, 2)
    }
    
    # ESCENARIO 2: Productor que USA ensilaje propio (producción lechera)
    ingreso_leche = leche_ha * precio_leche_litro
    costo_ensilaje_propio = costo_produccion_total
    # Costos adicionales de producción lechera (alimentación complementaria, manejo, etc.)
    costo_adicional_lecheria = leche_ha * 3.5  # ~3.5 MXN por litro producido
    costo_total_lecheria = costo_ensilaje_propio + costo_adicional_lecheria
    utilidad_lecheria = ingreso_leche - costo_total_lecheria
    margen_lecheria = (utilidad_lecheria / ingreso_leche * 100) if ingreso_leche > 0 else 0
    
    # Valor implícito del ensilaje basado en la leche que produce
    valor_implicito_ensilaje = (leche_ton * precio_leche_litro) / 1000  # Por tonelada MS
    
    escenario_uso_propio = {
        'descripcion': 'Productor que usa ensilaje para sus vacas',
        'rendimiento_ms_ha': round(yield_dm, 2),
        'produccion_leche_ha': round(leche_ha, 2),
        'produccion_leche_ton_ms': round(leche_ton, 2),
        'precio_leche_litro': precio_leche_litro,
        'ingreso_leche_ha': round(ingreso_leche, 2),
        'costo_ensilaje_ha': round(costo_ensilaje_propio, 2),
        'costo_adicional_lecheria_ha': round(costo_adicional_lecheria, 2),
        'costo_total_ha': round(costo_total_lecheria, 2),
        'utilidad_neta_ha': round(utilidad_lecheria, 2),
        'margen_utilidad': round(margen_lecheria, 2),
        'valor_implicito_ensilaje_ton': round(valor_implicito_ensilaje, 2),
        'roi': round((utilidad_lecheria / costo_total_lecheria * 100) if costo_total_lecheria > 0 else 0, 2)
    }
    
    # ESCENARIO 3: Productor que COMPRA ensilaje
    costo_compra_ensilaje = yield_dm * (precio_ensilaje_ton_ms + costo_transporte_ton)
    ingreso_leche_comprador = leche_ha * precio_leche_litro
    costo_adicional_comprador = leche_ha * 3.5
    costo_total_comprador = costo_compra_ensilaje + costo_adicional_comprador
    utilidad_comprador = ingreso_leche_comprador - costo_total_comprador
    margen_comprador = (utilidad_comprador / ingreso_leche_comprador * 100) if ingreso_leche_comprador > 0 else 0
    
    # Precio máximo que debería pagar por el ensilaje para mantener rentabilidad
    margen_minimo_deseado = 0.20  # 20%
    ingreso_objetivo = ingreso_leche_comprador * (1 - margen_minimo_deseado)
    precio_maximo_ensilaje = (ingreso_objetivo - costo_adicional_comprador) / yield_dm if yield_dm > 0 else 0
    
    escenario_compra = {
        'descripcion': 'Productor que compra ensilaje',
        'necesidad_ms_ha': round(yield_dm, 2),
        'precio_compra_ton_ms': precio_ensilaje_ton_ms,
        'costo_transporte_ton': costo_transporte_ton,
        'costo_ensilaje_ha': round(costo_compra_ensilaje, 2),
        'produccion_leche_ha': round(leche_ha, 2),
        'ingreso_leche_ha': round(ingreso_leche_comprador, 2),
        'costo_adicional_lecheria_ha': round(costo_adicional_comprador, 2),
        'costo_total_ha': round(costo_total_comprador, 2),
        'utilidad_neta_ha': round(utilidad_comprador, 2),
        'margen_utilidad': round(margen_comprador, 2),
        'precio_maximo_recomendado_ton': round(precio_maximo_ensilaje, 2),
        'roi': round((utilidad_comprador / costo_total_comprador * 100) if costo_total_comprador > 0 else 0, 2)
    }
    
    # ANÁLISIS COMPARATIVO
    mejor_escenario = max(
        [('venta', escenario_venta['utilidad_neta_ha']),
         ('uso_propio', escenario_uso_propio['utilidad_neta_ha']),
         ('compra', escenario_compra['utilidad_neta_ha'])],
        key=lambda x: x[1]
    )
    
    recomendacion = {
        'mejor_opcion': mejor_escenario[0],
        'utilidad_maxima_ha': round(mejor_escenario[1], 2),
        'diferencia_vs_venta': round(escenario_uso_propio['utilidad_neta_ha'] - escenario_venta['utilidad_neta_ha'], 2),
        'factor_decision': 'produccion_lechera' if mejor_escenario[0] == 'uso_propio' else 'venta_directa',
        'justificacion': _generar_recomendacion_ensilaje(escenario_venta, escenario_uso_propio, escenario_compra, mejor_escenario[0])
    }
    
    return {
        'escenario_venta': escenario_venta,
        'escenario_uso_propio': escenario_uso_propio,
        'escenario_compra': escenario_compra,
        'recomendacion': recomendacion,
        'parametros_mercado': {
            'precio_ensilaje_ton_ms': precio_ensilaje_ton_ms,
            'precio_leche_litro': precio_leche_litro,
            'costo_produccion_ton_ms': costo_produccion_ensilaje,
            'costo_transporte_ton': costo_transporte_ton
        }
    }

def _generar_recomendacion_ensilaje(venta: dict, uso_propio: dict, compra: dict, mejor: str) -> str:
    """Genera recomendación textual para el productor."""
    if mejor == 'uso_propio':
        diferencia = uso_propio['utilidad_neta_ha'] - venta['utilidad_neta_ha']
        return (f"La producción lechera propia genera ${diferencia:,.2f} MXN más por hectárea "
                f"que vender el ensilaje. Con un ROI de {uso_propio['roi']:.1f}%, "
                f"es más rentable usar el ensilaje para alimentar vacas lecheras.")
    elif mejor == 'venta':
        return (f"Vender el ensilaje es más rentable con un margen de {venta['margen_utilidad']:.1f}%. "
                f"Genera ${venta['utilidad_neta_ha']:,.2f} MXN por hectárea sin los costos "
                f"adicionales de la producción lechera.")
    else:
        return (f"Para productores sin tierra, comprar ensilaje a ${compra['precio_compra_ton_ms']:,.2f} MXN/ton "
                f"y producir leche genera ${compra['utilidad_neta_ha']:,.2f} MXN/ha equivalente. "
                f"Precio máximo recomendado: ${compra['precio_maximo_recomendado_ton']:,.2f} MXN/ton.")