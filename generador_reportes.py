# /OLIVIA_WEB/generador_reportes.py
"""
Script: Genera reporte_global_4semanas.csv usando la Lógica Unificada.
Este script está optimizado para cargar los logs en RAM una sola vez.
Ejecutar: python generador_reportes.py
"""
import pandas as pd
import numpy as np
import tensorflow as tf
import pickle
import json
import os
import sys
import traceback
from datetime import datetime

# --- Rutas Base (Relativas a la carpeta /models) ---
BASE_PATH = 'models'
CATALOGO_PATH = os.path.join(BASE_PATH, 'catalogoOlivia.csv')
VENTAS_PATH = os.path.join(BASE_PATH, 'ventas_semanales_con_temporada.csv')
LOG_FASE1_PATH = os.path.join(BASE_PATH, 'log_fase1_lstm.csv')
LOG_FASE2_PATH = os.path.join(BASE_PATH, 'log_fase2_estadisticos.csv')
OUTPUT_PATH = os.path.join(BASE_PATH, 'reporte_global_4semanas.csv')


# --- ❗️ Lógica de IA (Optimizada para ejecución Offline) ❗️ ---
# Esta es una copia de la lógica de 'predict.py', pero adaptada
# para aceptar los DataFrames de log como argumentos.

def forecast_lstm_offline(codigo, temporalidad, scaler_data, residuos, ventas_producto):
    """Pronóstico con modelo LSTM (Versión Offline)"""
    try:
        modelo_path = os.path.join(BASE_PATH, 'modelos_lstm', f'{codigo}.keras')
        modelo = tf.keras.models.load_model(modelo_path, compile=False)
        
        scaler = scaler_data['scaler']
        lookback = int(scaler_data['lookback'])
        features = scaler_data.get('features', ['Ventas_Semanales', 'es_temporada_alta'])
        
        historial = ventas_producto.sort_values('Fecha_Fin_Semana').tail(lookback)
        
        if len(historial) < lookback:
            raise Exception(f"Historial insuficiente: {len(historial)}/{lookback}")
        
        X = historial[features].values
        X_scaled = scaler.transform(X)
        X_input = np.array([X_scaled])
        
        pasos_requeridos = 12 if temporalidad == 'trimestral' else 4
        horizonte_modelo = 4
        predicciones_scaled = []
        
        for _ in range(int(np.ceil(pasos_requeridos / horizonte_modelo))):
            pred_batch = modelo.predict(X_input, verbose=0)[0]
            predicciones_scaled.extend(pred_batch)
            
            dummy_features = np.zeros((horizonte_modelo, len(features)))
            dummy_features[:, 0] = pred_batch
            X_input_nuevas = np.concatenate([X_input[0, horizonte_modelo:, :], dummy_features])
            X_input = np.array([X_input_nuevas])

        predicciones_scaled = predicciones_scaled[:pasos_requeridos]
        
        pred_dummy_array = np.zeros((len(predicciones_scaled), len(features)))
        pred_dummy_array[:, 0] = predicciones_scaled
        predicciones_reales = scaler.inverse_transform(pred_dummy_array)[:, 0]

        return {"status": "fase1_lstm", "predicciones": predicciones_reales.tolist()}
        
    except Exception as e:
        return {"status": "error_lstm", "mensaje": str(e)}

def forecast_estadistico_offline(codigo, temporalidad, row):
    """Pronóstico con modelo estadístico (Versión Offline)"""
    try:
        metodo = row['metodo_usado']
        pasos = 12 if temporalidad == 'trimestral' else 4

        modelo_path = os.path.join(BASE_PATH, 'modelos_estadisticos', f'{codigo}_{metodo}.pkl')
        with open(modelo_path, 'rb') as f:
            modelo_data = pickle.load(f)

        if temporalidad == 'mensual':
            predicciones = json.loads(row['predicciones'])
        else: 
            modelo = modelo_data['modelo']
            if metodo == 'SARIMA':
                predicciones = modelo.predict(n_periods=pasos)
            elif metodo == 'HOLT_WINTERS':
                predicciones = modelo.forecast(steps=pasos)
            elif metodo == 'EWMA':
                ultimo_valor = modelo_data['modelo']['ultimo_valor_ewma']
                predicciones = [ultimo_valor] * pasos
            else: # EXP_SMOOTHING
                predicciones = modelo.forecast(steps=pasos)
        
        return {"status": "fase2_estadistico", "predicciones": [float(p) for p in predicciones[:pasos]]}
            
    except Exception as e:
        return {"status": "error_estadistico", "mensaje": str(e)}

def get_forecast_offline(codigo, temporalidad, log_fase1, log_fase2, ventas_semanales):
    """
    Lógica de Consulta Unificada (Versión Offline).
    Acepta DataFrames de Log/Ventas como argumentos para evitar lecturas de disco.
    """
    
    # Pre-cargar scalers/residuos es complejo, los cargamos bajo demanda.
    
    # Try Fase 1 (LSTM)
    try:
        if codigo in log_fase1.index and log_fase1.loc[codigo]['status'] == 'APROBADO':
            # Cargar scaler
            scaler_path = os.path.join(BASE_PATH, 'scalers', f'{codigo}_scaler.pkl')
            with open(scaler_path, 'rb') as f:
                scaler_data = pickle.load(f)
            
            # Cargar residuos
            residuos_path = os.path.join(BASE_PATH, 'residuos_historicos', f'{codigo}_residuos.pkl')
            with open(residuos_path, 'rb') as f:
                residuos = pickle.load(f)
            
            # Filtrar ventas del producto (desde RAM)
            ventas_producto = ventas_semanales[ventas_semanales['CodigoProducto'] == codigo]
            
            return forecast_lstm_offline(codigo, temporalidad, scaler_data, residuos, ventas_producto)
    except Exception as e:
        # print(f"⚠️  Fase 1 (LSTM) falló para {codigo}: {e}")
        pass # Intentar Fase 2
    
    # Try Fase 2 (Estadístico)
    try:
        if codigo in log_fase2.index:
            row = log_fase2.loc[codigo]
            return forecast_estadistico_offline(codigo, temporalidad, row)
    except Exception as e:
        # print(f"⚠️  Fase 2 (Estadístico) falló para {codigo}: {e}")
        pass # Marcar como sin modelo
    
    # Sin modelo
    return {"status": "sin_modelo", "predicciones": [0] * (12 if temporalidad == 'trimestral' else 4)}

