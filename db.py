import pyodbc
from datetime import datetime

# Usuario y contraseña 'sa'
SA_PASSWORD = 'sa'
DB_SERVER = '80CLSOP13'
DB_NAME = 'SIS_RESERVAS_CANCHA'
DB_DRIVER = '{ODBC Driver 17 for SQL Server}'


def get_db_connection():
    # Cadena de conexión para SQL Server usando autenticación de SQL Server
    connection_string = (
        f'DRIVER={DB_DRIVER};'
        f'SERVER={DB_SERVER};'
        f'DATABASE={DB_NAME};'
        'UID=sa;'
        f'PWD={SA_PASSWORD};'
    )

    try:
        conn = pyodbc.connect(connection_string, autocommit=True)
        print("Conexión a SQL Server exitosa.")
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0] if ex.args else 'DESCONOCIDO'
        mensaje = ex.args[1] if len(ex.args) > 1 else str(ex)
        print(f"ERROR DE CONEXIÓN [{sqlstate}]: {mensaje}")
        return None


########################################################################





def init_db():
    """Crea la tabla `users` si no existe."""
    create_table_sql = (
        "IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')"
        " CREATE TABLE users ("
        " id INT IDENTITY(1,1) PRIMARY KEY,") + (
            " username NVARCHAR(150) NOT NULL UNIQUE,"
            " password NVARCHAR(255) NOT NULL,"
            " nombres NVARCHAR(150) NOT NULL,"
            " apellidos NVARCHAR(150) NOT NULL,"
            " dni NVARCHAR(20) NULL,"
            " role NVARCHAR(50) NOT NULL"
        ")"
    )
    # Build combined string since earlier concatenation had an issue
    create_table_sql = (
        "IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')"
        " CREATE TABLE users ("
        " id INT IDENTITY(1,1) PRIMARY KEY,"
        " username NVARCHAR(150) NOT NULL UNIQUE,"
        " password NVARCHAR(255) NOT NULL,"
        " nombres NVARCHAR(150) NOT NULL,"
        " apellidos NVARCHAR(150) NOT NULL,"
        " dni NVARCHAR(20) NULL,"
        " role NVARCHAR(50) NOT NULL"
        ")"
    )

    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute(create_table_sql)

    alter_commands = [
        "IF COL_LENGTH('users', 'nombres') IS NULL ALTER TABLE users ADD nombres NVARCHAR(150) NOT NULL DEFAULT ''",
        "IF COL_LENGTH('users', 'apellidos') IS NULL ALTER TABLE users ADD apellidos NVARCHAR(150) NOT NULL DEFAULT ''",
        "IF COL_LENGTH('users', 'dni') IS NULL ALTER TABLE users ADD dni NVARCHAR(20) NULL",
        "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UQ_users_dni' AND object_id = OBJECT_ID('dbo.users'))"
        " CREATE UNIQUE INDEX UQ_users_dni ON dbo.users (dni) WHERE dni IS NOT NULL"
    ]

    for command in alter_commands:
        cursor.execute(command)

    create_reservas_sql = (
        "IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='reservas' AND xtype='U')"
        " CREATE TABLE reservas ("
        " id INT IDENTITY(1,1) PRIMARY KEY,"
        " usuario_id INT NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE CASCADE,"
        " usuario_username NVARCHAR(150) NOT NULL,"
        " nombre_mostrado NVARCHAR(300) NOT NULL,"
        " fecha_reserva DATE NOT NULL,"
        " dia NVARCHAR(15) NOT NULL,"
        " hora_inicio TIME(0) NOT NULL,"
        " hora_fin TIME(0) NOT NULL,"
        " duracion_horas TINYINT NOT NULL,"
        " creado_en DATETIME2 NOT NULL DEFAULT SYSDATETIME()"
        ")"
    )
    cursor.execute(create_reservas_sql)

    alter_reservas_commands = [
        "IF COL_LENGTH('reservas', 'usuario_username') IS NULL ALTER TABLE reservas ADD usuario_username NVARCHAR(150) NOT NULL DEFAULT ''",
        "IF COL_LENGTH('reservas', 'nombre_mostrado') IS NULL ALTER TABLE reservas ADD nombre_mostrado NVARCHAR(300) NOT NULL DEFAULT ''",
        "IF COL_LENGTH('reservas', 'fecha_reserva') IS NULL ALTER TABLE reservas ADD fecha_reserva DATE NOT NULL DEFAULT CAST(GETDATE() AS DATE)",
        "IF COL_LENGTH('reservas', 'dia') IS NULL ALTER TABLE reservas ADD dia NVARCHAR(15) NOT NULL DEFAULT 'Lunes'",
        "IF COL_LENGTH('reservas', 'duracion_horas') IS NULL ALTER TABLE reservas ADD duracion_horas TINYINT NOT NULL DEFAULT 1",
        "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_reservas_fecha_hora' AND object_id = OBJECT_ID('dbo.reservas'))"
        " CREATE UNIQUE INDEX IX_reservas_fecha_hora ON dbo.reservas (fecha_reserva, hora_inicio, hora_fin, usuario_id)",
    ]

    for command in alter_reservas_commands:
        cursor.execute(command)

    if not _reservas_tiene_usuario_username(cursor):
        cursor.execute("UPDATE reservas SET usuario_username = (SELECT username FROM users WHERE users.id = reservas.usuario_id)")

    cursor.close()
    conn.close()


