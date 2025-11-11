# /OLIVIA_WEB/actualizador_semanal.py
"""
Script ETL: Actualiza 'ventas_semanales_con_temporada.csv'
Replicando la lógica de '1b_exploracion_olivia_final.py'.
Ejecutar: python actualizador_semanal.py
"""
import pandas as pd
import numpy as np
from datetime import datetime

# --- Configuración de Rutas ---
INPUT_PATH = 'models/ventasOli2025.csv'
OUTPUT_PATH = 'models/ventas_semanales_con_temporada.csv'

# --- Configuración de ETL (Basado en 1b_exploracion_olivia_final.py) ---
VENTANA_MEDIA_MOVIL = 4
PERCENTIL_TEMPORADA = 0.85 # (Equivalente a 85)

def extraer_ventas_diarias(ruta_input):
    """Carga y limpia las ventas diarias desde el CSV nativo."""
    print(f"📥 Cargando ventas diarias desde: {ruta_input}...")
    try:
        df = pd.read_csv(
            ruta_input, 
            sep=';', 
            encoding='utf-8',
            parse_dates=['Fecha'], # Convertir 'Fecha' a datetime al cargar
            dtype={'CodigoProducto': str, 'CantidadVendidaTotal': float}
        )
        
        # Asegurar que los nombres de columnas sean consistentes
        df.rename(columns={
            'CodigoProducto': 'CodigoProducto',
            'Fecha': 'Fecha',
            'CantidadVendidaTotal': 'Ventas_Diarias'
        }, inplace=True, errors='ignore')
        
        # Filtrar solo columnas necesarias
        df = df[['Fecha', 'CodigoProducto', 'Ventas_Diarias']]
        
        # Eliminar ventas en Domingo (como en COLAB 0)
        df = df[df['Fecha'].dt.dayofweek != 6].copy()
        
        print(f"✅ Cargadas {len(df)} filas de ventas diarias (Lunes-Sábado).")
        return df
        
    except Exception as e:
        print(f"❌ Error al cargar {ruta_input}: {e}")
        return None

def transformar_a_semanal(df):
    """
    Agrega ventas diarias a semanales y crea la feature 'es_temporada_alta'
    replicando la lógica exacta de COLAB 1B.
    """
    if df is None or df.empty:
        return None
        
    print("🔄 Transformando a granularidad semanal (agrupando por Sábado)...")
    
    # Agrupar por semana (resample). 'W-SAT' agrupa por semanas que terminan el Sábado.
    df_semanal = (
        df.groupby('CodigoProducto')
        .resample('W-SAT', on='Fecha')['Ventas_Diarias']
        .sum()
        .reset_index()
    )
    df_semanal.rename(columns={'Ventas_Diarias': 'Ventas_Semanales'}, inplace=True)

    # Crear fechas de inicio y fin de semana
    df_semanal['Fecha_Fin_Semana'] = df_semanal['Fecha']
    df_semanal['Fecha_Inicio_Semana'] = df_semanal['Fecha'] - pd.to_timedelta('6 days')
    
    # --- Lógica de Temporada Alta (Réplica de COLAB 1B) ---
    print(f" Creando feature 'es_temporada_alta' (MA{VENTANA_MEDIA_MOVIL} y P{int(PERCENTIL_TEMPORADA*100)})...")
    
    df_semanal = df_semanal.sort_values(by=['CodigoProducto', 'Fecha_Fin_Semana'])
    
    # 1. Media Móvil
    df_semanal['tendencia_ma'] = df_semanal.groupby('CodigoProducto')['Ventas_Semanales'] \
                                     .transform(lambda x: x.rolling(window=VENTANA_MEDIA_MOVIL, min_periods=1).mean())

    # 2. Umbral del Percentil (por producto)
    umbral_p85 = df_semanal.groupby('CodigoProducto')['tendencia_ma'] \
                            .transform(lambda x: x.quantile(PERCENTIL_TEMPORADA))

    # 3. Feature binario 'es_temporada_alta'
    df_semanal['es_temporada_alta'] = (df_semanal['tendencia_ma'] > umbral_p85).astype(int)

    # --- Limpieza Final ---
    columnas_finales = [
        'CodigoProducto',
        'Fecha_Inicio_Semana',
        'Fecha_Fin_Semana',
        'Ventas_Semanales',
        'es_temporada_alta'
    ]
    
    df_final = df_semanal[columnas_finales].copy()
    
    # Convertir fechas a string en formato ISO para guardado consistente
    df_final['Fecha_Inicio_Semana'] = df_final['Fecha_Inicio_Semana'].dt.strftime('%Y-%m-%d')
    df_final['Fecha_Fin_Semana'] = df_final['Fecha_Fin_Semana'].dt.strftime('%Y-%m-%d')

    print(f"✅ Transformación completa: {len(df_final)} registros semanales.")
    return df_final

def cargar_csv(df, ruta_salida):
    """Guarda el DataFrame como CSV."""
    if df is None:
        print("❌ No hay datos para guardar.")
        return
        
    try:
        df.to_csv(ruta_salida, sep=';', index=False, encoding='utf-8')
        print(f"\n🎉 ¡ÉXITO! Archivo actualizado guardado en:")
        print(f"   {ruta_salida}")
        print(f"   (Rangos: {df['Fecha_Fin_Semana'].min()} a {df['Fecha_Fin_Semana'].max()})")
    except Exception as e:
        print(f"❌ Error al guardar el CSV: {e}")

# --- Ejecución del Pipeline ---
if __name__ == "__main__":
    print(f"--- Iniciando Actualizador Semanal de OLIVIA ({datetime.now()}) ---")
    
    datos_diarios = extraer_ventas_diarias(INPUT_PATH)
    datos_semanales = transformar_a_semanal(datos_diarios)
    cargar_csv(datos_semanales, OUTPUT_PATH)
        
    print("--- Proceso de actualización finalizado. ---")