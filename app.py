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
    send_file,
    jsonify,
)

import psycopg2
from psycopg2.extras import RealDictCursor

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


# =========================================================
# CONFIGURACIÓN
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave_secreta_inventario_2026",
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

    cursor = conn.cursor()
    cursor.execute("SET TIME ZONE 'America/Bogota'")
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
        "pbkdf2:",
    ))


def migrate_old_passwords(cursor):
    cursor.execute("""
        SELECT id, password
        FROM usuarios
    """)

    for usuario_id, password_actual in cursor.fetchall():
        if not password_is_hashed(password_actual):
            cursor.execute("""
                UPDATE usuarios
                SET password = %s
                WHERE id = %s
            """, (
                generate_password_hash(password_actual),
                usuario_id,
            ))


# =========================================================
# PERMISOS
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
            "danger",
        )
        return False

    return True


def requiere_admin():
    if not usuario_logueado():
        flash(
            "Debe iniciar sesión para acceder.",
            "danger",
        )
        return False

    if session.get("rol") != "admin":
        flash(
            "No tienes permisos de administrador para realizar esta acción.",
            "danger",
        )
        return False

    return True


# =========================================================
# BASE DE DATOS
# =========================================================

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    try:
        # -----------------------------------------------------
        # USUARIOS
        # -----------------------------------------------------
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
            ADD COLUMN IF NOT EXISTS genero
            TEXT NOT NULL DEFAULT 'Hombre'
        """)

        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS fecha_registro
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        # -----------------------------------------------------
        # PROVEEDORES
        # -----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proveedores (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                contacto TEXT,
                telefono TEXT,
                email TEXT
            )
        """)

        cursor.execute("""
            ALTER TABLE proveedores
            ADD COLUMN IF NOT EXISTS contacto TEXT
        """)

        cursor.execute("""
            ALTER TABLE proveedores
            ADD COLUMN IF NOT EXISTS telefono TEXT
        """)

        cursor.execute("""
            ALTER TABLE proveedores
            ADD COLUMN IF NOT EXISTS email TEXT
        """)

        # -----------------------------------------------------
        # PRODUCTOS
        # -----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                categoria TEXT,
                precio DOUBLE PRECISION NOT NULL DEFAULT 0,
                existencias INTEGER NOT NULL DEFAULT 0,
                precio_compra DOUBLE PRECISION NOT NULL DEFAULT 0,
                proveedor_id INTEGER
            )
        """)

        cursor.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS categoria TEXT
        """)

        cursor.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS precio
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS existencias
            INTEGER NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS precio_compra
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS proveedor_id INTEGER
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_productos_nombre
            ON productos(nombre)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_productos_categoria
            ON productos(categoria)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_productos_proveedor
            ON productos(proveedor_id)
        """)

        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_productos_proveedor'
                ) THEN
                    ALTER TABLE productos
                    ADD CONSTRAINT fk_productos_proveedor
                    FOREIGN KEY (proveedor_id)
                    REFERENCES proveedores(id)
                    ON DELETE SET NULL;
                END IF;
            END
            $$;
        """)

        # -----------------------------------------------------
        # MOVIMIENTOS
        # -----------------------------------------------------
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

        cursor.execute("""
            ALTER TABLE movimientos
            ADD COLUMN IF NOT EXISTS fecha
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cursor.execute("""
            ALTER TABLE movimientos
            ADD COLUMN IF NOT EXISTS producto_id INTEGER
        """)

        cursor.execute("""
            ALTER TABLE movimientos
            ADD COLUMN IF NOT EXISTS tipo TEXT
        """)

        cursor.execute("""
            ALTER TABLE movimientos
            ADD COLUMN IF NOT EXISTS cantidad INTEGER
        """)

        cursor.execute("""
            ALTER TABLE movimientos
            ADD COLUMN IF NOT EXISTS motivo TEXT
        """)

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

        cursor.execute("""
            ALTER TABLE movimientos
            ADD COLUMN IF NOT EXISTS usuario TEXT
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_movimientos_producto
            ON movimientos(producto_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_movimientos_fecha
            ON movimientos(fecha)
        """)

        # -----------------------------------------------------
        # SECUENCIA DE FACTURAS
        # -----------------------------------------------------
        cursor.execute("""
            CREATE SEQUENCE IF NOT EXISTS factura_numero_seq
            START WITH 1
            INCREMENT BY 1
        """)

        # -----------------------------------------------------
        # FACTURAS
        # -----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id SERIAL PRIMARY KEY,
                numero_factura BIGINT UNIQUE NOT NULL
                    DEFAULT nextval('factura_numero_seq'),
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usuario TEXT NOT NULL,
                cliente_nombre TEXT,
                cliente_documento TEXT,
                cliente_telefono TEXT,
                cliente_email TEXT,
                metodo_pago TEXT DEFAULT 'Efectivo',
                subtotal DOUBLE PRECISION NOT NULL DEFAULT 0,
                descuento DOUBLE PRECISION NOT NULL DEFAULT 0,
                impuesto DOUBLE PRECISION NOT NULL DEFAULT 0,
                total DOUBLE PRECISION NOT NULL DEFAULT 0,
                estado TEXT NOT NULL DEFAULT 'Pagada',
                observaciones TEXT
            )
        """)

        # -----------------------------------------------------
        # MIGRACIÓN IMPORTANTE:
        # versiones anteriores pudieron crear numero_factura
        # como TEXT. Se convierte a BIGINT antes de usar MAX()
        # y la secuencia.
        # -----------------------------------------------------
        cursor.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'facturas'
              AND column_name = 'numero_factura'
        """)

        tipo_numero = cursor.fetchone()

        if tipo_numero and tipo_numero[0] not in (
            "bigint",
            "integer",
            "smallint",
        ):
            cursor.execute("""
                ALTER TABLE facturas
                ALTER COLUMN numero_factura DROP DEFAULT
            """)

            cursor.execute("""
                ALTER TABLE facturas
                ALTER COLUMN numero_factura DROP NOT NULL
            """)

            cursor.execute("""
                ALTER TABLE facturas
                ALTER COLUMN numero_factura TYPE BIGINT
                USING (
                    CASE
                        WHEN TRIM(numero_factura::TEXT)
                             ~ '^[0-9]+$'
                        THEN TRIM(numero_factura::TEXT)::BIGINT
                        ELSE NULL
                    END
                )
            """)

            cursor.execute("""
                WITH base AS (
                    SELECT
                        COALESCE(MAX(numero_factura), 0) AS max_num
                    FROM facturas
                ),
                faltantes AS (
                    SELECT
                        id,
                        (
                            base.max_num
                            + ROW_NUMBER() OVER (ORDER BY id)
                        )::BIGINT AS nuevo_numero
                    FROM facturas
                    CROSS JOIN base
                    WHERE numero_factura IS NULL
                )
                UPDATE facturas f
                SET numero_factura = faltantes.nuevo_numero
                FROM faltantes
                WHERE f.id = faltantes.id
            """)

            cursor.execute("""
                ALTER TABLE facturas
                ALTER COLUMN numero_factura SET NOT NULL
            """)

        # -----------------------------------------------------
        # ASEGURAR COLUMNAS DE FACTURAS EXISTENTES
        # -----------------------------------------------------
        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS fecha
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS usuario TEXT
        """)

        cursor.execute("""
            UPDATE facturas
            SET usuario = COALESCE(usuario, 'admin')
            WHERE usuario IS NULL
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ALTER COLUMN usuario SET NOT NULL
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS cliente_nombre TEXT
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS cliente_documento TEXT
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS cliente_telefono TEXT
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS cliente_email TEXT
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS metodo_pago TEXT
            DEFAULT 'Efectivo'
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS subtotal
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS descuento
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS impuesto
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS total
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS estado TEXT
            NOT NULL DEFAULT 'Pagada'
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS observaciones TEXT
        """)

        # Eliminar cualquier default antiguo incompatible
        # y colocar el correcto para la numeración.
        cursor.execute("""
            ALTER TABLE facturas
            ALTER COLUMN numero_factura DROP DEFAULT
        """)

        cursor.execute("""
            ALTER TABLE facturas
            ALTER COLUMN numero_factura
            SET DEFAULT nextval('factura_numero_seq')
        """)

        # -----------------------------------------------------
        # DETALLES DE FACTURA
        # -----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS factura_detalles (
                id SERIAL PRIMARY KEY,
                factura_id INTEGER NOT NULL,
                producto_id INTEGER,
                producto_nombre TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_compra DOUBLE PRECISION NOT NULL DEFAULT 0,
                precio_unitario DOUBLE PRECISION NOT NULL DEFAULT 0,
                descuento DOUBLE PRECISION NOT NULL DEFAULT 0,
                subtotal DOUBLE PRECISION NOT NULL DEFAULT 0,
                utilidad DOUBLE PRECISION NOT NULL DEFAULT 0,
                FOREIGN KEY (factura_id)
                    REFERENCES facturas(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (producto_id)
                    REFERENCES productos(id)
                    ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS producto_id INTEGER
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS producto_nombre TEXT
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS cantidad INTEGER
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS precio_compra
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS precio_unitario
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS descuento
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS subtotal
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE factura_detalles
            ADD COLUMN IF NOT EXISTS utilidad
            DOUBLE PRECISION NOT NULL DEFAULT 0
        """)

        # -----------------------------------------------------
        # ÍNDICES
        # -----------------------------------------------------
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_facturas_fecha
            ON facturas(fecha)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_facturas_usuario
            ON facturas(usuario)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_factura_detalles_factura
            ON factura_detalles(factura_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_factura_detalles_producto
            ON factura_detalles(producto_id)
        """)

        # -----------------------------------------------------
        # AJUSTAR SECUENCIA
        # -----------------------------------------------------
        cursor.execute("""
            SELECT COALESCE(MAX(numero_factura), 0)
            FROM facturas
        """)

        ultimo_numero = cursor.fetchone()[0] or 0

        if ultimo_numero > 0:
            cursor.execute("""
                SELECT setval(
                    'factura_numero_seq',
                    %s,
                    true
                )
            """, (ultimo_numero,))
        else:
            cursor.execute("""
                SELECT setval(
                    'factura_numero_seq',
                    1,
                    false
                )
            """)

        # -----------------------------------------------------
        # ADMINISTRADOR
        # -----------------------------------------------------
        cursor.execute("""
            SELECT id, password, rol
            FROM usuarios
            WHERE usuario = %s
        """, ("admin",))

        usuario_admin = cursor.fetchone()

        if usuario_admin is None:
            cursor.execute("""
                INSERT INTO usuarios (
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
                generate_password_hash("admin123"),
                "admin",
                "Hombre",
            ))
        else:
            cursor.execute("""
                UPDATE usuarios
                SET rol = 'admin'
                WHERE usuario = 'admin'
            """)

        migrate_old_passwords(cursor)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


# Crear / actualizar automáticamente las tablas.
init_db()


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/")
def index():
    if not requiere_login():
        return redirect(url_for("login"))

    busqueda = request.args.get("q", "").strip()

    filtro_stock = request.args.get(
        "stock",
        "todos",
    ).strip().lower()

    if filtro_stock not in (
        "todos",
        "stock",
        "bajo",
        "agotado",
    ):
        filtro_stock = "todos"

    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    condiciones = []
    parametros = []

    if busqueda:
        condiciones.append("""
            (
                CAST(p.id AS TEXT) ILIKE %s
                OR p.nombre ILIKE %s
                OR COALESCE(p.categoria, '') ILIKE %s
            )
        """)

        texto = f"%{busqueda}%"

        parametros.extend([
            texto,
            texto,
            texto,
        ])

    if filtro_stock == "stock":
        condiciones.append("p.existencias > 0")
    elif filtro_stock == "bajo":
        condiciones.append(
            "p.existencias BETWEEN 1 AND 5"
        )
    elif filtro_stock == "agotado":
        condiciones.append("p.existencias = 0")

    where_sql = ""

    if condiciones:
        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )

    cursor.execute(f"""
        SELECT
            p.id,
            p.nombre,
            p.categoria,
            p.precio,
            p.precio_compra,
            p.existencias,
            p.proveedor_id,
            pr.nombre AS proveedor_nombre
        FROM productos p
        LEFT JOIN proveedores pr
            ON p.proveedor_id = pr.id
        {where_sql}
        ORDER BY p.id DESC
    """, parametros)

    productos = cursor.fetchall()

    # IMPORTANTE:
    # Se devuelve m.fecha como fecha real de PostgreSQL,
    # no como texto, porque movimientos.html utiliza
    # .strftime().
    if busqueda or filtro_stock != "todos":
        ids_productos = [
            producto["id"]
            for producto in productos
        ]

        if ids_productos:
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
                INNER JOIN productos p
                    ON m.producto_id = p.id
                WHERE m.producto_id = ANY(%s)
                ORDER BY m.id DESC
                LIMIT 50
            """, (ids_productos,))

            movimientos = cursor.fetchall()
        else:
            movimientos = []
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
            LIMIT 50
        """)

        movimientos = cursor.fetchall()

    total_productos = len(productos)

    unidades_totales = sum(
        producto["existencias"]
        for producto in productos
    )

    valor_inventario = sum(
        float(producto["precio"] or 0)
        * producto["existencias"]
        for producto in productos
    )

    valor_inventario_costo = sum(
        float(producto["precio_compra"] or 0)
        * producto["existencias"]
        for producto in productos
    )

    valor_potencial_venta = sum(
        float(producto["precio"] or 0)
        * producto["existencias"]
        for producto in productos
    )

    utilidad_potencial = (
        valor_potencial_venta
        - valor_inventario_costo
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
        valor_inventario_costo=valor_inventario_costo,
        valor_potencial_venta=valor_potencial_venta,
        utilidad_potencial=utilidad_potencial,
        stock_bajo=stock_bajo,
        agotados=agotados,
        busqueda=busqueda,
        filtro_stock=filtro_stock,
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get(
            "usuario",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        if not usuario or not password:
            flash(
                "Debe ingresar usuario y contraseña.",
                "danger",
            )
            return render_template("login.html")

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
        """, (usuario,))

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(
            user["password"],
            password,
        ):
            session["usuario"] = user["usuario"]
            session["rol"] = user["rol"]
            session["genero"] = user["genero"]

            flash(
                "¡Inicio de sesión exitoso!",
                "success",
            )

            return redirect(url_for("index"))

        flash(
            "Usuario o contraseña incorrectos.",
            "danger",
        )

    return render_template("login.html")


