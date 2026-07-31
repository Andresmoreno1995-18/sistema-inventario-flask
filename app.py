import os
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file

app = Flask(__name__)
app.secret_key = 'clave_secreta_inventario'

DB_NAME = 'inventario.db'

# --- INICIALIZACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla Usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Tabla Productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio REAL NOT NULL,
            existencias INTEGER NOT NULL
        )
    ''')
    
    # Tabla Proveedores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            contacto TEXT,
            telefono TEXT
        )
    ''')
    
    # Tabla Movimientos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            producto_id INTEGER,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT,
            usuario TEXT,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')
    
    # Usuario por defecto si no existe
    cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (usuario, password) VALUES ('admin', 'admin123')")
        
    conn.commit()
    conn.close()

init_db()

# --- RUTAS DE LA APLICACIÓN ---

@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Consultar Productos
    cursor.execute("SELECT id, nombre, categoria, precio, existencias FROM productos")
    productos = cursor.fetchall()
    
    # Consultar Últimos Movimientos
    cursor.execute('''
        SELECT m.fecha, p.nombre, m.tipo, m.cantidad, m.usuario 
        FROM movimientos m 
        JOIN productos p ON m.producto_id = p.id 
        ORDER BY m.id DESC LIMIT 5
    ''')
    movimientos = cursor.fetchall()
    
    # Métricas para las tarjetas superiores
    total_productos = len(productos)
    unidades_totales = sum(p[4] for p in productos) if productos else 0
    valor_inventario = sum(p[3] * p[4] for p in productos) if productos else 0.0
    stock_bajo = sum(1 for p in productos if 0 < p[4] <= 5)
    agotados = sum(1 for p in productos if p[4] == 0)
    
    conn.close()
    
    return render_template(
        'index.html',
        productos=productos,
        movimientos=movimientos,
        total_productos=total_productos,
        unidades_totales=unidades_totales,
        valor_inventario=valor_inventario,
        stock_bajo=stock_bajo,
        agotados=agotados
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND password = ?", (usuario, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['usuario'] = usuario
            flash('¡Inicio de sesión exitoso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('login'))

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        precio = float(request.form['precio'])
        existencias = int(request.form['existencias'])
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO productos (nombre, categoria, precio, existencias) VALUES (?, ?, ?, ?)",
                       (nombre, categoria, precio, existencias))
        conn.commit()
        conn.close()
        
        flash('Producto agregado con éxito.', 'success')
        return redirect(url_for('index'))
        
    return render_template('producto_form.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        precio = float(request.form['precio'])
        existencias = int(request.form['existencias'])
        
        cursor.execute("UPDATE productos SET nombre = ?, categoria = ?, precio = ?, existencias = ? WHERE id = ?",
                       (nombre, categoria, precio, existencias, id))
        conn.commit()
        conn.close()
        
        flash('Producto actualizado.', 'success')
        return redirect(url_for('index'))
        
    cursor.execute("SELECT * FROM productos WHERE id = ?", (id,))
    producto = cursor.fetchone()
    conn.close()
    
    return render_template('producto_form.html', producto=producto)

@app.route('/eliminar/<int:id>')
def eliminar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    flash('Producto eliminado.', 'warning')
    return redirect(url_for('index'))

@app.route('/movimientos', methods=['GET', 'POST'])
def movimientos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        producto_id = int(request.form['producto_id'])
        tipo = request.form['tipo']
        cantidad = int(request.form['cantidad'])
        motivo = request.form.get('motivo', '')
        usuario = session.get('usuario', 'admin')
        
        # Validar existencias
        cursor.execute("SELECT existencias FROM productos WHERE id = ?", (producto_id,))
        prod = cursor.fetchone()
        
        if prod:
            stock_actual = prod[0]
            if tipo == 'Salida' and cantidad > stock_actual:
                flash(f'Error: No hay suficiente stock. Disponible: {stock_actual}', 'danger')
            else:
                nuevo_stock = stock_actual + cantidad if tipo == 'Entrada' else stock_actual - cantidad
                cursor.execute("UPDATE productos SET existencias = ? WHERE id = ?", (nuevo_stock, producto_id))
                cursor.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, motivo, usuario) VALUES (?, ?, ?, ?, ?)",
                               (producto_id, tipo, cantidad, motivo, usuario))
                conn.commit()
                flash('Movimiento registrado correctamente.', 'success')
                
    cursor.execute("SELECT id, nombre, categoria, precio, existencias FROM productos")
    productos = cursor.fetchall()
    
    cursor.execute('''
        SELECT m.fecha, p.nombre, m.tipo, m.cantidad, m.motivo, m.usuario 
        FROM movimientos m 
        JOIN productos p ON m.producto_id = p.id 
        ORDER BY m.id DESC
    ''')
    lista_movimientos = cursor.fetchall()
    
    conn.close()
    return render_template('movimientos.html', productos=productos, movimientos=lista_movimientos)

@app.route('/proveedores', methods=['GET', 'POST'])
def proveedores():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        contacto = request.form['contacto']
        telefono = request.form['telefono']
        
        cursor.execute("INSERT INTO proveedores (nombre, contacto, telefono) VALUES (?, ?, ?)",
                       (nombre, contacto, telefono))
        conn.commit()
        flash('Proveedor agregado.', 'success')
        
    cursor.execute("SELECT * FROM proveedores")
    provs = cursor.fetchall()
    conn.close()
    
    return render_template('proveedores.html', proveedores=provs)

@app.route('/exportar')
def exportar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    
    csv_path = "inventario_export.csv"
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)

@app.route('/grafico')
def grafico():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT nombre, existencias FROM productos", conn)
    conn.close()
    
    if not df.empty:
        plt.figure(figsize=(8, 4))
        plt.bar(df['nombre'], df['existencias'], color='skyblue')
        plt.xlabel('Productos')
        plt.ylabel('Existencias')
        plt.title('Stock Actual por Producto')
        plt.tight_layout()
        img_path = "static/grafico.png"
        os.makedirs("static", exist_ok=True)
        plt.savefig(img_path)
        plt.close()
        return send_file(img_path, mimetype='image/png')
    
    flash('No hay datos para generar el gráfico.', 'warning')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
