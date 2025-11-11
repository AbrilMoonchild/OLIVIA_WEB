# /OLIVIA_WEB/olivia_app/blueprints/predict.py
from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
import tensorflow as tf
import pickle
import json
import os

predict_bp = Blueprint('predict', __name__)

# --- Rutas Base (Relativas a la carpeta /models) ---
BASE_PATH = 'models'
CATALOGO_PATH = os.path.join(BASE_PATH, 'catalogoOlivia.csv')
VENTAS_PATH = os.path.join(BASE_PATH, 'ventas_semanales_con_temporada.csv')
LOG_FASE1_PATH = os.path.join(BASE_PATH, 'log_fase1_lstm.csv')
LOG_FASE2_PATH = os.path.join(BASE_PATH, 'log_fase2_estadisticos.csv')

# --- ❗️ SOLUCIÓN DE RENDIMIENTO ❗️ ---
# Cargar todos los archivos de IA en memoria RAM al iniciar el servidor
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
    # Si falta un archivo, creamos DataFrames vacíos para evitar que la app se caiga
    CATALOGO = pd.DataFrame(columns=['codigoProd', 'marcaPrd', 'esImportacion', 'descProd'])
    LOG_FASE1 = pd.DataFrame(columns=['status'])
    LOG_FASE2 = pd.DataFrame(columns=['metodo_usado', 'predicciones', 'intervalos'])
    VENTAS_SEMANALES = pd.DataFrame(columns=['CodigoProducto', 'Fecha_Fin_Semana', 'Ventas_Semanales', 'es_temporada_alta'])
# --- FIN SOLUCIÓN DE RENDIMIENTO ---


@predict_bp.route('/predict_interactive', methods=['POST'])
def predict_interactive():
    """
    API unificada de pronóstico.
    Soporta: Por Código, Por Lista, Por Marca, Por Origen, General
    """
    data = request.json
    tipo = data.get('tipo', 'codigo')
    temporalidad = data.get('temporalidad', 'mensual') # mensual (4s) o trimestral (12s)
    
    codigos = []
    
    try:
        # Extraer parámetros según tipo
        if tipo == 'codigo':
            codigos = [data.get('codigo')]
        elif tipo == 'lista':
            codigos = data.get('codigos', [])
        elif tipo == 'marca':
            marca = data.get('marca')
            codigos = CATALOGO[CATALOGO['marcaPrd'] == marca]['codigoProd'].tolist()
        elif tipo == 'origen':
            origen = int(data.get('origen', 0)) # 0=Local, 1=Importado
            codigos = CATALOGO[CATALOGO['esImportacion'] == origen]['codigoProd'].tolist()
        elif tipo == 'general':
            codigos = CATALOGO['codigoProd'].tolist()
        else:
            return jsonify({"error": "Tipo de consulta no válido"}), 400
        
        if not codigos or all(c is None for c in codigos):
             return jsonify({"error": "No se proporcionaron códigos de producto válidos"}), 400

        # Ejecutar pronóstico para cada código
        resultados_detalle = []
        pronostico_agregado = np.zeros(12 if temporalidad == 'trimestral' else 4)
        
        for codigo in codigos:
            if codigo is None: continue
            
            resultado = get_forecast(codigo, temporalidad)
            
            if resultado['status'] != 'sin_modelo':
                # Enriquecer con info del catálogo
                try:
                    info = CATALOGO[CATALOGO['codigoProd'] == codigo].iloc[0]
                    resultado['descripcion'] = info['descProd']
                    resultado['marca'] = info['marcaPrd']
                    resultado['origen'] = 'Importado' if info['esImportacion'] == 1 else 'Local'
                except:
                    resultado['descripcion'] = 'N/A'
                    resultado['marca'] = 'N/A'
                    resultado['origen'] = 'N/A'
                
                resultados_detalle.append(resultado)
                # Sumar al pronóstico agregado
                pronostico_agregado += np.array(resultado['predicciones'])
        
        return jsonify({
            "tipo_consulta": tipo,
            "temporalidad": temporalidad,
            "total_productos_solicitados": len(codigos),
            "total_productos_encontrados": len(resultados_detalle),
            "pronostico_agregado": [round(p) for p in pronostico_agregado],
            "resultados_detalle": resultados_detalle
        })

    except Exception as e:
        current_app.logger.error(f"Error en /predict_interactive: {e}")
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500


