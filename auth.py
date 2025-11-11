from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
import bcrypt
from ..db import obtener_conexion

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    return render_template('index.html')

@auth_bp.route('/login', methods=['POST'])
def login():
    datos = request.json
    correo = datos.get("correo")
    contraseña = datos.get("contraseña")

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

    cursor = conexion.cursor()
    cursor.execute(
        "SELECT nombre, apellidos, correo, rol, cargo, contraseña FROM Usuarios WHERE correo = ?", 
        (correo,)
    )
    usuario = cursor.fetchone()
    conexion.close()

    if usuario:
        hashed_pw = usuario[5]
        if bcrypt.checkpw(contraseña.encode('utf-8'), hashed_pw.encode('utf-8')):
            session["nombre"] = usuario[0]
            session["apellidos"] = usuario[1]
            session["correo"] = usuario[2]
            session["rol"] = usuario[3]
            session["cargo"] = usuario[4]
            return jsonify({"mensaje": "Login exitoso"})

    return jsonify({"mensaje": "Correo o contraseña incorrectos"}), 401

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.home'))

@auth_bp.route('/home')
def dashboard():
    if 'nombre' in session and 'apellidos' in session:
        return render_template(
            'home.html',
            usuario=session.get('nombre', ''),
            apellidos=session.get('apellidos', ''),
            correo=session.get('correo', ''),
            rol=session.get('rol', ''),
            cargo=session.get('cargo', '')
        )
    else:
        return redirect(url_for('auth.home'))