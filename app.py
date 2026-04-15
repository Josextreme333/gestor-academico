from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_key"

DB = "database.db"
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
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ======================
# INIT DB
# ======================
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        email TEXT UNIQUE,
        password TEXT,
        rol TEXT,
        estado TEXT DEFAULT 'pendiente'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pdfs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profesor_id INTEGER,
        nombre TEXT,
        archivo TEXT,
        carrera TEXT,
        materia TEXT,
        observaciones TEXT,
        fecha TEXT
    )
    """)

    # columnas nuevas
    try:
        cur.execute("ALTER TABLE pdfs ADD COLUMN fecha_creacion TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE pdfs ADD COLUMN fecha_edicion TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE pdfs ADD COLUMN creado_por TEXT")
    except:
        pass

    try:
        cur.execute("ALTER TABLE pdfs ADD COLUMN editado_por TEXT")
    except:
        pass

    conn.commit()
    conn.close()

# ======================
# CREAR 2 ADMINS FIJOS
# ======================
def crear_admins():

    conn = get_db()

    admins = conn.execute(
        "SELECT email FROM usuarios WHERE rol='admin'"
    ).fetchall()

    emails = [a["email"] for a in admins]

    if "admin@admin.com" not in emails:
        conn.execute("""
        INSERT INTO usuarios (nombre,email,password,rol,estado)
        VALUES (?,?,?,?,?)
        """,(
            "Administrador",
            "admin@admin.com",
            generate_password_hash("admin123"),
            "admin",
            "aprobado"
        ))

    if "jefe@admin.com" not in emails:
        conn.execute("""
        INSERT INTO usuarios (nombre,email,password,rol,estado)
        VALUES (?,?,?,?,?)
        """,(
            "Jefe de Carrera",
            "jefe@admin.com",
            generate_password_hash("admin123"),
            "admin",
            "aprobado"
        ))

    conn.commit()
    conn.close()

#======================
init_db()
crear_admins()

# ======================
# LOGIN
# ======================
@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        if not user:
            return render_template("login.html", error="Usuario no encontrado")

        if not check_password_hash(user["password"], password):
            return render_template("login.html", error="Contraseña incorrecta")

        if user["rol"] != "admin" and user["estado"] != "aprobado":
            return render_template("login.html", error="Cuenta no aprobada")

        session["user_id"] = user["id"]
        session["nombre"] = user["nombre"]
        session["rol"] = user["rol"]

        if user["rol"] == "admin":
            return redirect("/admin")

        return redirect("/dashboard")

    return render_template("login.html")


# ======================
# REGISTER
# ======================
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        nombre = request.form["nombre"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()

        try:
            conn.execute("""
            INSERT INTO usuarios (nombre,email,password,rol,estado)
            VALUES (?,?,?,?,?)
            """,(
                nombre,
                email,
                password,
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

    usuarios = conn.execute("""
        SELECT * FROM usuarios
        WHERE rol='profesor'
        ORDER BY estado
    """).fetchall()

    archivos = conn.execute("""
        SELECT 
            pdfs.*,
            usuarios.nombre AS profesor_nombre
        FROM pdfs
        LEFT JOIN usuarios 
        ON usuarios.id = pdfs.profesor_id
        ORDER BY pdfs.fecha DESC
    """).fetchall()

    conn.close()

    return render_template("admin.html",
        usuarios=usuarios,
        archivos=archivos
    )


# ======================
# APROBAR
# ======================
@app.route("/aprobar/<int:id>")
def aprobar(id):

    conn = get_db()
    conn.execute(
        "UPDATE usuarios SET estado='aprobado' WHERE id=?",
        (id,)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


# ======================
# RECHAZAR
# ======================
@app.route("/rechazar/<int:id>")
def rechazar(id):

    conn = get_db()
    conn.execute(
        "UPDATE usuarios SET estado='rechazado' WHERE id=?",
        (id,)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


# ======================
# ELIMINAR USUARIO
# ======================
@app.route("/eliminar/<int:id>")
def eliminar(id):

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()

    user = conn.execute(
        "SELECT rol FROM usuarios WHERE id=?",
        (id,)
    ).fetchone()

    # no borrar admins
    if user and user["rol"] == "admin":
        conn.close()
        return redirect("/usuarios")

    # borrar pdfs del profesor
    conn.execute(
        "DELETE FROM pdfs WHERE profesor_id=?",
        (id,)
    )

    # borrar usuario
    conn.execute(
        "DELETE FROM usuarios WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/usuarios")


# ======================
# ALIAS ELIMINAR (para HTML)
# ======================
@app.route("/eliminar_usuario/<int:id>")
def eliminar_usuario(id):
    return eliminar(id)


# ======================
# USUARIOS
# ======================
@app.route("/usuarios")
def usuarios():

    if session.get("rol") != "admin":
        return redirect("/")

    conn = get_db()

    usuarios = conn.execute("""
        SELECT * FROM usuarios
        WHERE estado='aprobado'
        ORDER BY nombre
    """).fetchall()

    conn.close()

    return render_template("usuarios.html", usuarios=usuarios)


# ======================
# DASHBOARD
# ======================
@app.route("/dashboard")
def dashboard():

    if session.get("rol") != "profesor":
        return redirect("/")

    conn = get_db()

    archivos = conn.execute("""
        SELECT * FROM pdfs
        WHERE profesor_id=?
        ORDER BY fecha DESC
    """,(session["user_id"],)).fetchall()

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

    if request.method == "POST":

        nombre = request.form["nombre"]
        email = request.form["email"]

        conn.execute("""
        UPDATE usuarios
        SET nombre=?, email=?
        WHERE id=?
        """,(
            nombre,
            email,
            session["user_id"]
        ))
        conn.commit()

        session["nombre"] = nombre

    user = conn.execute(
        "SELECT * FROM usuarios WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return render_template("perfil.html", user=user)

# ======================
# PASSWORD
# ======================
@app.route("/password", methods=["POST"])
def password():

    actual = request.form["actual"]
    nueva = request.form["nueva"]
    confirmar = request.form["confirmar"]

    if nueva != confirmar:
        return redirect("/perfil")

    conn = get_db()

    user = conn.execute(
        "SELECT password FROM usuarios WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if not check_password_hash(user["password"], actual):
        conn.close()
        return redirect("/perfil")

    conn.execute("""
    UPDATE usuarios SET password=?
    WHERE id=?
    """,(
        generate_password_hash(nueva),
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
    conn.execute("""
    INSERT INTO pdfs (
        profesor_id,
        nombre,
        archivo,
        carrera,
        materia,
        observaciones,
        fecha,
        fecha_creacion,
        creado_por
    )
    VALUES (?,?,?,?,?,?,?,?,?)
    """,(
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

    pdf = conn.execute(
        "SELECT archivo FROM pdfs WHERE id=?",
        (id,)
    ).fetchone()

    if pdf:
        path = os.path.join(UPLOAD_FOLDER, pdf["archivo"])
        if os.path.exists(path):
            os.remove(path)

    conn.execute("DELETE FROM pdfs WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin")


# ======================
# EDITAR PDF
# ======================
@app.route("/editar_pdf/<int:id>", methods=["GET","POST"])
def editar_pdf(id):

    conn = get_db()

    pdf = conn.execute(
        "SELECT * FROM pdfs WHERE id=?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        archivo = pdf["archivo"]

        file = request.files.get("pdf")

        if file and file.filename != "":
            original = secure_filename(file.filename)
            archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original}"
            file.save(os.path.join(UPLOAD_FOLDER, archivo))

        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

        conn.execute("""
        UPDATE pdfs
        SET carrera=?,
            materia=?,
            observaciones=?,
            archivo=?,
            fecha=?,
            fecha_edicion=?,
            editado_por=?
        WHERE id=?
        """,(
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

        if session["rol"] == "admin":
            return redirect("/admin")

        return redirect("/dashboard")

    conn.close()
    return render_template("editar_pdf.html", pdf=pdf)


if __name__ == "__main__":
    app.run(debug=True)