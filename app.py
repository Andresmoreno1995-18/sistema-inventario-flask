import os
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

import psycopg2
from psycopg2.extras import RealDictCursor

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# CONFIGURACIÓN
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave_secreta_inventario_2026"
)

DATABASE_URL = os.environ.get("DATABASE_URL")


# =========================================================
# CONEXIÓN A POSTGRESQL
# =========================================================

def get_db():

    if not DATABASE_URL:

        raise RuntimeError(
            "No se encontró la variable DATABASE_URL."
        )

    conn = psycopg2.connect(DATABASE_URL)

    # Hora oficial de Colombia
    cursor = conn.cursor()

    cursor.execute(
        "SET TIME ZONE 'America/Bogota'"
    )

    cursor.close()

    return conn


# =========================================================
# SEGURIDAD DE CONTRASEÑAS
# =========================================================

def password_is_hashed(password):

    if not password:
        return False

    return password.startswith((
        "scrypt:",
        "pbkdf2:"
    ))


def migrate_old_passwords(cursor):

    cursor.execute("""
        SELECT
            id,
            password
        FROM usuarios
    """)

    usuarios = cursor.fetchall()

    for usuario in usuarios:

        usuario_id = usuario[0]
        password_actual = usuario[1]

        if not password_is_hashed(password_actual):

            password_protegida = generate_password_hash(
                password_actual
            )

            cursor.execute("""
                UPDATE usuarios
                SET password = %s
                WHERE id = %s
            """, (
                password_protegida,
                usuario_id
            ))


# =========================================================
# FUNCIONES DE PERMISOS
# =========================================================

def usuario_logueado():

    return "usuario" in session


def es_admin():

    return (
        "usuario" in session
        and session.get("rol") == "admin"
    )


def requiere_login():

    if not usuario_logueado():

        flash(
            "Debe iniciar sesión para acceder.",
            "danger"
        )

        return False

    return True


def requiere_admin():

    if not usuario_logueado():

        flash(
            "Debe iniciar sesión para acceder.",
            "danger"
        )

        return False

    if session.get("rol") != "admin":

        flash(
            "No tienes permisos de administrador para realizar esta acción.",
            "danger"
        )

        return False

    return True


# =========================================================
# INICIALIZAR BASE DE DATOS
# =========================================================

def init_db():

    conn = get_db()

    cursor = conn.cursor()


    # =====================================================
    # USUARIOS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'admin',
            genero TEXT NOT NULL DEFAULT 'Hombre',
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""
        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS genero TEXT NOT NULL DEFAULT 'Hombre'
    """)


    cursor.execute("""
        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS fecha_registro
        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """)


    # =====================================================
    # PRODUCTOS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio DOUBLE PRECISION NOT NULL DEFAULT 0,
            existencias INTEGER NOT NULL DEFAULT 0
        )
    """)


    # =====================================================
    # PROVEEDORES
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            contacto TEXT,
            telefono TEXT
        )
    """)


    # =====================================================
    # MOVIMIENTOS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id SERIAL PRIMARY KEY,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            producto_id INTEGER,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT,
            factura TEXT,
            orden_compra TEXT,
            comentarios TEXT,
            usuario TEXT,
            FOREIGN KEY (producto_id)
                REFERENCES productos(id)
                ON DELETE CASCADE
        )
    """)


    # =====================================================
    # AGREGAR CAMPOS SI YA EXISTÍA LA TABLA
    # =====================================================

    cursor.execute("""
        ALTER TABLE movimientos
        ADD COLUMN IF NOT EXISTS factura TEXT
    """)


    cursor.execute("""
        ALTER TABLE movimientos
        ADD COLUMN IF NOT EXISTS orden_compra TEXT
    """)


    cursor.execute("""
        ALTER TABLE movimientos
        ADD COLUMN IF NOT EXISTS comentarios TEXT
    """)


    # =====================================================
    # USUARIO ADMINISTRADOR
    # =====================================================

    cursor.execute("""
        SELECT
            id,
            password,
            rol
        FROM usuarios
        WHERE usuario = %s
    """, (
        "admin",
    ))


    usuario_admin = cursor.fetchone()


    if usuario_admin is None:

        password_admin = generate_password_hash(
            "admin123"
        )

        cursor.execute("""
            INSERT INTO usuarios
            (
                usuario,
                password,
                rol,
                genero,
                fecha_registro
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                CURRENT_TIMESTAMP
            )
        """, (
            "admin",
            password_admin,
            "admin",
            "Hombre"
        ))

    else:

        cursor.execute("""
            UPDATE usuarios
            SET rol = 'admin'
            WHERE usuario = 'admin'
        """)


    # =====================================================
    # MIGRAR CONTRASEÑAS ANTIGUAS
    # =====================================================

    migrate_old_passwords(cursor)


    conn.commit()

    cursor.close()

    conn.close()