# =========================================================
# REGISTRO DE USUARIOS
# =========================================================

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if not requiere_admin():
        return redirect(url_for("index"))

    if request.method == "POST":
        usuario = request.form.get(
            "usuario",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        genero = request.form.get(
            "genero",
            "",
        ).strip()

        rol = request.form.get(
            "rol",
            "",
        ).strip()

        if not usuario or not password:
            flash(
                "Debe ingresar usuario y contraseña.",
                "danger",
            )
            return render_template("registro.html")

        if genero not in ("Hombre", "Mujer"):
            flash(
                "Debe seleccionar Hombre o Mujer.",
                "danger",
            )
            return render_template("registro.html")

        if rol not in ("admin", "usuario"):
            flash(
                "Debe seleccionar un rol válido.",
                "danger",
            )
            return render_template("registro.html")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id
            FROM usuarios
            WHERE usuario = %s
        """, (usuario,))

        if cursor.fetchone():
            cursor.close()
            conn.close()

            flash(
                "Ese nombre de usuario ya existe.",
                "danger",
            )

            return render_template("registro.html")

        cursor.execute("""
            INSERT INTO usuarios (
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
            generate_password_hash(password),
            rol,
            genero,
        ))

        conn.commit()
        cursor.close()
        conn.close()

        flash(
            "Usuario registrado correctamente.",
            "success",
        )

        return redirect(url_for("index"))

    return render_template("registro.html")