def get_forecast(codigo, temporalidad):
    """
    Lógica de Consulta Unificada V5.3
    (Lee desde los DataFrames en RAM, no desde el disco)
    """
    
    # Try Fase 1 (LSTM)
    try:
        if codigo in LOG_FASE1.index and LOG_FASE1.loc[codigo]['status'] == 'APROBADO':
            return forecast_lstm(codigo, temporalidad)
    except Exception as e:
        print(f"⚠️  Error Fase 1 (LSTM) para {codigo}: {e}")
    
    # Try Fase 2 (Estadístico)
    try:
        if codigo in LOG_FASE2.index:
            row = LOG_FASE2.loc[codigo]
            return forecast_estadistico(codigo, temporalidad, row)
    except Exception as e:
        print(f"⚠️  Error Fase 2 (Estadístico) para {codigo}: {e}")
    
    # Sin modelo
    return {
        "codigo": codigo,
        "status": "sin_modelo",
        "mensaje": "No hay modelo disponible para este producto"
    }

def forecast_lstm(codigo, temporalidad):
    """Pronóstico con modelo LSTM (Fase 1)"""
    try:
        # Cargar modelo
        modelo_path = os.path.join(BASE_PATH, 'modelos_lstm', f'{codigo}.keras')
        modelo = tf.keras.models.load_model(modelo_path, compile=False)
        
        # Cargar scaler
        scaler_path = os.path.join(BASE_PATH, 'scalers', f'{codigo}_scaler.pkl')
        with open(scaler_path, 'rb') as f:
            scaler_data = pickle.load(f)
            scaler = scaler_data['scaler']
            lookback = int(scaler_data['lookback'])
            features = scaler_data.get('features', ['Ventas_Semanales', 'es_temporada_alta']) # Fallback
        
        # Cargar residuos
        residuos_path = os.path.join(BASE_PATH, 'residuos_historicos', f'{codigo}_residuos.pkl')
        with open(residuos_path, 'rb') as f:
            residuos = pickle.load(f)
        
        # Cargar historial (desde RAM)
        ventas_producto = VENTAS_SEMANALES[VENTAS_SEMANALES['CodigoProducto'] == codigo]\
                            .sort_values('Fecha_Fin_Semana')\
                            .tail(lookback)
        
        if len(ventas_producto) < lookback:
            raise Exception(f"Historial insuficiente en CSV: {len(ventas_producto)}/{lookback}")
        
        # Preparar entrada
        X = ventas_producto[features].values
        X_scaled = scaler.transform(X)
        X_input = np.array([X_scaled]) # (1, lookback, n_features)
        
        # Pronóstico
        pasos_requeridos = 12 if temporalidad == 'trimestral' else 4
        horizonte_modelo = 4 # El modelo siempre predice 4 semanas
        predicciones_scaled = []
        
        for _ in range(int(np.ceil(pasos_requeridos / horizonte_modelo))):
            pred_batch = modelo.predict(X_input, verbose=0)[0] # (4,)
            predicciones_scaled.extend(pred_batch)
            
            # Recursivo para siguiente lote
            # Crear dummy input para las 4 nuevas predicciones
            dummy_features = np.zeros((horizonte_modelo, len(features)))
            dummy_features[:, 0] = pred_batch
            
            # (Asumimos que 'es_temporada_alta' y otros features son 0 para el futuro)
            
            # Añadir las nuevas predicciones al input y quitar las más viejas
            X_input_nuevas = np.concatenate([X_input[0, horizonte_modelo:, :], dummy_features])
            X_input = np.array([X_input_nuevas])

        predicciones_scaled = predicciones_scaled[:pasos_requeridos]

        # --- ❗️ SOLUCIÓN DE EXACTITUD (Desnormalización) ❗️ ---
        # Replicar la lógica de la celda interactiva del script de entrenamiento
        pred_dummy_array = np.zeros((len(predicciones_scaled), len(features)))
        pred_dummy_array[:, 0] = predicciones_scaled
        predicciones_reales = scaler.inverse_transform(pred_dummy_array)[:, 0]
        # --- FIN SOLUCIÓN DE EXACTITUD ---

        # Intervalos de confianza
        p10 = np.maximum(0, predicciones_reales + np.percentile(residuos, 10))
        p90 = np.maximum(0, predicciones_reales + np.percentile(residuos, 90))
        
        return {
            "codigo": codigo,
            "status": "fase1_lstm",
            "temporalidad": temporalidad,
            "predicciones": [round(float(p)) for p in predicciones_reales],
            "intervalos": {
                "P10": [round(float(p)) for p in p10],
                "P90": [round(float(p)) for p in p90]
            }
        }
        
    except Exception as e:
        return {
            "codigo": codigo,
            "status": "error_lstm",
            "mensaje": f"Error al procesar LSTM: {e}"
        }

