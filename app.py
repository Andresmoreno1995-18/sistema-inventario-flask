import os
import sqlite3
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file
)


# =========================================================
# CONFIGURACIÓN
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave_secreta_inventario_2026"
)

DB_NAME = "inventario.db"


# =========================================================
# CONEXIÓN A BASE DE DATOS
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# INICIALIZAR BASE DE DATOS
# =========================================================

def init_db():

    conn = get_db()
    cursor = conn.cursor()

    # -------------------------
    # USUARIOS
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'admin'
        )
    """)

    # -------------------------
    # PRODUCTOS
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio REAL NOT NULL DEFAULT 0,
            existencias INTEGER NOT NULL DEFAULT 0
        )
    """)

    # -------------------------
    # PROVEEDORES
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            contacto TEXT,
            telefono TEXT
        )
    """)

    # -------------------------
    # MOVIMIENTOS
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            producto_id INTEGER,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT,
            usuario TEXT,
            FOREIGN KEY (producto_id)
                REFERENCES productos(id)
        )
    """)

    # -------------------------
    # USUARIO ADMINISTRADOR
    # -------------------------

    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        ("admin",)
    )

    usuario_admin = cursor.fetchone()

    if usuario_admin is None:

        cursor.execute("""
            INSERT INTO usuarios
            (usuario, password, rol)
            VALUES (?, ?, ?)
        """, (
            "admin",
            "admin123",
            "admin"
        ))

    conn.commit()
    conn.close()


# Crear la base de datos automáticamente
init_db()


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/")
def index():

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    productos = conn.execute("""
        SELECT
            id,
            nombre,
            categoria,
            precio,
            existencias
        FROM productos
        ORDER BY id DESC
    """).fetchall()

    movimientos = conn.execute("""
        SELECT
            m.fecha,
            p.nombre,
            m.tipo,
            m.cantidad,
            m.usuario
        FROM movimientos m
        LEFT JOIN productos p
            ON m.producto_id = p.id
        ORDER BY m.id DESC
        LIMIT 5
    """).fetchall()

    total_productos = len(productos)

    unidades_totales = sum(
        producto["existencias"]
        for producto in productos
    )

    valor_inventario = sum(
        producto["precio"] * producto["existencias"]
        for producto in productos
    )

    stock_bajo = sum(
        1
        for producto in productos
        if 0 < producto["existencias"] <= 5
    )

    agotados = sum(
        1
        for producto in productos
        if producto["existencias"] == 0
    )

    conn.close()

    return render_template(
        "index.html",
        productos=productos,
        movimientos=movimientos,
        total_productos=total_productos,
        unidades_totales=unidades_totales,
        valor_inventario=valor_inventario,
        stock_bajo=stock_bajo,
        agotados=agotados
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        if not usuario or not password:

            flash(
                "Debe ingresar usuario y contraseña.",
                "danger"
            )

            return render_template("login.html")

        conn = get_db()

        user = conn.execute("""
            SELECT
                id,
                usuario,
                password,
                rol
            FROM usuarios
            WHERE usuario = ?
              AND password = ?
        """, (
            usuario,
            password
        )).fetchone()

        conn.close()

        if user:

            session["usuario"] = user["usuario"]
            session["rol"] = user["rol"]

            flash(
                "¡Inicio de sesión exitoso!",
                "success"
            )

            return redirect(url_for("index"))

        flash(
            "Usuario o contraseña incorrectos.",
            "danger"
        )

    return render_template("login.html")


# =========================================================
# CERRAR SESIÓN
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Sesión cerrada correctamente.",
        "info"
    )

    return redirect(url_for("login"))


# =========================================================
# AGREGAR PRODUCTO
# =========================================================

@app.route("/agregar", methods=["GET", "POST"])
def agregar():

    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()
        categoria = request.form.get("categoria", "").strip()

        try:
            precio = float(request.form.get("precio", 0))
            existencias = int(
                request.form.get("existencias", 0)
            )
        except ValueError:

            flash(
                "Precio o existencias no tienen un valor válido.",
                "danger"
            )

            return render_template("producto_form.html")

        conn = get_db()

        conn.execute("""
            INSERT INTO productos
            (nombre, categoria, precio, existencias)
            VALUES (?, ?, ?, ?)
        """, (
            nombre,
            categoria,
            precio,
            existencias
        ))

        conn.commit()
        conn.close()

        flash(
            "Producto agregado con éxito.",
            "success"
        )

        return redirect(url_for("index"))

    return render_template("producto_form.html")


# =========================================================
# EDITAR PRODUCTO
# =========================================================

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()
        categoria = request.form.get("categoria", "").strip()

        try:
            precio = float(request.form.get("precio", 0))
            existencias = int(
                request.form.get("existencias", 0)
            )
        except ValueError:

            conn.close()

            flash(
                "Precio o existencias no válidos.",
                "danger"
            )

            return redirect(
                url_for("editar", id=id)
            )

        conn.execute("""
            UPDATE productos
            SET
                nombre = ?,
                categoria = ?,
                precio = ?,
                existencias = ?
            WHERE id = ?
        """, (
            nombre,
            categoria,
            precio,
            existencias,
            id
        ))

        conn.commit()
        conn.close()

        flash(
            "Producto actualizado.",
            "success"
        )

        return redirect(url_for("index"))

    producto = conn.execute("""
        SELECT *
        FROM productos
        WHERE id = ?
    """, (id,)).fetchone()

    conn.close()

    if producto is None:

        flash(
            "Producto no encontrado.",
            "danger"
        )

        return redirect(url_for("index"))

    return render_template(
        "producto_form.html",
        producto=producto
    )