# =========================================================
# CERRAR SESIÓN
# =========================================================

@app.route("/logout")
def logout():
    session.clear()

    flash(
        "Sesión cerrada correctamente.",
        "info",
    )

    return redirect(url_for("login"))


# =========================================================
# AGREGAR PRODUCTO
# =========================================================

@app.route("/agregar", methods=["GET", "POST"])
def agregar():
    if not requiere_admin():
        return redirect(url_for("index"))

    if request.method == "POST":
        nombre = request.form.get(
            "nombre",
            "",
        ).strip()

        categoria = request.form.get(
            "categoria",
            "",
        ).strip()

        try:
            precio = float(
                request.form.get("precio", 0)
            )

            precio_compra = float(
                request.form.get(
                    "precio_compra",
                    0,
                )
            )

            existencias = int(
                request.form.get(
                    "existencias",
                    0,
                )
            )
        except (TypeError, ValueError):
            flash(
                "Precio, precio de compra o existencias no tienen un valor válido.",
                "danger",
            )
            return render_template(
                "producto_form.html"
            )

        proveedor_id = request.form.get(
            "proveedor_id",
            "",
        ).strip()

        if proveedor_id:
            try:
                proveedor_id = int(proveedor_id)
            except ValueError:
                flash(
                    "El proveedor seleccionado no es válido.",
                    "danger",
                )
                return render_template(
                    "producto_form.html"
                )
        else:
            proveedor_id = None

        if not nombre:
            flash(
                "Debe ingresar el nombre del producto.",
                "danger",
            )
            return render_template(
                "producto_form.html"
            )

        if precio < 0:
            flash(
                "El precio de venta no puede ser negativo.",
                "danger",
            )
            return render_template(
                "producto_form.html"
            )

        if precio_compra < 0:
            flash(
                "El precio de compra no puede ser negativo.",
                "danger",
            )
            return render_template(
                "producto_form.html"
            )

        if existencias < 0:
            flash(
                "Las existencias no pueden ser negativas.",
                "danger",
            )
            return render_template(
                "producto_form.html"
            )

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO productos (
                    nombre,
                    categoria,
                    precio,
                    precio_compra,
                    existencias,
                    proveedor_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                nombre,
                categoria,
                precio,
                precio_compra,
                existencias,
                proveedor_id,
            ))

            producto_id = cursor.fetchone()[0]

            if existencias > 0:
                cursor.execute("""
                    INSERT INTO movimientos (
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
                    "Entrada",
                    existencias,
                    "Ajuste de inventario",
                    "",
                    "",
                    "Stock inicial del producto",
                    session.get(
                        "usuario",
                        "admin",
                    ),
                ))

            conn.commit()

            flash(
                "Producto agregado con éxito.",
                "success",
            )

        except Exception:
            conn.rollback()

            flash(
                "No fue posible agregar el producto.",
                "danger",
            )

            cursor.close()
            conn.close()

            return render_template(
                "producto_form.html"
            )

        cursor.close()
        conn.close()

        return redirect(url_for("index"))

    return render_template("producto_form.html")


# =========================================================
# EDITAR PRODUCTO
# =========================================================

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if not requiere_admin():
        return redirect(url_for("index"))

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    if request.method == "POST":
        nombre = request.form.get(
            "nombre",
            "",
        ).strip()

        categoria = request.form.get(
            "categoria",
            "",
        ).strip()

        try:
            precio = float(
                request.form.get(
                    "precio",
                    0,
                )
            )

            precio_compra = float(
                request.form.get(
                    "precio_compra",
                    0,
                )
            )

            existencias = int(
                request.form.get(
                    "existencias",
                    0,
                )
            )
        except (TypeError, ValueError):
            cursor.close()
            conn.close()

            flash(
                "Precio o existencias no válidos.",
                "danger",
            )

            return redirect(
                url_for(
                    "editar",
                    id=id,
                )
            )

        proveedor_id = request.form.get(
            "proveedor_id",
            "",
        ).strip()

        if proveedor_id:
            try:
                proveedor_id = int(
                    proveedor_id
                )
            except ValueError:
                proveedor_id = None
        else:
            proveedor_id = None

        if precio < 0 or precio_compra < 0:
            cursor.close()
            conn.close()

            flash(
                "Los precios no pueden ser negativos.",
                "danger",
            )

            return redirect(
                url_for(
                    "editar",
                    id=id,
                )
            )

        if existencias < 0:
            cursor.close()
            conn.close()

            flash(
                "Las existencias no pueden ser negativas.",
                "danger",
            )

            return redirect(
                url_for(
                    "editar",
                    id=id,
                )
            )

        cursor.execute("""
            UPDATE productos
            SET
                nombre = %s,
                categoria = %s,
                precio = %s,
                precio_compra = %s,
                existencias = %s,
                proveedor_id = %s
            WHERE id = %s
        """, (
            nombre,
            categoria,
            precio,
            precio_compra,
            existencias,
            proveedor_id,
            id,
        ))

        conn.commit()
        cursor.close()
        conn.close()

        flash(
            "Producto actualizado.",
            "success",
        )

        return redirect(url_for("index"))

    cursor.execute("""
        SELECT
            p.*,
            pr.nombre AS proveedor_nombre
        FROM productos p
        LEFT JOIN proveedores pr
            ON p.proveedor_id = pr.id
        WHERE p.id = %s
    """, (id,))

    producto = cursor.fetchone()

    cursor.close()
    conn.close()

    if producto is None:
        flash(
            "Producto no encontrado.",
            "danger",
        )
        return redirect(url_for("index"))

    return render_template(
        "producto_form.html",
        producto=producto,
    )


# =========================================================
# ELIMINAR PRODUCTO
# =========================================================

@app.route("/eliminar/<int:id>")
def eliminar(id):
    if not requiere_admin():
        return redirect(url_for("index"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM movimientos
        WHERE producto_id = %s
    """, (id,))

    cursor.execute("""
        DELETE FROM productos
        WHERE id = %s
    """, (id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Producto eliminado.",
        "warning",
    )

    return redirect(url_for("index"))


# =========================================================
# MOVIMIENTOS
# =========================================================

@app.route("/movimientos", methods=["GET", "POST"])
def movimientos():
    if not requiere_login():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    if request.method == "POST":
        try:
            producto_id = int(
                request.form.get("producto_id")
            )

            cantidad = int(
                request.form.get("cantidad")
            )
        except (TypeError, ValueError):
            cursor.close()
            conn.close()

            flash(
                "Cantidad o producto no válidos.",
                "danger",
            )

            return redirect(
                url_for("movimientos")
            )

        tipo = request.form.get(
            "tipo",
            "",
        ).strip()

        motivo = request.form.get(
            "motivo",
            "",
        ).strip()

        factura = request.form.get(
            "factura",
            "",
        ).strip()

        orden_compra = request.form.get(
            "orden_compra",
            "",
        ).strip()

        comentarios = request.form.get(
            "comentarios",
            "",
        ).strip()

        usuario = session.get(
            "usuario",
            "admin",
        )

        cursor.execute("""
            SELECT existencias
            FROM productos
            WHERE id = %s
        """, (producto_id,))

        producto = cursor.fetchone()

        if producto is None:
            flash(
                "El producto no existe.",
                "danger",
            )

        elif cantidad <= 0:
            flash(
                "La cantidad debe ser mayor que cero.",
                "danger",
            )

        elif (
            tipo == "Salida"
            and cantidad > producto["existencias"]
        ):
            flash(
                f"No hay suficiente stock. Disponible: {producto['existencias']}",
                "danger",
            )

        elif tipo not in ("Entrada", "Salida"):
            flash(
                "Tipo de movimiento no válido.",
                "danger",
            )

        elif motivo not in (
            "Compra",
            "Venta",
            "Devolución de cliente",
            "Devolución a proveedor",
            "Ajuste de inventario",
            "Otro",
        ):
            flash(
                "Debe seleccionar un motivo válido.",
                "danger",
            )

        elif (
            motivo in (
                "Devolución de cliente",
                "Devolución a proveedor",
            )
            and not comentarios
        ):
            flash(
                "En una devolución debe indicar el motivo o explicación en comentarios.",
                "danger",
            )

        else:
            stock_actual = producto["existencias"]

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
                producto_id,
            ))

            cursor.execute("""
                INSERT INTO movimientos (
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
                usuario,
            ))

            conn.commit()

            flash(
                "Movimiento registrado correctamente.",
                "success",
            )

    cursor.execute("""
        SELECT
            id,
            nombre,
            categoria,
            precio,
            precio_compra,
            existencias
        FROM productos
        ORDER BY nombre
    """)

    productos = cursor.fetchall()

    # IMPORTANTE:
    # No usamos TO_CHAR() aquí. movimientos.html llama
    # a mov['fecha'].strftime(), por lo que fecha debe llegar
    # como datetime de PostgreSQL.
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
        movimientos=lista_movimientos,
    )


# =========================================================
# PROVEEDORES
# =========================================================

@app.route("/proveedores", methods=["GET", "POST"])
def proveedores():
    if not requiere_login():
        return redirect(url_for("login"))

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
                "danger",
            )

            return redirect(
                url_for("proveedores")
            )

        nombre = request.form.get(
            "nombre",
            "",
        ).strip()

        contacto = request.form.get(
            "contacto",
            "",
        ).strip()

        telefono = request.form.get(
            "telefono",
            "",
        ).strip()

        email = request.form.get(
            "email",
            "",
        ).strip()

        if not nombre:
            cursor.close()
            conn.close()

            flash(
                "Debe ingresar el nombre del proveedor.",
                "danger",
            )

            return redirect(
                url_for("proveedores")
            )

        cursor.execute("""
            INSERT INTO proveedores (
                nombre,
                contacto,
                telefono,
                email
            )
            VALUES (%s, %s, %s, %s)
        """, (
            nombre,
            contacto,
            telefono,
            email,
        ))

        conn.commit()

        flash(
            "Proveedor agregado.",
            "success",
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
        proveedores=provs,
    )


# =========================================================
# API - PRODUCTOS
# =========================================================

@app.route("/api/productos", methods=["GET"])
def api_productos():
    if not requiere_login():
        return jsonify({
            "error": "No autorizado",
        }), 401

    busqueda = request.args.get(
        "q",
        "",
    ).strip()

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    if busqueda:
        texto = f"%{busqueda}%"

        cursor.execute("""
            SELECT
                p.id,
                p.nombre,
                p.categoria,
                p.precio,
                p.precio_compra,
                p.existencias,
                p.proveedor_id,
                pr.nombre AS proveedor_nombre
            FROM productos p
            LEFT JOIN proveedores pr
                ON p.proveedor_id = pr.id
            WHERE
                CAST(p.id AS TEXT) ILIKE %s
                OR p.nombre ILIKE %s
                OR COALESCE(p.categoria, '') ILIKE %s
            ORDER BY p.nombre
            LIMIT 50
        """, (
            texto,
            texto,
            texto,
        ))
    else:
        cursor.execute("""
            SELECT
                p.id,
                p.nombre,
                p.categoria,
                p.precio,
                p.precio_compra,
                p.existencias,
                p.proveedor_id,
                pr.nombre AS proveedor_nombre
            FROM productos p
            LEFT JOIN proveedores pr
                ON p.proveedor_id = pr.id
            ORDER BY p.nombre
            LIMIT 100
        """)

    productos = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        "productos": productos,
    })


# =========================================================
# API - PRODUCTO INDIVIDUAL
# =========================================================

@app.route("/api/productos/<int:id>", methods=["GET"])
def api_producto(id):
    if not requiere_login():
        return jsonify({
            "error": "No autorizado",
        }), 401

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cursor.execute("""
        SELECT
            p.id,
            p.nombre,
            p.categoria,
            p.precio,
            p.precio_compra,
            p.existencias,
            p.proveedor_id,
            pr.nombre AS proveedor_nombre
        FROM productos p
        LEFT JOIN proveedores pr
            ON p.proveedor_id = pr.id
        WHERE p.id = %s
    """, (id,))

    producto = cursor.fetchone()

    cursor.close()
    conn.close()

    if producto is None:
        return jsonify({
            "error": "Producto no encontrado",
        }), 404

    return jsonify(producto)


# =========================================================
# API - DASHBOARD
# =========================================================

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    if not requiere_login():
        return jsonify({
            "error": "No autorizado",
        }), 401

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cursor.execute("""
        SELECT
            COUNT(*) AS total_productos,
            COALESCE(SUM(existencias), 0)
                AS unidades_totales,
            COALESCE(
                SUM(existencias * precio_compra),
                0
            ) AS inventario_costo,
            COALESCE(
                SUM(existencias * precio),
                0
            ) AS inventario_venta,
            COALESCE(
                SUM(
                    existencias
                    * (precio - precio_compra)
                ),
                0
            ) AS utilidad_potencial,
            COUNT(
                CASE
                    WHEN existencias BETWEEN 1 AND 5
                    THEN 1
                END
            ) AS stock_bajo,
            COUNT(
                CASE
                    WHEN existencias = 0
                    THEN 1
                END
            ) AS agotados
        FROM productos
    """)

    inventario = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(*) AS cantidad_facturas,
            COALESCE(SUM(total), 0)
                AS total_ventas
        FROM facturas
        WHERE
            fecha::date = CURRENT_DATE
            AND estado <> 'Anulada'
    """)

    ventas_dia = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(*) AS cantidad_facturas,
            COALESCE(SUM(total), 0)
                AS total_ventas
        FROM facturas
        WHERE
            DATE_TRUNC('month', fecha)
            =
            DATE_TRUNC('month', CURRENT_TIMESTAMP)
            AND estado <> 'Anulada'
    """)

    ventas_mes = cursor.fetchone()

    cursor.execute("""
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN m.tipo = 'Entrada'
                        AND m.motivo = 'Compra'
                        THEN
                            m.cantidad
                            * COALESCE(
                                p.precio_compra,
                                0
                            )
                        ELSE 0
                    END
                ),
                0
            ) AS compras_mes
        FROM movimientos m
        LEFT JOIN productos p
            ON m.producto_id = p.id
        WHERE
            DATE_TRUNC('month', m.fecha)
            =
            DATE_TRUNC('month', CURRENT_TIMESTAMP)
    """)

    compras_mes = cursor.fetchone()

    cursor.execute("""
        SELECT
            fd.producto_id,
            fd.producto_nombre,
            COALESCE(SUM(fd.cantidad), 0)
                AS unidades_vendidas,
            COALESCE(SUM(fd.subtotal), 0)
                AS ventas,
            COALESCE(SUM(fd.utilidad), 0)
                AS utilidad
        FROM factura_detalles fd
        INNER JOIN facturas f
            ON fd.factura_id = f.id
        WHERE f.estado <> 'Anulada'
        GROUP BY
            fd.producto_id,
            fd.producto_nombre
        ORDER BY unidades_vendidas DESC
        LIMIT 10
    """)

    productos_mas_vendidos = cursor.fetchall()

    cursor.execute("""
        SELECT
            COALESCE(
                p.categoria,
                'Sin categoría'
            ) AS categoria,
            COALESCE(SUM(fd.subtotal), 0)
                AS ventas,
            COALESCE(SUM(fd.utilidad), 0)
                AS utilidad
        FROM factura_detalles fd
        INNER JOIN facturas f
            ON fd.factura_id = f.id
        LEFT JOIN productos p
            ON fd.producto_id = p.id
        WHERE f.estado <> 'Anulada'
        GROUP BY p.categoria
        ORDER BY utilidad DESC
        LIMIT 10
    """)

    categorias_rentables = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        "inventario": inventario,
        "ventas_dia": ventas_dia,
        "ventas_mes": ventas_mes,
        "compras_mes": compras_mes,
        "productos_mas_vendidos": productos_mas_vendidos,
        "categorias_mas_rentables": categorias_rentables,
    })


# =========================================================
# API - CONSULTAR FACTURA
# =========================================================

@app.route("/api/facturas/<int:id>", methods=["GET"])
def api_factura(id):
    if not requiere_login():
        return jsonify({
            "error": "No autorizado",
        }), 401

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM facturas
        WHERE id = %s
    """, (id,))

    factura = cursor.fetchone()

    if factura is None:
        cursor.close()
        conn.close()

        return jsonify({
            "error": "Factura no encontrada",
        }), 404

    cursor.execute("""
        SELECT *
        FROM factura_detalles
        WHERE factura_id = %s
        ORDER BY id
    """, (id,))

    detalles = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        "factura": factura,
        "detalles": detalles,
    })


