from flask import Blueprint, request, jsonify, session
import bcrypt
from ..db import obtener_conexion

user_bp = Blueprint('user', __name__)

@user_bp.route('/verificar-password', methods=['POST'])
def verificar_password():
    if 'correo' not in session:
        return jsonify({"valida": False, "mensaje": "Usuario no autenticado"}), 401

    datos = request.json
    password_ingresada = datos.get("password")

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"valida": False, "mensaje": "Error en la conexión"}), 500

    cursor = conexion.cursor()
    cursor.execute("SELECT contraseña FROM Usuarios WHERE correo = ?", (session["correo"],))
    resultado = cursor.fetchone()
    conexion.close()

    if resultado and bcrypt.checkpw(password_ingresada.encode('utf-8'), resultado[0].encode('utf-8')):
        return jsonify({"valida": True})
    else:
        return jsonify({"valida": False, "mensaje": "Contraseña incorrecta"})

@user_bp.route('/actualizar-password', methods=['POST'])
def actualizar_password():
    if 'correo' not in session:
        return jsonify({"exito": False, "mensaje": "Usuario no autenticado"}), 401

    datos = request.json
    nueva_password = datos.get("nueva_password")

    if not nueva_password or len(nueva_password) < 7:
        return jsonify({"exito": False, "mensaje": "La contraseña debe tener al menos 7 caracteres"}), 400

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"exito": False, "mensaje": "Error en la conexión"}), 500

    try:
        password_hashed = bcrypt.hashpw(nueva_password.encode('utf-8'), bcrypt.gensalt())
        cursor = conexion.cursor()
        cursor.execute(
            "UPDATE Usuarios SET contraseña = ? WHERE correo = ?",
            (password_hashed.decode('utf-8'), session["correo"])
        )
        conexion.commit()
        conexion.close()
        return jsonify({"exito": True, "mensaje": "Contraseña actualizada correctamente"})
    except Exception as e:
        print(f"❌ Error al actualizar la contraseña: {e}")
        return jsonify({"exito": False, "mensaje": "Error al actualizar la contraseña"}), 500

@user_bp.route('/get_users', methods=['GET'])
def get_users():
    if 'correo' not in session:
        return jsonify({"mensaje": "Usuario no autenticado"}), 401

    correo_usuario_logueado = session['correo']

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

    cursor = conexion.cursor()
    cursor.execute("""
        SELECT id, correo, nombre, apellidos, rol, cargo
        FROM Usuarios
        WHERE correo != ? AND estado = 1
    """, (correo_usuario_logueado,))
    
    usuarios = cursor.fetchall()
    conexion.close()

    usuarios_json = []
    for usuario in usuarios:
        usuarios_json.append({
            "id": usuario[0],
            "correo": usuario[1],
            "nombre": usuario[2],
            "apellidos": usuario[3],
            "rol": usuario[4],
            "cargo": usuario[5]
        })

    return jsonify(usuarios_json)

@user_bp.route('/agregar_usuario', methods=['POST'])
def agregar_usuario():
    data = request.get_json()
    nombre = data.get('nombre')
    apellidos = data.get('apellidos')
    correo = data.get('correo')
    password = data.get('password')
    rol = data.get('rol')
    cargo = data.get('cargo')

    if not nombre or not apellidos or not correo or not password or not rol or not cargo:
        return jsonify({"success": False, "message": "Todos los campos son requeridos."}), 400

    password_hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"success": False, "message": "Error al conectar"}), 500

    try:
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Usuarios (nombre, apellidos, correo, contraseña, rol, cargo, estado)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (nombre, apellidos, correo, password_hashed.decode('utf-8'), rol, cargo))
        conexion.commit()
        return jsonify({"success": True, "message": "Usuario agregado exitosamente"}), 200
    except Exception as e:
        print(f"❌ Error al agregar el usuario: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    finally:
        conexion.close()

@user_bp.route('/get_user/<int:id>', methods=['GET'])
def get_user(id):
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"mensaje": "Error al conectar"}), 500

    cursor = conexion.cursor()
    cursor.execute("""
        SELECT nombre, apellidos, correo, rol, cargo
        FROM Usuarios WHERE id = ?
    """, (id,))
    
    usuario = cursor.fetchone()
    conexion.close()

    if usuario:
        return jsonify({
            "nombre": usuario[0],
            "apellidos": usuario[1],
            "correo": usuario[2],
            "rol": usuario[3],
            "cargo": usuario[4]
        })
    else:
        return jsonify({"mensaje": "Usuario no encontrado"}), 404

@user_bp.route('/editar_usuario/<int:id>', methods=['POST'])
def editar_usuario(id):
    data = request.get_json()
    nombre = data.get('nombre')
    apellidos = data.get('apellidos')
    correo = data.get('correo')
    rol = data.get('rol')
    cargo = data.get('cargo')

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE Usuarios
            SET nombre = ?, apellidos = ?, correo = ?, rol = ?, cargo = ?
            WHERE id = ?
        """, (nombre, apellidos, correo, rol, cargo, id))
        conexion.commit()
        conexion.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_bp.route('/desactivar_usuario/<int:id>', methods=['POST'])
def desactivar_usuario(id):
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"success": False, "message": "Error al conectar"}), 500

    try:
        cursor = conexion.cursor()
        cursor.execute("UPDATE Usuarios SET estado = 0 WHERE id = ?", (id,))
        conexion.commit()
        return jsonify({"success": True, "message": "Usuario desactivado"}), 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "message": "Error al desactivar"}), 500
    finally:
        conexion.close()

@user_bp.route('/change_password/<int:id>', methods=['POST'])
def change_password(id):
    nueva_contraseña = "SISPRO123"

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"success": False, "message": "Error al conectar"}), 500

    try:
        password_hashed = bcrypt.hashpw(nueva_contraseña.encode('utf-8'), bcrypt.gensalt())
        cursor = conexion.cursor()
        cursor.execute("UPDATE Usuarios SET contraseña = ? WHERE id = ?", (password_hashed.decode('utf-8'), id))
        conexion.commit()
        return jsonify({"success": True, "message": "Contraseña actualizada"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    finally:
        conexion.close()