from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
try:
    import db
    DB_AVAILABLE = True
except Exception as _err:
    db = None
    DB_AVAILABLE = False
    print("Aviso: módulo de base de datos no disponible. Instala 'pyodbc' y configura MSSQL_CONN para habilitar auth.")
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.secret_key = "canchas_secretas"  # clave necesaria para usar mensajes flash

FORMATO_FECHA = "%Y-%m-%d"

# Días disponibles para mostrar en los formularios.
DIAS_SEMANA = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sabado",
    "Domingo"
]

HORAS_DISPONIBLES = [f"{hora:02d}:00" for hora in range(6, 22)]


def obtener_dia_desde_fecha(fecha_obj):
    if not fecha_obj:
        return DIAS_SEMANA[0]
    indice = fecha_obj.weekday()
    if 0 <= indice < len(DIAS_SEMANA):
        return DIAS_SEMANA[indice]
    return DIAS_SEMANA[0]


def obtener_reservas_por_dia(fecha_inicio=None, fecha_fin=None):
    """Genera un diccionario con las reservas organizadas por día."""
    reservas_por_dia = {dia: [] for dia in DIAS_SEMANA}

    reservas_db = []
    if DB_AVAILABLE:
        try:
            reservas_db = db.obtener_reservas()
        except Exception as exc:
            print("No se pudieron cargar reservas desde la base de datos:", exc)

    for reserva in reservas_db:
        fecha_reserva = reserva.get("fecha_reserva")
        if fecha_inicio and fecha_reserva and fecha_reserva < fecha_inicio:
            continue
        if fecha_fin and fecha_reserva and fecha_reserva > fecha_fin:
            continue
        if reserva["dia"] in reservas_por_dia:
            reservas_por_dia[reserva["dia"]].append(reserva)

    for reservas_dia in reservas_por_dia.values():
        reservas_dia.sort(key=lambda r: (r.get("fecha_reserva", date.today()), r["inicio"]))

    return reservas_por_dia


def horarios_se_cruzan(inicio_a, fin_a, inicio_b, fin_b):
    """Devuelve True si dos rangos horarios se sobreponen."""
    return inicio_a < fin_b and fin_a > inicio_b


def obtener_dia_actual():
    """Retorna el nombre del día actual según la lista `DIAS_SEMANA`."""
    return obtener_dia_desde_fecha(datetime.now().date())


def generar_segmentos_horarios(reservas_dia, horas_disponibles=None):
    """Construye una lista de bloques horarios de una hora marcando disponibilidad."""
    if horas_disponibles is None:
        horas_disponibles = HORAS_DISPONIBLES

    segmentos = []
    formato = "%H:%M"
    for hora_inicio_str in horas_disponibles:
        hora_actual = datetime.strptime(hora_inicio_str, formato)
        siguiente_hora = hora_actual + timedelta(hours=1)
        reserva_segmento = next(
            (
                reserva
                for reserva in reservas_dia
                if horarios_se_cruzan(
                    hora_actual.time(),
                    siguiente_hora.time(),
                    reserva["inicio"],
                    reserva["fin"],
                )
            ),
            None,
        )

        segmentos.append(
            {
                "hora_inicio": hora_actual.strftime(formato),
                "hora_fin": siguiente_hora.strftime(formato),
                "estado": "Reservado" if reserva_segmento else "Disponible",
                "reserva": reserva_segmento,
            }
        )

        hora_actual = siguiente_hora

    return segmentos