# =========================================================
# ELIMINAR PRODUCTO
# =========================================================

@app.route("/eliminar/<int:id>")
def eliminar(id):

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    conn.execute(
        "DELETE FROM movimientos WHERE producto_id = ?",
        (id,)
    )

    conn.execute(
        "DELETE FROM productos WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash(
        "Producto eliminado.",
        "warning"
    )

    return redirect(url_for("index"))


# =========================================================
# MOVIMIENTOS
# =========================================================

@app.route("/movimientos", methods=["GET", "POST"])
def movimientos():

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":

        try:
            producto_id = int(
                request.form.get("producto_id")
            )

            cantidad = int(
                request.form.get("cantidad")
            )

        except (TypeError, ValueError):

            conn.close()

            flash(
                "Cantidad o producto no válidos.",
                "danger"
            )

            return redirect(
                url_for("movimientos")
            )

        tipo = request.form.get("tipo", "").strip()
        motivo = request.form.get("motivo", "").strip()
        usuario = session.get("usuario", "admin")

        producto = conn.execute("""
            SELECT existencias
            FROM productos
            WHERE id = ?
        """, (producto_id,)).fetchone()

        if producto is None:

            flash(
                "El producto no existe.",
                "danger"
            )

        elif cantidad <= 0:

            flash(
                "La cantidad debe ser mayor que cero.",
                "danger"
            )

        elif tipo == "Salida" and cantidad > producto["existencias"]:

            flash(
                f"No hay suficiente stock. Disponible: {producto['existencias']}",
                "danger"
            )

        elif tipo not in ("Entrada", "Salida"):

            flash(
                "Tipo de movimiento no válido.",
                "danger"
            )

        else:

            stock_actual = producto["existencias"]

            if tipo == "Entrada":
                nuevo_stock = stock_actual + cantidad
            else:
                nuevo_stock = stock_actual - cantidad

            conn.execute("""
                UPDATE productos
                SET existencias = ?
                WHERE id = ?
            """, (
                nuevo_stock,
                producto_id
            ))

            conn.execute("""
                INSERT INTO movimientos
                (
                    producto_id,
                    tipo,
                    cantidad,
                    motivo,
                    usuario
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                producto_id,
                tipo,
                cantidad,
                motivo,
                usuario
            ))

            conn.commit()

            flash(
                "Movimiento registrado correctamente.",
                "success"
            )

    productos = conn.execute("""
        SELECT
            id,
            nombre,
            categoria,
            precio,
            existencias
        FROM productos
        ORDER BY nombre
    """).fetchall()

    lista_movimientos = conn.execute("""
        SELECT
            m.fecha,
            p.nombre,
            m.tipo,
            m.cantidad,
            m.motivo,
            m.usuario
        FROM movimientos m
        LEFT JOIN productos p
            ON m.producto_id = p.id
        ORDER BY m.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "movimientos.html",
        productos=productos,
        movimientos=lista_movimientos
    )


# =========================================================
# PROVEEDORES
# =========================================================

@app.route("/proveedores", methods=["GET", "POST"])
def proveedores():

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()
        contacto = request.form.get("contacto", "").strip()
        telefono = request.form.get("telefono", "").strip()

        conn.execute("""
            INSERT INTO proveedores
            (nombre, contacto, telefono)
            VALUES (?, ?, ?)
        """, (
            nombre,
            contacto,
            telefono
        ))

        conn.commit()

        flash(
            "Proveedor agregado.",
            "success"
        )

    provs = conn.execute("""
        SELECT *
        FROM proveedores
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "proveedores.html",
        proveedores=provs
    )


# =========================================================
# EXPORTAR INVENTARIO
# =========================================================

@app.route("/exportar")
def exportar():

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)

    df = pd.read_sql_query(
        "SELECT * FROM productos",
        conn
    )

    conn.close()

    csv_path = "inventario_export.csv"

    df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    return send_file(
        csv_path,
        as_attachment=True,
        download_name="inventario_export.csv",
        mimetype="text/csv"
    )


# =========================================================
# GRÁFICO
# =========================================================

@app.route("/grafico")
def grafico():

    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)

    df = pd.read_sql_query("""
        SELECT
            nombre,
            existencias
        FROM productos
    """, conn)

    conn.close()

    if df.empty:

        flash(
            "No hay datos para generar el gráfico.",
            "warning"
        )

        return redirect(url_for("index"))

    plt.figure(figsize=(8, 4))

    plt.bar(
        df["nombre"],
        df["existencias"]
    )

    plt.xlabel("Productos")
    plt.ylabel("Existencias")
    plt.title("Stock Actual por Producto")

    plt.xticks(
        rotation=45,
        ha="right"
    )

    plt.tight_layout()

    os.makedirs(
        "static",
        exist_ok=True
    )

    img_path = "static/grafico.png"

    plt.savefig(img_path)

    plt.close()

    return send_file(
        img_path,
        mimetype="image/png"
    )


# =========================================================
# EJECUTAR APLICACIÓN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
