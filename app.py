from flask import Flask, render_template, request, redirect, session, send_from_directory
import psycopg2
import psycopg2.extras
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_key"

DATABASE_URL = "postgresql://gestor_academico_db_ln6m_user:5446xA5IUK9hWzwibZ7obDBTvugi3oir@dpg-d7fvq7471suc73a91t9g-a.oregon-postgres.render.com/gestor_academico_db_ln6m"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ======================
# SERVIR ARCHIVOS
# ======================
@app.route("/uploads/<filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ======================
# DB CONNECTION
# ======================
def get_db():
    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )
    conn.autocommit = False
    return conn


# ======================
# INIT DB
# ======================
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        nombre TEXT,
        email TEXT UNIQUE,
        password TEXT,
        rol TEXT,
        estado TEXT DEFAULT 'pendiente'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pdfs (
        id SERIAL PRIMARY KEY,
        profesor_id INTEGER,
        nombre TEXT,
        archivo TEXT,
        carrera TEXT,
        materia TEXT,
        observaciones TEXT,
        fecha TEXT,
        fecha_creacion TEXT,
        fecha_edicion TEXT,
        creado_por TEXT,
        editado_por TEXT
    )
    """)

    conn.commit()
    conn.close()


# ======================
# CREAR ADMINS
# ======================
def crear_admins():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT email FROM usuarios WHERE rol='admin'")
    admins = cur.fetchall()

    emails = [a["email"] for a in admins]

    if "admin@admin.com" not in emails:
        cur.execute("""
        INSERT INTO usuarios (nombre,email,password,rol,estado)
        VALUES (%s,%s,%s,%s,%s)
        """, (
            "Administrador",
            "admin@admin.com",
            generate_password_hash("admin123"),
            "admin",
            "aprobado"
        ))

    if "jefe@admin.com" not in emails:
        cur.execute("""
        INSERT INTO usuarios (nombre,email,password,rol,estado)
        VALUES (%s,%s,%s,%s,%s)
        """, (
            "Jefe de Carrera",
            "jefe@admin.com",
            generate_password_hash("admin123"),
            "admin",
            "aprobado"
        ))

    conn.commit()
    conn.close()


init_db()
crear_admins()


# ======================
# LOGIN
# ======================
@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM usuarios WHERE email=%s", (request.form["email"],))
        user = cur.fetchone()

        conn.close()

        if not user:
            return render_template("login.html", error="Usuario no encontrado")

        if not check_password_hash(user["password"], request.form["password"]):
            return render_template("login.html", error="Contraseña incorrecta")

        if user["rol"] != "admin" and user["estado"] != "aprobado":
            return render_template("login.html", error="Cuenta no aprobada")

        session["user_id"] = user["id"]
        session["nombre"] = user["nombre"]
        session["rol"] = user["rol"]

        return redirect("/admin" if user["rol"] == "admin" else "/dashboard")

    return render_template("login.html")


# ======================
# REGISTER
# ======================
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
            INSERT INTO usuarios (nombre,email,password,rol,estado)
            VALUES (%s,%s,%s,%s,%s)
            """, (
                request.form["nombre"],
                request.form["email"],
                generate_password_hash(request.form["password"]),
                "profesor",
                "pendiente"
            ))

            conn.commit()

        except:
            conn.close()
            return "Email ya registrado"

        conn.close()
        return redirect("/")

    return render_template("register.html")


# ======================
# LOGOUT
# ======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ======================
# ADMIN
# ======================
@app.route("/admin")
def admin():

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM usuarios WHERE rol='profesor' ORDER BY estado")
    usuarios = cur.fetchall()

    cur.execute("""
        SELECT pdfs.*, usuarios.nombre AS profesor_nombre
        FROM pdfs
        LEFT JOIN usuarios ON usuarios.id = pdfs.profesor_id
        ORDER BY pdfs.fecha DESC
    """)
    archivos = cur.fetchall()

    conn.close()

    return render_template("admin.html",
        usuarios=usuarios,
        archivos=archivos
    )

# ======================
# USUARIOS
# ======================
@app.route("/usuarios")
def usuarios():

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ✔ AHORA MUESTRA TODOS LOS USUARIOS (no solo pendientes)
    cur.execute("""
        SELECT * FROM usuarios
        ORDER BY rol, estado, nombre
    """)

    usuarios = cur.fetchall()
    conn.close()

    return render_template("usuarios.html", usuarios=usuarios)