def _reservas_tiene_usuario_username(cursor):
    try:
        cursor.execute("SELECT TOP 1 usuario_username FROM reservas")
        cursor.fetchone()
        return True
    except pyodbc.Error:
        return False


def create_user(username, password_hash, role="client", nombres="", apellidos="", dni=None):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, nombres, apellidos, dni, role) VALUES (?, ?, ?, ?, ?, ?)",
        (username, password_hash, nombres, apellidos, dni, role),
    )
    cursor.close()
    conn.close()


def get_user_by_username(username):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role, nombres, apellidos, dni FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "nombres": row[4],
            "apellidos": row[5],
            "dni": row[6],
        }
    return None


def crear_reserva(usuario_id, usuario_username, nombre_mostrado, fecha_reserva, dia, hora_inicio, hora_fin, duracion_horas):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reservas (usuario_id, usuario_username, nombre_mostrado, fecha_reserva, dia, hora_inicio, hora_fin, duracion_horas)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (usuario_id, usuario_username, nombre_mostrado, fecha_reserva, dia, hora_inicio, hora_fin, duracion_horas)
    )
    cursor.close()
    conn.close()


def obtener_reservas(fecha=None):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    if fecha:
        cursor.execute(
            "SELECT id, usuario_id, usuario_username, nombre_mostrado, fecha_reserva, dia, hora_inicio, hora_fin, duracion_horas"
            " FROM reservas WHERE fecha_reserva = ?", (fecha,)
        )
    else:
        cursor.execute(
            "SELECT id, usuario_id, usuario_username, nombre_mostrado, fecha_reserva, dia, hora_inicio, hora_fin, duracion_horas"
            " FROM reservas"
        )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    reservas = []
    for row in rows:
        fecha_reserva = row[4]
        hora_inicio = row[6]
        hora_fin = row[7]
        reservas.append(
            {
                "id": row[0],
                "usuario_id": row[1],
                "usuario_username": row[2],
                "nombre": row[3],
                "fecha_reserva": fecha_reserva,
                "dia": row[5],
                "inicio": hora_inicio,
                "fin": hora_fin,
                "hora_inicio": hora_inicio.strftime("%H:%M"),
                "hora_fin": hora_fin.strftime("%H:%M"),
                "duracion": row[8],
            }
        )
    return reservas












#########################################################################################

# db.py (Añade esto al final del archivo)

if __name__ == '__main__':
    print("--- Verificando la conexión a la base de datos ---")
    
    conexion_de_prueba = get_db_connection()
    
    if conexion_de_prueba:
        print("✅ PRUEBA EXITOSA: La conexión a la base de datos funciona correctamente.")
        # Cierra la conexión de prueba inmediatamente
        conexion_de_prueba.close() 
    else:
        print("❌ PRUEBA FALLIDA: Revisa el error mostrado arriba y tu cadena de conexión.")
    print("--------------------------------------------------")