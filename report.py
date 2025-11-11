# /OLIVIA_WEB/olivia_app/blueprints/report.py
from flask import Blueprint, request, jsonify
import pandas as pd
import os

report_bp = Blueprint('report', __name__)

# --- Rutas Base ---
BASE_PATH = 'models'
REPORTE_PATH = os.path.join(BASE_PATH, 'reporte_global_4semanas.csv')
CATALOGO_PATH = os.path.join(BASE_PATH, 'catalogoOlivia.csv')
LOG_FASE1_PATH = os.path.join(BASE_PATH, 'log_fase1_lstm.csv')
LOG_FASE2_PATH = os.path.join(BASE_PATH, 'log_fase2_estadisticos.csv')

# --- ❗️ SOLUCIÓN DE RENDIMIENTO ❗️ ---
# Cargar archivos de reporte en memoria RAM al iniciar
try:
    print("Cargando 'reporte_global_4semanas.csv' en memoria...")
    REPORTE_GLOBAL = pd.read_csv(REPORTE_PATH, sep=';', encoding='utf-8')
    print("Cargando 'catalogoOlivia.csv' (para reportes) en memoria...")
    CATALOGO = pd.read_csv(CATALOGO_PATH, sep=';', encoding='utf-8')
    print("Cargando 'log_fase1_lstm.csv' (para reportes) en memoria...")
    LOG_FASE1 = pd.read_csv(LOG_FASE1_PATH, sep=';', encoding='utf-8')
    print("Cargando 'log_fase2_estadisticos.csv' (para reportes) en memoria...")
    LOG_FASE2 = pd.read_csv(LOG_FASE2_PATH, sep=';', encoding='utf-8')
    print("✅ Todos los archivos de REPORTE cargados en RAM.")
except Exception as e:
    print(f"⚠️  ADVERTENCIA: No se pudo cargar 'reporte_global_4semanas.csv'. "
          f"Las rutas de reporte fallarán hasta que se ejecute 'generador_reportes.py'. Error: {e}")
    REPORTE_GLOBAL = pd.DataFrame(columns=['CodigoProducto', 'descProd', 'marcaPrd', 'Origen', 'Pronostico_Suma_4sem', 'Clasificacion_ABC'])
    # (Los otros archivos ya fueron cargados por predict.py, pero es bueno tenerlos aquí por si acaso)
    if 'CATALOGO' not in globals():
        CATALOGO = pd.read_csv(CATALOGO_PATH, sep=';', encoding='utf-8')
        LOG_FASE1 = pd.read_csv(LOG_FASE1_PATH, sep=';', encoding='utf-8')
        LOG_FASE2 = pd.read_csv(LOG_FASE2_PATH, sep=';', encoding='utf-8')
# --- FIN SOLUCIÓN DE RENDIMIENTO ---


@report_bp.route('/get_reporte_agregado', methods=['POST'])
def get_reporte_agregado():
    """
    Lee el reporte pre-calculado y filtra según criterios
    """
    data = request.json
    tipo = data.get('tipo', 'general')  # general, marca, origen
    
    try:
        # Usar el DataFrame en memoria REPORTE_GLOBAL
        reporte_filtrado = REPORTE_GLOBAL.copy()
        
        if tipo == 'marca':
            marca = data.get('marca')
            reporte_filtrado = reporte_filtrado[reporte_filtrado['marcaPrd'] == marca]
        elif tipo == 'origen':
            origen = data.get('origen')  # 'Local' o 'Importado'
            reporte_filtrado = reporte_filtrado[reporte_filtrado['Origen'] == origen]
        
        # Convertir a JSON
        resultados = reporte_filtrado.to_dict(orient='records')
        
        # Calcular el total agregado del filtro
        pronostico_agregado = reporte_filtrado['Pronostico_Suma_4sem'].sum()
        
        return jsonify({
            "total_productos": len(resultados),
            "tipo_consulta": tipo,
            "pronostico_agregado_4sem": float(pronostico_agregado), # Convertir de numpy a float
            "resultados_detalle": resultados
        })
        
    except Exception as e:
        return jsonify({"error": f"Error al procesar reporte: {e}"}), 500

@report_bp.route('/get_dashboard_stats', methods=['GET'])
def get_dashboard_stats():
    """
    Estadísticas para el Dashboard de Desempeño
    (Lee desde los DataFrames en RAM)
    """
    try:
        # Cobertura de modelos
        total_productos = len(CATALOGO)
        con_fase1 = len(LOG_FASE1[LOG_FASE1['status'] == 'APROBADO'])
        con_fase2 = len(LOG_FASE2['CodigoProducto'].unique()) # Contar productos únicos
        sin_modelo = total_productos - con_fase1 - con_fase2
        
        # Top 10 productos (del reporte)
        top10 = REPORTE_GLOBAL.nlargest(10, 'Pronostico_Suma_4sem')\
                              [['CodigoProducto', 'descProd', 'Pronostico_Suma_4sem']]\
                              .to_dict(orient='records')
        
        # Ventas por marca
        ventas_marca = REPORTE_GLOBAL.groupby('marcaPrd')['Pronostico_Suma_4sem'].sum().nlargest(5).to_dict()
        
        # Ventas por origen
        ventas_origen = REPORTE_GLOBAL.groupby('Origen')['Pronostico_Suma_4sem'].sum().to_dict()
        
        return jsonify({
            "cobertura": {
                "total": total_productos,
                "fase1_lstm": con_fase1,
                "fase2_estadistico": con_fase2,
                "sin_modelo": sin_modelo
            },
            "top10_productos": top10,
            "ventas_por_marca": ventas_marca,
            "ventas_por_origen": ventas_origen
        })
        
    except Exception as e:
        return jsonify({"error": f"Error al generar estadísticas: {e}"}), 500