# =========================================================
# API - LISTAR FACTURAS
# =========================================================

@app.route("/api/facturas", methods=["GET"])
def api_facturas():
    if not requiere_login():
        return jsonify({
            "error": "No autorizado",
        }), 401

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    limite = request.args.get(
        "limite",
        "100",
    )

    try:
        limite = int(limite)
    except (TypeError, ValueError):
        limite = 100

    limite = max(
        1,
        min(limite, 500),
    )

    cursor.execute("""
        SELECT
            id,
            numero_factura,
            fecha,
            usuario,
            cliente_nombre,
            cliente_documento,
            metodo_pago,
            subtotal,
            descuento,
            impuesto,
            total,
            estado
        FROM facturas
        ORDER BY id DESC
        LIMIT %s
    """, (limite,))

    facturas = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        "facturas": facturas,
    })


# =========================================================
# EXPORTAR FACTURAS
# =========================================================

@app.route("/exportar_facturas")
def exportar_facturas():
    if not requiere_admin():
        return redirect(url_for("index"))

    conn = get_db()

    df = pd.read_sql_query("""
        SELECT
            f.numero_factura,
            f.fecha,
            f.usuario,
            f.cliente_nombre,
            f.cliente_documento,
            f.cliente_telefono,
            f.cliente_email,
            f.metodo_pago,
            f.subtotal,
            f.descuento,
            f.impuesto,
            f.total,
            f.estado,
            f.observaciones
        FROM facturas f
        ORDER BY f.id DESC
    """, conn)

    conn.close()

    csv_path = "facturas_export.csv"

    df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    return send_file(
        csv_path,
        as_attachment=True,
        download_name="facturas_export.csv",
        mimetype="text/csv",
    )