def obtener_horas_libres(dia, duracion=1, fecha_reserva=None):
    """Devuelve la lista de horas en punto libres para un día específico.

    Ahora considera la `duracion` (horas) y devuelve sólo las horas de inicio
    que cuentan con `duracion` bloques consecutivos libres.
    """
    if dia not in DIAS_SEMANA:
        return []

    if fecha_reserva is None:
        return HORAS_DISPONIBLES.copy()

    formato = "%H:%M"
    # Marcamos ocupadas todas las horas en punto que estén cubiertas por reservas.
    horas_ocupadas = set()
    reservas_fecha = []
    if DB_AVAILABLE:
        try:
            reservas_fecha = db.obtener_reservas(fecha_reserva)
        except Exception as exc:
            print("No se pudieron obtener reservas para la fecha", fecha_reserva, exc)

    for reserva in reservas_fecha:
        if reserva["dia"] != dia:
            continue
        inicio_dt = datetime.strptime(reserva["hora_inicio"], formato)
        fin_dt = datetime.strptime(reserva["hora_fin"], formato)
        curr = inicio_dt
        while curr < fin_dt:
            horas_ocupadas.add(curr.strftime(formato))
            curr += timedelta(hours=1)

    # Ahora para cada posible hora de inicio, comprobamos si hay duracion bloques
    horas_validas = []
    for hora in HORAS_DISPONIBLES:
        inicio_dt = datetime.strptime(hora, formato)
        fin_dt = inicio_dt + timedelta(hours=duracion)
        # comprobar que no exceda horario de cierre (22:00)
        cierre = datetime.strptime(HORAS_DISPONIBLES[-1], formato) + timedelta(hours=1)
        if fin_dt > cierre:
            continue

        # comprobar todos los bloques intermedios
        curr = inicio_dt
        disponible = True
        while curr < fin_dt:
            if curr.strftime(formato) in horas_ocupadas:
                disponible = False
                break
            curr += timedelta(hours=1)

        if disponible:
            horas_validas.append(hora)

    return horas_validas


def construir_horas_inicio_fin(dia, duracion=1, fecha_reserva=None):
    """Devuelve una lista de dicts {'hora_inicio','hora_fin'} para horas de inicio
    válidas según la duración."""
    formato = "%H:%M"
    horas_inicio = obtener_horas_libres(dia, duracion, fecha_reserva)
    result = []
    for hora in horas_inicio:
        inicio_dt = datetime.strptime(hora, formato)
        fin_dt = inicio_dt + timedelta(hours=duracion)
        result.append({
            "hora_inicio": inicio_dt.strftime(formato),
            "hora_fin": fin_dt.strftime(formato),
        })
    return result