# =========================================================
# CREAR TABLAS AUTOMÁTICAMENTE
# =========================================================

init_db()


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/")
def index():

    if not requiere_login():

        return redirect(
            url_for("login")
        )


    # =====================================================
    # DATOS DE BÚSQUEDA
    # =====================================================

    busqueda = request.args.get(
        "q",
        ""
    ).strip()


    filtro_stock = request.args.get(
        "stock",
        "todos"
    ).strip().lower()


    if filtro_stock not in (
        "todos",
        "stock",
        "bajo",
        "agotado"
    ):

        filtro_stock = "todos"


    conn = get_db()

    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )


    # =====================================================
    # CONSTRUIR FILTROS DE PRODUCTOS
    # =====================================================

    condiciones = []

    parametros = []


    if busqueda:

        condiciones.append("""
            (
                CAST(id AS TEXT) ILIKE %s
                OR nombre ILIKE %s
                OR COALESCE(categoria, '') ILIKE %s
            )
        """)

        texto_busqueda = f"%{busqueda}%"

        parametros.extend([
            texto_busqueda,
            texto_busqueda,
            texto_busqueda
        ])


    if filtro_stock == "stock":

        condiciones.append("""
            existencias > 0
        """)


    elif filtro_stock == "bajo":

        condiciones.append("""
            existencias BETWEEN 1 AND 5
        """)


    elif filtro_stock == "agotado":

        condiciones.append("""
            existencias = 0
        """)


    where_sql = ""


    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # =====================================================
    # PRODUCTOS
    # =====================================================

    cursor.execute(f"""
        SELECT
            id,
            nombre,
            categoria,
            precio,
            existencias
        FROM productos

        {where_sql}

        ORDER BY id DESC
    """, parametros)


    productos = cursor.fetchall()


    # =====================================================
    # MOVIMIENTOS
    #
    # IMPORTANTE:
    #
    # Si se está consultando un producto:
    # solamente aparecen movimientos de los productos
    # que coinciden con la consulta.
    #
    # Si no se está consultando ningún producto:
    # aparecen los últimos 5 movimientos generales.
    # =====================================================

    if busqueda or filtro_stock != "todos":

        cursor.execute(f"""
            SELECT
                m.fecha,
                p.nombre,
                m.tipo,
                m.cantidad,
                m.motivo,
                m.factura,
                m.orden_compra,
                m.comentarios,
                m.usuario
            FROM movimientos m

            INNER JOIN productos p
                ON m.producto_id = p.id

            {where_sql}

            ORDER BY m.id DESC
            LIMIT 50
        """, parametros)


        movimientos = cursor.fetchall()

    else:

        cursor.execute("""
            SELECT
                m.fecha,
                p.nombre,
                m.tipo,
                m.cantidad,
                m.motivo,
                m.factura,
                m.orden_compra,
                m.comentarios,
                m.usuario
            FROM movimientos m

            LEFT JOIN productos p
                ON m.producto_id = p.id

            ORDER BY m.id DESC
            LIMIT 5
        """)


        movimientos = cursor.fetchall()


    # =====================================================
    # RESUMEN
    # =====================================================

    total_productos = len(
        productos
    )


    unidades_totales = sum(
        producto["existencias"]
        for producto in productos
    )


    valor_inventario = sum(
        float(producto["precio"])
        * producto["existencias"]
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


    cursor.close()

    conn.close()


    return render_template(

        "index.html",

        productos=productos,

        movimientos=movimientos,

        total_productos=total_productos,

        unidades_totales=unidades_totales,

        valor_inventario=valor_inventario,

        stock_bajo=stock_bajo,

        agotados=agotados,

        busqueda=busqueda,

        filtro_stock=filtro_stock
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()


        password = request.form.get(
            "password",
            ""
        )


        if not usuario or not password:

            flash(
                "Debe ingresar usuario y contraseña.",
                "danger"
            )

            return render_template(
                "login.html"
            )


        conn = get_db()

        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )


        cursor.execute("""
            SELECT
                id,
                usuario,
                password,
                rol,
                genero
            FROM usuarios
            WHERE usuario = %s
        """, (
            usuario,
        ))


        user = cursor.fetchone()


        cursor.close()

        conn.close()


        if user and check_password_hash(
            user["password"],
            password
        ):

            session["usuario"] = user["usuario"]

            session["rol"] = user["rol"]

            session["genero"] = user["genero"]


            flash(
                "¡Inicio de sesión exitoso!",
                "success"
            )


            return redirect(
                url_for("index")
            )


        flash(
            "Usuario o contraseña incorrectos.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# =========================================================
# REGISTRO DE USUARIOS
# =========================================================

@app.route(
    "/registro",
    methods=["GET", "POST"]
)
def registro():

    if not requiere_admin():

        return redirect(
            url_for("index")
        )


    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()


        password = request.form.get(
            "password",
            ""
        )


        genero = request.form.get(
            "genero",
            ""
        ).strip()


        rol = request.form.get(
            "rol",
            ""
        ).strip()


        if not usuario or not password:

            flash(
                "Debe ingresar usuario y contraseña.",
                "danger"
            )

            return render_template(
                "registro.html"
            )


        if genero not in (
            "Hombre",
            "Mujer"
        ):

            flash(
                "Debe seleccionar Hombre o Mujer.",
                "danger"
            )

            return render_template(
                "registro.html"
            )


        if rol not in (
            "admin",
            "usuario"
        ):

            flash(
                "Debe seleccionar un rol válido.",
                "danger"
            )

            return render_template(
                "registro.html"
            )


        conn = get_db()

        cursor = conn.cursor()


        cursor.execute("""
            SELECT id
            FROM usuarios
            WHERE usuario = %s
        """, (
            usuario,
        ))


        usuario_existente = cursor.fetchone()


        if usuario_existente:

            cursor.close()

            conn.close()


            flash(
                "Ese nombre de usuario ya existe.",
                "danger"
            )


            return render_template(
                "registro.html"
            )


        password_protegida = generate_password_hash(
            password
        )


        cursor.execute("""
            INSERT INTO usuarios
            (
                usuario,
                password,
                rol,
                genero,
                fecha_registro
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                CURRENT_TIMESTAMP
            )
        """, (
            usuario,
            password_protegida,
            rol,
            genero
        ))


        conn.commit()

        cursor.close()

        conn.close()


        flash(
            "Usuario registrado correctamente.",
            "success"
        )


        return redirect(
            url_for("index")
        )


    return render_template(
        "registro.html"
    )


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


    return redirect(
        url_for("login")
    )


# =========================================================
# AGREGAR PRODUCTO
# =========================================================

@app.route(
    "/agregar",
    methods=["GET", "POST"]
)
def agregar():

    if not requiere_admin():

        return redirect(
            url_for("index")
        )


    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()


        categoria = request.form.get(
            "categoria",
            ""
        ).strip()


        try:

            precio = float(
                request.form.get(
                    "precio",
                    0
                )
            )


            existencias = int(
                request.form.get(
                    "existencias",
                    0
                )
            )


        except ValueError:

            flash(
                "Precio o existencias no tienen un valor válido.",
                "danger"
            )


            return render_template(
                "producto_form.html"
            )


        conn = get_db()

        cursor = conn.cursor()


        cursor.execute("""
            INSERT INTO productos
            (
                nombre,
                categoria,
                precio,
                existencias
            )
            VALUES (%s, %s, %s, %s)
        """, (
            nombre,
            categoria,
            precio,
            existencias
        ))


        conn.commit()

        cursor.close()

        conn.close()


        flash(
            "Producto agregado con éxito.",
            "success"
        )


        return redirect(
            url_for("index")
        )


    return render_template(
        "producto_form.html"
    )


# =========================================================
# EDITAR PRODUCTO
# =========================================================

@app.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    if not requiere_admin():

        return redirect(
            url_for("index")
        )


    conn = get_db()

    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )


    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()


        categoria = request.form.get(
            "categoria",
            ""
        ).strip()


        try:

            precio = float(
                request.form.get(
                    "precio",
                    0
                )
            )


            existencias = int(
                request.form.get(
                    "existencias",
                    0
                )
            )


        except ValueError:

            cursor.close()

            conn.close()


            flash(
                "Precio o existencias no válidos.",
                "danger"
            )


            return redirect(
                url_for(
                    "editar",
                    id=id
                )
            )


        cursor.execute("""
            UPDATE productos
            SET
                nombre = %s,
                categoria = %s,
                precio = %s,
                existencias = %s
            WHERE id = %s
        """, (
            nombre,
            categoria,
            precio,
            existencias,
            id
        ))


        conn.commit()

        cursor.close()

        conn.close()


        flash(
            "Producto actualizado.",
            "success"
        )


        return redirect(
            url_for("index")
        )


    cursor.execute("""
        SELECT *
        FROM productos
        WHERE id = %s
    """, (
        id,
    ))


    producto = cursor.fetchone()


    cursor.close()

    conn.close()


    if producto is None:

        flash(
            "Producto no encontrado.",
            "danger"
        )


        return redirect(
            url_for("index")
        )


    return render_template(
        "producto_form.html",
        producto=producto
    )


# =========================================================
# ELIMINAR PRODUCTO
# =========================================================

@app.route(
    "/eliminar/<int:id>"
)
def eliminar(id):

    if not requiere_admin():

        return redirect(
            url_for("index")
        )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute("""
        DELETE FROM movimientos
        WHERE producto_id = %s
    """, (
        id,
    ))


    cursor.execute("""
        DELETE FROM productos
        WHERE id = %s
    """, (
        id,
    ))


    conn.commit()

    cursor.close()

    conn.close()


    flash(
        "Producto eliminado.",
        "warning"
    )


    return redirect(
        url_for("index")
    )


# =========================================================
# MOVIMIENTOS
# =========================================================

@app.route(
    "/movimientos",
    methods=["GET", "POST"]
)
def movimientos():

    if not requiere_login():

        return redirect(
            url_for("login")
        )


    conn = get_db()

    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )


    if request.method == "POST":

        try:

            producto_id = int(
                request.form.get(
                    "producto_id"
                )
            )


            cantidad = int(
                request.form.get(
                    "cantidad"
                )
            )


        except (
            TypeError,
            ValueError
        ):

            cursor.close()

            conn.close()


            flash(
                "Cantidad o producto no válidos.",
                "danger"
            )


            return redirect(
                url_for("movimientos")
            )


        tipo = request.form.get(
            "tipo",
            ""
        ).strip()


        motivo = request.form.get(
            "motivo",
            ""
        ).strip()


        factura = request.form.get(
            "factura",
            ""
        ).strip()


        orden_compra = request.form.get(
            "orden_compra",
            ""
        ).strip()


        comentarios = request.form.get(
            "comentarios",
            ""
        ).strip()


        usuario = session.get(
            "usuario",
            "admin"
        )


        cursor.execute("""
            SELECT existencias
            FROM productos
            WHERE id = %s
        """, (
            producto_id,
        ))


        producto = cursor.fetchone()


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


        elif (
            tipo == "Salida"
            and cantidad > producto["existencias"]
        ):

            flash(
                f"No hay suficiente stock. Disponible: {producto['existencias']}",
                "danger"
            )


        elif tipo not in (
            "Entrada",
            "Salida"
        ):

            flash(
                "Tipo de movimiento no válido.",
                "danger"
            )


        elif motivo not in (
            "Compra",
            "Venta",
            "Devolución de cliente",
            "Devolución a proveedor",
            "Ajuste de inventario",
            "Otro"
        ):

            flash(
                "Debe seleccionar un motivo válido.",
                "danger"
            )


        elif (
            motivo in (
                "Devolución de cliente",
                "Devolución a proveedor"
            )
            and not comentarios
        ):

            flash(
                "En una devolución debe indicar el motivo o explicación en comentarios.",
                "danger"
            )


        else:

            stock_actual = producto[
                "existencias"
            ]


            if tipo == "Entrada":

                nuevo_stock = (
                    stock_actual + cantidad
                )

            else:

                nuevo_stock = (
                    stock_actual - cantidad
                )


            cursor.execute("""
                UPDATE productos
                SET existencias = %s
                WHERE id = %s
            """, (
                nuevo_stock,
                producto_id
            ))


            # =================================================
            # REGISTRAR MOVIMIENTO
            # =================================================

            cursor.execute("""
                INSERT INTO movimientos
                (
                    fecha,
                    producto_id,
                    tipo,
                    cantidad,
                    motivo,
                    factura,
                    orden_compra,
                    comentarios,
                    usuario
                )
                VALUES (
                    CURRENT_TIMESTAMP,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                producto_id,
                tipo,
                cantidad,
                motivo,
                factura,
                orden_compra,
                comentarios,
                usuario
            ))


            conn.commit()


            flash(
                "Movimiento registrado correctamente.",
                "success"
            )


    # =====================================================
    # PRODUCTOS
    # =====================================================

    cursor.execute("""
        SELECT
            id,
            nombre,
            categoria,
            precio,
            existencias
        FROM productos
        ORDER BY nombre
    """)


    productos = cursor.fetchall()


    # =====================================================
    # HISTORIAL DE MOVIMIENTOS
    #
    # IMPORTANTE:
    # NO usamos TO_CHAR.
    #
    # fecha queda como TIMESTAMP para que el HTML pueda
    # utilizar:
    #
    # mov["fecha"].strftime(...)
    # =====================================================

    cursor.execute("""
        SELECT
            m.fecha,
            p.nombre,
            m.tipo,
            m.cantidad,
            m.motivo,
            m.factura,
            m.orden_compra,
            m.comentarios,
            m.usuario
        FROM movimientos m
        LEFT JOIN productos p
            ON m.producto_id = p.id
        ORDER BY m.id DESC
    """)


    lista_movimientos = cursor.fetchall()


    cursor.close()

    conn.close()


    return render_template(
        "movimientos.html",
        productos=productos,
        movimientos=lista_movimientos
    )


# =========================================================
# PROVEEDORES
# =========================================================

@app.route(
    "/proveedores",
    methods=["GET", "POST"]
)
def proveedores():

    if not requiere_login():

        return redirect(
            url_for("login")
        )


    conn = get_db()

    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )


    if request.method == "POST":

        if not es_admin():

            cursor.close()

            conn.close()


            flash(
                "No tienes permisos para agregar proveedores.",
                "danger"
            )


            return redirect(
                url_for("proveedores")
            )


        nombre = request.form.get(
            "nombre",
            ""
        ).strip()


        contacto = request.form.get(
            "contacto",
            ""
        ).strip()


        telefono = request.form.get(
            "telefono",
            ""
        ).strip()


        cursor.execute("""
            INSERT INTO proveedores
            (
                nombre,
                contacto,
                telefono
            )
            VALUES (%s, %s, %s)
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


    cursor.execute("""
        SELECT *
        FROM proveedores
        ORDER BY id DESC
    """)


    provs = cursor.fetchall()


    cursor.close()

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

    if not requiere_admin():

        return redirect(
            url_for("index")
        )


    conn = get_db()


    df = pd.read_sql_query(
        """
        SELECT
            id,
            nombre,
            categoria,
            precio,
            existencias
        FROM productos
        """,
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

    if not requiere_login():

        return redirect(
            url_for("login")
        )


    conn = get_db()


    df = pd.read_sql_query(
        """
        SELECT
            nombre,
            existencias
        FROM productos
        """,
        conn
    )


    conn.close()


    if df.empty:

        flash(
            "No hay datos para generar el gráfico.",
            "warning"
        )


        return redirect(
            url_for("index")
        )


    plt.figure(
        figsize=(8, 4)
    )


    plt.bar(
        df["nombre"],
        df["existencias"]
    )


    plt.xlabel(
        "Productos"
    )


    plt.ylabel(
        "Existencias"
    )


    plt.title(
        "Stock Actual por Producto"
    )


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


    plt.savefig(
        img_path
    )


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
        os.environ.get(
            "PORT",
            5000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