# =========================================================
# EXPORTAR INVENTARIO
# =========================================================

@app.route("/exportar")
def exportar():
    if not requiere_admin():
        return redirect(url_for("index"))

    conn = get_db()

    df = pd.read_sql_query("""
        SELECT
            p.id,
            p.nombre,
            p.categoria,
            p.precio_compra,
            p.precio,
            p.existencias,
            COALESCE(
                p.existencias * p.precio_compra,
                0
            ) AS valor_inventario_costo,
            COALESCE(
                p.existencias * p.precio,
                0
            ) AS valor_inventario_venta,
            COALESCE(
                p.existencias
                * (p.precio - p.precio_compra),
                0
            ) AS utilidad_potencial,
            pr.nombre AS proveedor
        FROM productos p
        LEFT JOIN proveedores pr
            ON p.proveedor_id = pr.id
        ORDER BY p.id
    """, conn)

    conn.close()

    csv_path = "inventario_export.csv"

    df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    return send_file(
        csv_path,
        as_attachment=True,
        download_name="inventario_export.csv",
        mimetype="text/csv",
    )


# =========================================================
# GRÁFICO
# =========================================================

@app.route("/grafico")
def grafico():
    if not requiere_login():
        return redirect(url_for("login"))

    conn = get_db()

    df = pd.read_sql_query("""
        SELECT
            nombre,
            existencias
        FROM productos
        ORDER BY existencias DESC
    """, conn)

    conn.close()

    if df.empty:
        flash(
            "No hay datos para generar el gráfico.",
            "warning",
        )

        return redirect(url_for("index"))

    plt.figure(figsize=(8, 4))

    plt.bar(
        df["nombre"],
        df["existencias"],
    )

    plt.xlabel("Productos")
    plt.ylabel("Existencias")
    plt.title("Stock Actual por Producto")

    plt.xticks(
        rotation=45,
        ha="right",
    )

    plt.tight_layout()

    os.makedirs(
        "static",
        exist_ok=True,
    )

    img_path = "static/grafico.png"

    plt.savefig(img_path)
    plt.close()

    return send_file(
        img_path,
        mimetype="image/png",
    )


