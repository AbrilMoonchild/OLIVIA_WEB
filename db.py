import pyodbc
from .config import Config

def obtener_conexion():
    """Establece conexión con SQL Server"""
    try:
        conexion = pyodbc.connect(
            f'DRIVER={{SQL Server}};'
            f'SERVER={Config.DB_SERVER};'
            f'DATABASE={Config.DB_NAME};'
            f'UID={Config.DB_USERNAME};'
            f'PWD={Config.DB_PASSWORD}'
        )
        return conexion
    except Exception as e:
        print(f"❌ Error al conectar con SQL Server: {e}")
        return None