@app.route("/")
def inicio():
    """Página principal con enlaces y resumen semanal."""
    usuario = usuario_actual()
    if not usuario:
        return redirect(url_for("login"))

    form_data = session.pop("form_data", {})
    fecha_param = request.args.get("fecha")
    dia_param = request.args.get("dia")
    duracion_param = request.args.get("duracion")
    fecha_form = form_data.get("fecha")

    if fecha_param:
        try:
            fecha_seleccionada = datetime.strptime(fecha_param, FORMATO_FECHA).date()
        except ValueError:
            fecha_seleccionada = date.today()
    elif fecha_form:
        try:
            fecha_seleccionada = datetime.strptime(fecha_form, FORMATO_FECHA).date()
        except ValueError:
            fecha_seleccionada = date.today()
    else:
        fecha_seleccionada = date.today()

    if fecha_seleccionada:
        dia_calculado = obtener_dia_desde_fecha(fecha_seleccionada)
    else:
        dia_calculado = obtener_dia_actual()

    if dia_param in DIAS_SEMANA:
        dia_seleccionado = dia_param
    elif form_data.get("dia") in DIAS_SEMANA:
        dia_seleccionado = form_data.get("dia")
    else:
        dia_seleccionado = dia_calculado

    # Si el día seleccionado no coincide con la fecha, sincronizamos con la fecha
    if dia_seleccionado != dia_calculado:
        dia_seleccionado = dia_calculado

    inicio_semana = fecha_seleccionada - timedelta(days=fecha_seleccionada.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    reservas_por_dia = obtener_reservas_por_dia(inicio_semana, fin_semana)
    reservas_dia = reservas_por_dia.get(dia_seleccionado, [])
    reservas_dia_fecha = [r for r in reservas_dia if r.get("fecha_reserva") == fecha_seleccionada]
    segmentos = generar_segmentos_horarios(reservas_dia_fecha)
    dia_formulario = dia_seleccionado
    # Determinar duración: prioridad GET > form_data > 1
    try:
        duracion = int(duracion_param) if duracion_param else int(form_data.get("duracion", 1))
    except (ValueError, TypeError):
        duracion = 1

    if duracion not in (1, 2, 3):
        duracion = 1

    horas_formulario = construir_horas_inicio_fin(dia_formulario, duracion, fecha_seleccionada)
    hora_previa = form_data.get("hora_inicio")
    hora_previa_no_disponible = bool(hora_previa and hora_previa not in horas_formulario)
    formulario_bloqueado = len(horas_formulario) == 0

    nombre_usuario = obtener_nombre_usuario(usuario)
    form_data["dia"] = dia_formulario
    form_data.setdefault("fecha", fecha_seleccionada.strftime(FORMATO_FECHA))

    fechas_semana = {}
    for i, dia in enumerate(DIAS_SEMANA):
        fecha_dia = inicio_semana + timedelta(days=i)
        fechas_semana[dia] = {
            "iso": fecha_dia.strftime(FORMATO_FECHA),
            "visual": fecha_dia.strftime("%d-%m-%Y"),
        }

    return render_template(
        "index.html",
        reservas_por_dia=reservas_por_dia,
        dias=DIAS_SEMANA,
        form_data=form_data,
        dia_seleccionado=dia_seleccionado,
        segmentos=segmentos,
        dia_formulario=dia_formulario,
        horas_formulario=horas_formulario,
        formulario_bloqueado=formulario_bloqueado,
        hora_previa=hora_previa,
        hora_previa_no_disponible=hora_previa_no_disponible,
        duracion=duracion,
        usuario=usuario,
        nombre_usuario=nombre_usuario,
        fecha_reserva=fecha_seleccionada.strftime(FORMATO_FECHA),
        fechas_semana=fechas_semana,
    )


def usuario_actual():
    """Devuelve dict con usuario en sesión o None."""
    if not session.get("user_id"):
        return None
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
        "nombres": session.get("nombres"),
        "apellidos": session.get("apellidos"),
        "dni": session.get("dni"),
    }


def obtener_nombre_usuario(usuario):
    if not usuario:
        return ""
    partes = []
    nombres = usuario.get("nombres")
    apellidos = usuario.get("apellidos")
    if nombres:
        partes.append(nombres.strip())
    if apellidos:
        partes.append(apellidos.strip())
    nombre = " ".join(partes)
    if not nombre:
        username = usuario.get("username")
        nombre = username.strip() if username else ""
    return nombre