# =========================================================
# EJECUTAR APLICACIÓN
# =========================================================

# =========================================================
# FACTURACIÓN
# =========================================================

@app.route("/facturacion", methods=["GET"])
def facturacion():
    if not requiere_login():
        return redirect(url_for("login"))

    return render_template("facturacion.html")


# =========================================================
# CREAR FACTURA
# =========================================================

@app.route("/api/facturas/crear", methods=["POST"])
def crear_factura():

    if not requiere_login():
        return jsonify({
            "error": "No autorizado"
        }), 401

    datos = request.get_json(silent=True)

    if not datos:
        return jsonify({
            "error": "No se recibieron datos de la factura."
        }), 400

    detalles = datos.get("detalles", [])

    if not detalles:
        return jsonify({
            "error": "La factura debe contener al menos un producto."
        }), 400

    try:

        descuento_factura = float(
            datos.get("descuento", 0) or 0
        )

        impuesto = float(
            datos.get("impuesto", 0) or 0
        )

    except (TypeError, ValueError):

        return jsonify({
            "error": "Descuento o impuesto no válidos."
        }), 400

    if descuento_factura < 0:
        return jsonify({
            "error": "El descuento no puede ser negativo."
        }), 400

    if impuesto < 0:
        return jsonify({
            "error": "El impuesto no puede ser negativo."
        }), 400

    conn = get_db()
    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    try:

        # -------------------------------------------------
        # VALIDAR PRODUCTOS Y CALCULAR TOTALES
        # -------------------------------------------------

        subtotal = 0
        detalles_validos = []

        for detalle in detalles:

            try:
                producto_id = int(
                    detalle.get("producto_id")
                )

                cantidad = int(
                    detalle.get("cantidad")
                )

                precio_unitario = float(
                    detalle.get("precio_unitario", 0)
                )

                descuento_producto = float(
                    detalle.get("descuento", 0) or 0
                )

            except (TypeError, ValueError):

                raise ValueError(
                    "Uno de los productos de la factura contiene datos inválidos."
                )

            if cantidad <= 0:

                raise ValueError(
                    "La cantidad debe ser mayor que cero."
                )

            if descuento_producto < 0:

                raise ValueError(
                    "El descuento de un producto no puede ser negativo."
                )

            # Bloqueamos el producto para evitar
            # ventas simultáneas sobre el mismo stock.
            cursor.execute("""
                SELECT
                    id,
                    nombre,
                    precio,
                    precio_compra,
                    existencias
                FROM productos
                WHERE id = %s
                FOR UPDATE
            """, (producto_id,))

            producto = cursor.fetchone()

            if producto is None:

                raise ValueError(
                    f"El producto con ID {producto_id} no existe."
                )

            if cantidad > producto["existencias"]:

                raise ValueError(
                    "No hay suficiente stock para el producto: "
                    + producto["nombre"]
                    + ". Disponible: "
                    + str(producto["existencias"])
                )

            # Usamos el precio almacenado en la BD.
            # Así evitamos que el navegador pueda
            # manipular el precio de venta.
            precio_real = float(
                producto["precio"] or 0
            )

            precio_compra_real = float(
                producto["precio_compra"] or 0
            )

            subtotal_producto = (
                cantidad * precio_real
            ) - descuento_producto

            if subtotal_producto < 0:

                raise ValueError(
                    "El descuento no puede superar el valor del producto."
                )

            subtotal += subtotal_producto

            detalles_validos.append({
                "producto_id": producto["id"],
                "producto_nombre": producto["nombre"],
                "cantidad": cantidad,
                "precio_compra": precio_compra_real,
                "precio_unitario": precio_real,
                "descuento": descuento_producto,
                "subtotal": subtotal_producto,
                "utilidad": (
                    subtotal_producto
                    - (
                        cantidad
                        * precio_compra_real
                    )
                )
            })

        # -------------------------------------------------
        # DESCUENTO GENERAL
        # -------------------------------------------------

        if descuento_factura > subtotal:

            raise ValueError(
                "El descuento general no puede superar el subtotal."
            )

        total = (
            subtotal
            - descuento_factura
            + impuesto
        )

        if total < 0:

            raise ValueError(
                "El total de la factura no puede ser negativo."
            )

        # -------------------------------------------------
        # CREAR FACTURA
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO facturas (
                usuario,
                cliente_nombre,
                cliente_documento,
                cliente_telefono,
                cliente_email,
                metodo_pago,
                subtotal,
                descuento,
                impuesto,
                total,
                estado,
                observaciones
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'Pagada',
                %s
            )
            RETURNING
                id,
                numero_factura
        """, (
            session.get("usuario", "admin"),
            datos.get("cliente_nombre", "").strip(),
            datos.get("cliente_documento", "").strip(),
            datos.get("cliente_telefono", "").strip(),
            datos.get("cliente_email", "").strip(),
            datos.get("metodo_pago", "Efectivo"),
            subtotal,
            descuento_factura,
            impuesto,
            total,
            datos.get("observaciones", "").strip(),
        ))

        factura = cursor.fetchone()

        factura_id = factura["id"]
        numero_factura = factura["numero_factura"]

        # -------------------------------------------------
        # GUARDAR DETALLES Y DESCONTAR INVENTARIO
        # -------------------------------------------------

        for detalle in detalles_validos:

            cursor.execute("""
                INSERT INTO factura_detalles (
                    factura_id,
                    producto_id,
                    producto_nombre,
                    cantidad,
                    precio_compra,
                    precio_unitario,
                    descuento,
                    subtotal,
                    utilidad
                )
                VALUES (
                    %s,
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
                factura_id,
                detalle["producto_id"],
                detalle["producto_nombre"],
                detalle["cantidad"],
                detalle["precio_compra"],
                detalle["precio_unitario"],
                detalle["descuento"],
                detalle["subtotal"],
                detalle["utilidad"],
            ))

            # Descontar inventario
            cursor.execute("""
                UPDATE productos
                SET existencias = existencias - %s
                WHERE id = %s
            """, (
                detalle["cantidad"],
                detalle["producto_id"],
            ))

            # Registrar movimiento
            cursor.execute("""
                INSERT INTO movimientos (
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
                    'Salida',
                    %s,
                    'Venta',
                    %s,
                    '',
                    %s,
                    %s
                )
            """, (
                detalle["producto_id"],
                detalle["cantidad"],
                str(numero_factura),
                "Venta realizada mediante factura",
                session.get("usuario", "admin"),
            ))

        # -------------------------------------------------
        # CONFIRMAR TODO
        # -------------------------------------------------

        conn.commit()

        return jsonify({
            "ok": True,
            "id": factura_id,
            "numero_factura": numero_factura,
            "subtotal": subtotal,
            "descuento": descuento_factura,
            "impuesto": impuesto,
            "total": total,
        }), 201

    except ValueError as error:

        conn.rollback()

        return jsonify({
            "error": str(error)
        }), 400

    except Exception as error:

        conn.rollback()

        print(
            "ERROR CREANDO FACTURA:",
            error
        )

        return jsonify({
            "error": "No fue posible crear la factura."
        }), 500

    finally:

        cursor.close()
        conn.close()

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