# --- Función Principal del Generador de Reportes ---
def generar_reporte():
    print(f"--- Iniciando Generador de Reporte Global ({datetime.now()}) ---")
    
    # --- ❗️ SOLUCIÓN DE OPTIMIZACIÓN ❗️ ---
    # Cargar todos los archivos de IA en RAM una sola vez
    try:
        print("Cargando 'catalogoOlivia.csv' en memoria...")
        CATALOGO = pd.read_csv(CATALOGO_PATH, sep=';', encoding='utf-8')
        print("Cargando 'log_fase1_lstm.csv' en memoria...")
        LOG_FASE1 = pd.read_csv(LOG_FASE1_PATH, sep=';', encoding='utf-8').set_index('codigo')
        print("Cargando 'log_fase2_estadisticos.csv' en memoria...")
        LOG_FASE2 = pd.read_csv(LOG_FASE2_PATH, sep=';', encoding='utf-8').set_index('CodigoProducto')
        print("Cargando 'ventas_semanales_con_temporada.csv' en memoria...")
        VENTAS_SEMANALES = pd.read_csv(VENTAS_PATH, sep=';', encoding='utf-8')
        VENTAS_SEMANALES['Fecha_Fin_Semana'] = pd.to_datetime(VENTAS_SEMANALES['Fecha_Fin_Semana'])
        print("✅ Todos los archivos de IA cargados en RAM.")
    except Exception as e:
        print(f"❌ ERROR CRÍTICO AL CARGAR ARCHIVOS DE IA: {e}")
        return
    # --- FIN SOLUCIÓN DE OPTIMIZACIÓN ---

    print(f"📦 Procesando {len(CATALOGO)} productos del catálogo...")
    
    resultados = []
    
    for idx, row in CATALOGO.iterrows():
        codigo = row['codigoProd']
        
        # Obtener pronósticos (usando la versión offline)
        resultado_4sem = get_forecast_offline(codigo, 'mensual', LOG_FASE1, LOG_FASE2, VENTAS_SEMANALES)
        resultado_12sem = get_forecast_offline(codigo, 'trimestral', LOG_FASE1, LOG_FASE2, VENTAS_SEMANALES)
        
        # Sumar resultados
        suma_4sem = sum(resultado_4sem['predicciones'])
        suma_12sem = sum(resultado_12sem['predicciones'])
        
        resultados.append({
            'CodigoProducto': codigo,
            'descProd': row['descProd'],
            'marcaPrd': row['marcaPrd'],
            'Origen': 'Importado' if row['esImportacion'] == 1 else 'Local',
            'Pronostico_Suma_4sem': round(suma_4sem),
            'Pronostico_Suma_12sem_Exp': round(suma_12sem),
            'Status_IA': resultado_4sem['status'] # Guardar el status
        })
        
        if (idx + 1) % 500 == 0 or (idx + 1) == len(CATALOGO):
            print(f"⏳ Procesados {idx + 1}/{len(CATALOGO)} productos...")
            # Limpiar memoria de TensorFlow
            tf.keras.backend.clear_session()
    
    # Crear DataFrame
    df = pd.DataFrame(resultados)
    
    if df.empty:
        print("⚠️ No se generaron pronósticos. Verifica los modelos.")
        return
    
    # Clasificación ABC (Pareto)
    print("📊 Calculando Clasificación ABC (Pareto)...")
    df = df.sort_values('Pronostico_Suma_4sem', ascending=False).reset_index(drop=True)
    df['Porcentaje_Acumulado'] = df['Pronostico_Suma_4sem'].cumsum() / df['Pronostico_Suma_4sem'].sum()
    
    df['Clasificacion_ABC'] = 'C' # Asignar 'C' a todos por defecto
    df.loc[df['Porcentaje_Acumulado'] <= 0.80, 'Clasificacion_ABC'] = 'A'
    df.loc[(df['Porcentaje_Acumulado'] > 0.80) & (df['Porcentaje_Acumulado'] <= 0.95), 'Clasificacion_ABC'] = 'B'
    
    # Guardar
    df.to_csv(OUTPUT_PATH, sep=';', index=False, encoding='utf-8')
    
    print("\n" + "="*70)
    print(f"✅ Reporte global generado exitosamente: {OUTPUT_PATH}")
    print(f"📊 Total productos en reporte: {len(df)}")
    print(f"   Clase A (80%): {len(df[df['Clasificacion_ABC'] == 'A'])}")
    print(f"   Clase B (15%): {len(df[df['Clasificacion_ABC'] == 'B'])}")
    print(f"   Clase C (5%):  {len(df[df['Clasificacion_ABC'] == 'C'])}")
    print(f"💰 Pronóstico total (4 sem): {df['Pronostico_Suma_4sem'].sum():,.0f} unidades")
    print(f"--- Proceso de generación de reporte finalizado. ---")

if __name__ == '__main__':
    try:
        generar_reporte()
    except Exception as e:
        print(f"❌ Error fatal en generador_reportes: {e}")
        traceback.print_exc()