# ======================
# APROBAR / RECHAZAR
# ======================
@app.route("/aprobar/<int:id>")
def aprobar(id):

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE usuarios SET estado=%s WHERE id=%s",
        ("aprobado", id)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/rechazar/<int:id>")
def rechazar(id):

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE usuarios SET estado=%s WHERE id=%s",
        ("rechazado", id)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


# ======================
# ELIMINAR USUARIO
# ======================
@app.route("/eliminar_usuario/<int:id>")
def eliminar_usuario(id):

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # obtener usuario
    cur.execute("SELECT rol FROM usuarios WHERE id=%s", (id,))
    user = cur.fetchone()

    # protección admin
    if user and user["rol"] == "admin":
        conn.close()
        return redirect("/usuarios")

    # borrar PDFs del profesor
    cur.execute("DELETE FROM pdfs WHERE profesor_id=%s", (id,))

    # borrar usuario
    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect("/usuarios")

# ======================
# DASHBOARD
# ======================
@app.route("/dashboard")
def dashboard():

    if session.get("rol") != "profesor":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM pdfs WHERE profesor_id=%s ORDER BY fecha DESC",
                (session["user_id"],))

    archivos = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", archivos=archivos)


# ======================
# PERFIL
# ======================
@app.route("/perfil", methods=["GET","POST"])
def perfil():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        cur.execute("""
        UPDATE usuarios SET nombre=%s, email=%s WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["email"],
            session["user_id"]
        ))
        conn.commit()
        session["nombre"] = request.form["nombre"]

    cur.execute("SELECT * FROM usuarios WHERE id=%s", (session["user_id"],))
    user = cur.fetchone()

    conn.close()

    return render_template("perfil.html", user=user)


# ======================
# PASSWORD
# ======================
@app.route("/password", methods=["POST"])
def password():

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT password FROM usuarios WHERE id=%s", (session["user_id"],))
    user = cur.fetchone()

    if not check_password_hash(user["password"], request.form["actual"]):
        return redirect("/perfil")

    cur.execute("""
    UPDATE usuarios SET password=%s WHERE id=%s
    """, (
        generate_password_hash(request.form["nueva"]),
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/perfil")


# ======================
# SUBIR PDF
# ======================
@app.route("/subir_pdf", methods=["POST"])
def subir_pdf():

    file = request.files["pdf"]

    original = secure_filename(file.filename)
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original}"

    file.save(os.path.join(UPLOAD_FOLDER, filename))

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO pdfs (
        profesor_id,nombre,archivo,
        carrera,materia,observaciones,
        fecha,fecha_creacion,creado_por
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session["user_id"],
        original,
        filename,
        request.form.get("carrera"),
        request.form.get("materia"),
        request.form.get("observaciones"),
        fecha,
        fecha,
        session["nombre"]
    ))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ======================
# ELIMINAR PDF ADMIN
# ======================
@app.route("/eliminar_pdf_admin/<int:id>")
def eliminar_pdf_admin(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT archivo FROM pdfs WHERE id=%s", (id,))
    pdf = cur.fetchone()

    if pdf and pdf[0]:
        path = os.path.join(UPLOAD_FOLDER, pdf[0])
        if os.path.exists(path):
            os.remove(path)

    cur.execute("DELETE FROM pdfs WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect("/admin")


# ======================
# EDITAR PDF
# ======================
@app.route("/editar_pdf/<int:id>", methods=["GET","POST"])
def editar_pdf(id):

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM pdfs WHERE id=%s", (id,))
    pdf = cur.fetchone()

    if request.method == "POST":

        archivo = pdf["archivo"]

        file = request.files.get("pdf")

        if file and file.filename:
            original = secure_filename(file.filename)
            archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original}"
            file.save(os.path.join(UPLOAD_FOLDER, archivo))

        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

        cur.execute("""
        UPDATE pdfs SET
        carrera=%s,materia=%s,observaciones=%s,
        archivo=%s,fecha=%s,fecha_edicion=%s,editado_por=%s
        WHERE id=%s
        """, (
            request.form["carrera"],
            request.form["materia"],
            request.form["observaciones"],
            archivo,
            fecha,
            fecha,
            session["nombre"],
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/admin" if session["rol"] == "admin" else "/dashboard")

    conn.close()
    return render_template("editar_pdf.html", pdf=pdf)


if __name__ == "__main__":
    app.run(debug=True)