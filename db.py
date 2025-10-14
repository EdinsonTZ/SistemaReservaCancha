import pyodbc

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
        " role NVARCHAR(50) NOT NULL"
        ")"
    )

    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    cursor.close()
    conn.close()


def create_user(username, password_hash, role="client"):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    cursor.close()
    conn.close()


def get_user_by_username(username):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("No se pudo establecer conexión con SQL Server.")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
        }
    return None












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