## LOGIN ##########################################################

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Ingrese usuario y contraseña.", "warning")
        return redirect(url_for("login"))

    try:
        user = db.get_user_by_username(username)
    except Exception as e:
        flash("Error al conectarse a la base de datos.", "danger")
        return redirect(url_for("login"))

    if not user:
        flash("Usuario o contraseña incorrectos.", "danger")
        return redirect(url_for("login"))

    password_db = user.get("password_hash")
    password_ok = False

    if password_db:
        try:
            password_ok = check_password_hash(password_db, password)
        except ValueError:
            password_ok = False

    if not password_ok and password_db == password:
        password_ok = True

    if not password_ok:
        flash("Usuario o contraseña incorrectos.", "danger")
        return redirect(url_for("login"))

    # Guardar en sesión
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["nombres"] = user.get("nombres")
    session["apellidos"] = user.get("apellidos")
    session["dni"] = user.get("dni")
    flash("Autenticación exitosa.", "success")
    return redirect(url_for("inicio"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("role", None)
    session.pop("nombres", None)
    session.pop("apellidos", None)
    session.pop("dni", None)
    flash("Sesión cerrada.", "info")
    return redirect(url_for("inicio"))


@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    user = usuario_actual()
    if not user or user.get("role") != "admin":
        flash("Acceso denegado. Solo administradores.", "danger")
        return redirect(url_for("inicio"))

    if request.method == "GET":
        return render_template("admin_register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    nombres = request.form.get("nombres", "").strip()
    apellidos = request.form.get("apellidos", "").strip()
    dni = request.form.get("dni", "").strip()
    role = request.form.get("role", "client")

    if not username or not password or not nombres or not apellidos:
        flash("Completa usuario, contraseña, nombres y apellidos.", "warning")
        return redirect(url_for("admin_register"))

    dni_valor = dni or None

    password_hash = generate_password_hash(password)
    try:
        db.create_user(username, password_hash, role, nombres, apellidos, dni_valor)
    except Exception as e:
        flash("Error al crear el usuario (posible duplicado).", "danger")
        return redirect(url_for("admin_register"))

    flash("Usuario creado con éxito.", "success")
    return redirect(url_for("inicio"))


@app.route("/reservar", methods=["GET", "POST"])
def reservar():
    """Permite crear una nueva reserva y valida solapamientos."""
    user = usuario_actual()
    if not user:
        flash("Debes iniciar sesión para reservar.", "warning")
        return redirect(url_for("login"))

    nombre_usuario = obtener_nombre_usuario(user)

    if not nombre_usuario:
        flash("No se pudo determinar el nombre del usuario autenticado.", "danger")
        return redirect(url_for("inicio"))

    if request.method == "GET":
        # Permitir acceso directo al formulario y prefiltrar horas según query params
        dia = None  # El día se determinará desde la fecha elegida
        fecha_param = request.args.get("fecha")
        duracion_param = request.args.get("duracion")
        try:
            duracion = int(duracion_param) if duracion_param else 1
        except (ValueError, TypeError):
            duracion = 1
        if duracion not in (1, 2, 3):
            duracion = 1

        if fecha_param:
            try:
                fecha_reserva = datetime.strptime(fecha_param, FORMATO_FECHA).date()
            except ValueError:
                fecha_reserva = date.today()
        else:
            fecha_reserva = date.today()

        horas_disponibles = []
        if dia in DIAS_SEMANA:
            horas_disponibles = construir_horas_inicio_fin(dia, duracion, fecha_reserva)

        dia = obtener_dia_desde_fecha(fecha_reserva)
        form_data = {"dia": dia, "duracion": duracion, "fecha": fecha_reserva.strftime(FORMATO_FECHA)}
        return render_template(
            "reservar.html",
            dias=DIAS_SEMANA,
            horas_disponibles=horas_disponibles,
            form_data=form_data,
            usuario=user,
            nombre_usuario=nombre_usuario,
            fecha_reserva=fecha_reserva.strftime(FORMATO_FECHA),
        )

    if request.method == "POST":
        dia = request.form.get("dia")
        fecha_texto = request.form.get("fecha")
        hora_inicio = request.form.get("hora_inicio")

        # Validaciones básicas para evitar datos incompletos.
        if not dia or not hora_inicio or not fecha_texto:
            session["form_data"] = request.form.to_dict()
            flash("Por favor completa todos los campos.", "warning")
            fecha_redirect = fecha_texto or date.today().strftime(FORMATO_FECHA)
            return redirect(url_for("inicio", dia=dia, fecha=fecha_redirect))

        try:
            fecha_reserva = datetime.strptime(fecha_texto, FORMATO_FECHA).date()
        except ValueError:
            session["form_data"] = request.form.to_dict()
            flash("Fecha inválida.", "danger")
            return redirect(url_for("inicio", dia=dia or obtener_dia_actual(), fecha=fecha_texto or date.today().strftime(FORMATO_FECHA)))

        dia_calculado = obtener_dia_desde_fecha(fecha_reserva)
        dia = dia_calculado

        if dia not in DIAS_SEMANA:
            session["form_data"] = request.form.to_dict()
            flash("Selecciona un día válido de lunes a viernes.", "warning")
            return redirect(url_for("inicio", fecha=fecha_texto or date.today().strftime(FORMATO_FECHA)))

        # Leer duración enviada por el formulario (por seguridad limitar a 1-3)
        duracion_raw = request.form.get("duracion", "1")
        try:
            duracion = int(duracion_raw)
        except (ValueError, TypeError):
            duracion = 1

        if duracion not in (1, 2, 3):
            duracion = 1

        horas_libres = obtener_horas_libres(dia, duracion, fecha_reserva)

        if hora_inicio not in HORAS_DISPONIBLES:
            session["form_data"] = request.form.to_dict()
            flash("Selecciona una hora válida en punto.", "warning")
            return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))

        if hora_inicio not in horas_libres:
            session["form_data"] = request.form.to_dict()
            flash("El bloque elegido no está completamente disponible para la duración seleccionada.", "danger")
            return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))

        # Convertimos los horarios a objetos datetime.time para compararlos.
        formato_hora = "%H:%M"
        inicio_dt_full = datetime.strptime(hora_inicio, formato_hora)
        inicio_dt = inicio_dt_full.time()
        fin_dt_full = inicio_dt_full + timedelta(hours=duracion)
        fin_dt = fin_dt_full.time()
        hora_fin = fin_dt_full.strftime(formato_hora)

        # comprobar que no exceda horario de cierre (22:00)
        cierre = datetime.strptime(HORAS_DISPONIBLES[-1], formato_hora) + timedelta(hours=1)
        if fin_dt_full > cierre:
            session["form_data"] = request.form.to_dict()
            flash(f"La reserva excede el horario de cierre ({cierre.strftime(formato_hora)}).", "danger")
            return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))

        # Buscamos si ya existe una reserva que se cruza con el horario indicado.
        reservas_existentes = []
        if DB_AVAILABLE:
            try:
                reservas_existentes = db.obtener_reservas(fecha_reserva)
            except Exception as exc:
                print("No se pudieron obtener reservas para la validación:", exc)

        for reserva in reservas_existentes:
            if reserva["dia"] == dia:
                if horarios_se_cruzan(inicio_dt, fin_dt, reserva["inicio"], reserva["fin"]):
                    flash(
                        f"El intervalo elegido se cruza con la reserva de {reserva['nombre']} ("
                        f"{reserva['hora_inicio']} - {reserva['hora_fin']}).",
                        "danger",
                    )
                    session["form_data"] = request.form.to_dict()
                    return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))

        # Si todo está correcto, guardamos la nueva reserva en memoria.
        if DB_AVAILABLE:
            try:
                db.crear_reserva(
                    usuario_id=user.get("id"),
                    usuario_username=user.get("username"),
                    nombre_mostrado=nombre_usuario,
                    fecha_reserva=fecha_reserva,
                    dia=dia,
                    hora_inicio=hora_inicio,
                    hora_fin=hora_fin,
                    duracion_horas=duracion,
                )
            except Exception as exc:
                session["form_data"] = request.form.to_dict()
                flash("No se pudo guardar la reserva en la base de datos.", "danger")
                print("Error al crear reserva:", exc)
                return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))
        else:
            flash("La base de datos no está disponible, no se puede persistir la reserva.", "danger")
            return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))

        session.pop("form_data", None)
        flash("Reserva creada con éxito.", "success")
        return redirect(url_for("inicio", dia=dia, fecha=fecha_reserva.strftime(FORMATO_FECHA)))

    return render_template(
        "reservar.html",
        dias=DIAS_SEMANA,
        horas_disponibles=HORAS_DISPONIBLES,
        usuario=user,
        nombre_usuario=nombre_usuario,
        fecha_reserva=date.today().strftime(FORMATO_FECHA),
    )




# Vista detallada eliminada: la ruta /consultar ya no existe


if __name__ == "__main__":
    # Ejecuta la aplicación en modo debug para desarrollo local.
    # Si existe la variable de entorno para SQL Server, intentamos inicializar tablas.
    if os.environ.get('MSSQL_CONN'):
        try:
            db.init_db()
            print('Inicializada la base de datos (users).')
        except Exception as e:
            print('No se pudo inicializar la base de datos:', e)
    else:
        print('MSSQL_CONN no definida: la autenticación con SQL Server no estará disponible.')

    app.run(debug=True)
