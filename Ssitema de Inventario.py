import csv
import io
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response

# Configurar Matplotlib para generación de imágenes
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_inventario'

DATABASE = 'inventario.db'

def obtener_conexion():
    conexion = sqlite3.connect(DATABASE)
    conexion.row_factory = sqlite3.Row
    return conexion

# --- INICIALIZACIÓN DE LA BASE DE DATOS ---
def inicializar_bd():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    # 1. Tabla Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            contrasena TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'empleado'
        )
    """)
    
    # 2. Tabla Productos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            precio REAL NOT NULL DEFAULT 0.0
        )
    """)
    
    # 3. Tabla Proveedores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            contacto TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    """)
    
    # 4. Tabla Movimientos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            usuario TEXT DEFAULT 'Sistema',
            FOREIGN KEY(producto_id) REFERENCES productos(id)
        )
    """)

    # Crear usuario administrador si no existe
    cursor.execute("SELECT * FROM usuarios WHERE usuario = ?", ('admin',))
    if not cursor.fetchone():
        clave_encriptada = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO usuarios (usuario, contrasena, rol) VALUES (?, ?, ?)",
            ('admin', clave_encriptada, 'administrador')
        )

    conexion.commit()
    conexion.close()

inicializar_bd()

# --- DECORADORES DE SEGURIDAD ---
def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            flash("Debes iniciar sesión para acceder.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def requerir_roles(*roles):
    def decorator(f):
        @wraps(f)  
        def decorated_function(*args, **kwargs):
            if session.get("rol") not in roles:
                flash("No tienes permisos suficientes.", "danger")
                return redirect(url_for("inicio"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form.get('usuario')
        clave_input = request.form.get('contrasena')
        
        if not usuario_input or not clave_input:
            flash("Por favor completa todos los campos.", "warning")
            return render_template('login.html')

        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario_input,))
        usuario_db = cursor.fetchone()
        conexion.close()
        
        if usuario_db and check_password_hash(usuario_db['contrasena'], clave_input):
            session['usuario'] = usuario_db['usuario']
            session['rol'] = usuario_db['rol']
            flash(f"¡Bienvenido, {usuario_db['usuario']}!", "success")
            return redirect(url_for('inicio'))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('login'))

# --- RUTAS PRINCIPALES DEL INVENTARIO ---
@app.route('/')
@login_requerido
def inicio():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    
    cursor.execute("""
        SELECT m.id, p.nombre as producto, m.tipo, m.cantidad, m.fecha, m.usuario
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        ORDER BY m.id DESC LIMIT 5
    """)
    movimientos_recientes = cursor.fetchall()
    conexion.close()
    
    # Métricas principales
    total_productos = len(productos)
    unidades_totales = sum(p['cantidad'] for p in productos)
    valor_inventario = sum(p['cantidad'] * p['precio'] for p in productos)
    stock_bajo = sum(1 for p in productos if 0 < p['cantidad'] <= 5)
    agotados = sum(1 for p in productos if p['cantidad'] == 0)
    
    return render_template(
        'index.html',
        productos=productos,
        movimientos=movimientos_recientes,
        total_productos=total_productos,
        unidades_totales=unidades_totales,
        valor_inventario=valor_inventario,
        stock_bajo=stock_bajo,
        agotados=agotados
    )

@app.route('/agregar_producto', methods=['GET', 'POST'])
@login_requerido
def agregar_producto():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        categoria = request.form.get('categoria')
        cantidad = int(request.form.get('cantidad', 0))
        precio = float(request.form.get('precio', 0.0))
        
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO productos (nombre, categoria, cantidad, precio) VALUES (?, ?, ?, ?)",
            (nombre, categoria, cantidad, precio)
        )
        conexion.commit()
        conexion.close()
        flash("Producto agregado exitosamente.", "success")
        return redirect(url_for('inicio'))
        
    return render_template('producto_form.html', producto=None)

@app.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
@login_requerido
def editar_producto(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        categoria = request.form.get('categoria')
        cantidad = int(request.form.get('cantidad', 0))
        precio = float(request.form.get('precio', 0.0))
        
        cursor.execute("""
            UPDATE productos 
            SET nombre = ?, categoria = ?, cantidad = ?, precio = ? 
            WHERE id = ?
        """, (nombre, categoria, cantidad, precio, id))
        conexion.commit()
        conexion.close()
        flash("Producto actualizado correctamente.", "success")
        return redirect(url_for('inicio'))

    cursor.execute("SELECT * FROM productos WHERE id = ?", (id,))
    producto = cursor.fetchone()
    conexion.close()
    
    if not producto:
        flash("El producto no existe.", "danger")
        return redirect(url_for('inicio'))

    return render_template('producto_form.html', producto=producto)

@app.route('/eliminar_producto/<int:id>')
@login_requerido
@requerir_roles('administrador', 'admin')
def eliminar_producto(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id,))
    conexion.commit()
    conexion.close()
    flash("Producto eliminado correctamente.", "success")
    return redirect(url_for('inicio'))

# --- RUTAS DE PROVEEDORES ---
@app.route('/proveedores')
@app.route('/listar_proveedores')
@login_requerido
def listar_proveedores():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM proveedores")
    lista_proveedores = cursor.fetchall()
    conexion.close()
    return render_template('proveedores.html', proveedores=lista_proveedores)

# --- RUTAS DE REPORTES Y MOVIMIENTOS ---
@app.route('/reporte_csv')
@login_requerido
def reporte_csv():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    conexion.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nombre', 'Categoria', 'Cantidad', 'Precio'])
    for p in productos:
        writer.writerow([p['id'], p['nombre'], p['categoria'], p['cantidad'], p['precio']])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventario_reporte.csv"}
    )

@app.route('/reporte_grafico')
@login_requerido
def reporte_grafico():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre, cantidad FROM productos")
    productos = cursor.fetchall()
    conexion.close()

    nombres = [p['nombre'] for p in productos]
    cantidades = [p['cantidad'] for p in productos]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if nombres:
        bars = ax.bar(nombres, cantidades, color='#0d6efd')
        ax.set_ylabel('Cantidad en Stock')
        ax.set_title('Reporte de Stock por Producto')
        plt.xticks(rotation=30, ha='right')
        ax.bar_label(bars)
    else:
        ax.text(0.5, 0.5, 'No hay productos registrados', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)

    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100)
    img.seek(0)
    plt.close(fig)
    return Response(img.getvalue(), mimetype='image/png')

@app.route('/movimientos')
@login_requerido
def movimientos():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT m.id, p.nombre as producto, m.tipo, m.cantidad, m.fecha, m.usuario
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        ORDER BY m.id DESC
    """)
    lista_movimientos = cursor.fetchall()
    conexion.close()
    return render_template('movimientos.html', movimientos=lista_movimientos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)