def forecast_estadistico(codigo, temporalidad, row):
    """Pronóstico con modelo estadístico (Fase 2)"""
    try:
        metodo = row['metodo_usado']
        pasos = 12 if temporalidad == 'trimestral' else 4

        # Cargar el modelo desde el archivo .pkl
        modelo_path = os.path.join(BASE_PATH, 'modelos_estadisticos', f'{codigo}_{metodo}.pkl')
        with open(modelo_path, 'rb') as f:
            modelo_data = pickle.load(f)

        # Si es 'mensual', leemos los datos pre-calculados (más rápido)
        if temporalidad == 'mensual':
            predicciones = json.loads(row['predicciones'])
            intervalos = json.loads(row['intervalos'])
        
        # Si es 'trimestral', usamos el modelo cargado para predecir 12 pasos
        else: 
            modelo = modelo_data['modelo']
            
            if metodo == 'SARIMA':
                # pmdarima usa 'predict'
                predicciones = modelo.predict(n_periods=pasos)
            elif metodo == 'HOLT_WINTERS':
                # statsmodels usa 'forecast'
                predicciones = modelo.forecast(steps=pasos)
            elif metodo == 'EWMA':
                # EWMA es solo repetir el último valor
                ultimo_valor = modelo_data['modelo']['ultimo_valor_ewma']
                predicciones = [ultimo_valor] * pasos
            else: # EXP_SMOOTHING
                predicciones = modelo.forecast(steps=pasos)

            # Para trimestral, calculamos intervalos genéricos (no tenemos residuos)
            std_dev = np.std(predicciones) if np.std(predicciones) > 0.5 else np.mean(predicciones) * 0.2
            p10 = np.maximum(0, np.array(predicciones) - (1.28 * std_dev))
            p90 = np.maximum(0, np.array(predicciones) + (1.28 * std_dev))
            intervalos = {"P10": p10.tolist(), "P90": p90.tolist()}

        return {
            "codigo": codigo,
            "status": "fase2_estadistico",
            "metodo": metodo,
            "temporalidad": temporalidad,
            "predicciones": [round(float(p)) for p in predicciones[:pasos]],
            "intervalos": {
                "P10": [round(float(p)) for p in intervalos['P10'][:pasos]],
                "P90": [round(float(p)) for p in intervalos['P90'][:pasos]]
            }
        }
            
    except Exception as e:
        return {
            "codigo": codigo,
            "status": "error_estadistico",
            "mensaje": f"Error al procesar {metodo}: {e}"
        }