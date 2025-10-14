# SIS_RESERVAS_CANCHA

Aplicación web en Flask para la gestión de reservas de canchas con autenticación básica y conexión a SQL Server.

## Requisitos

- Python 3.10+
- pip
- SQL Server con el driver **ODBC Driver 17 for SQL Server**

## Instalación

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Si no existe `requirements.txt`, instala manualmente:

```bash
pip install flask pyodbc werkzeug
```

## Configuración de la base de datos

1. Ejecuta el script SQL del directorio del proyecto o usa el siguiente fragmento:

```sql
IF DB_ID('SIS_RESERVAS_CANCHA') IS NULL
BEGIN
    CREATE DATABASE SIS_RESERVAS_CANCHA;
END;
GO

USE SIS_RESERVAS_CANCHA;
GO

IF OBJECT_ID('dbo.users', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.users
    (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(150) NOT NULL UNIQUE,
        password NVARCHAR(255) NOT NULL,
        role NVARCHAR(50) NOT NULL
            CHECK (role IN ('admin', 'client'))
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = 'admin')
BEGIN
    INSERT INTO dbo.users (username, password, role)
    VALUES ('admin', 'admin123', 'admin');
END;
GO
```

2. Asegúrate de tener el usuario `sa` habilitado y con contraseña `sa` o ajusta `db.py` con tus credenciales.
3. Ejecuta `python db.py` para verificar la conexión (muestra mensajes en consola).

## Ejecución

```bash
set FLASK_APP=app.py
python app.py
```

La aplicación inicia en `http://127.0.0.1:5000/`. El inicio exige autenticación; usa `admin/admin123` (texto plano) mientras no se hayan cifrado las contraseñas.

## Características

- Registro y autenticación básica de usuarios (rutas `/login`, `/logout`, `/admin/register`).
- Gestión de reservas desde la ruta `/` con vista semanal.
- Formularios con validaciones de horarios y duración.

## Notas de seguridad

- En producción, reemplaza la contraseña del usuario `sa` y usa variables de entorno para credenciales.
- Cambia la columna `password` por hashes usando `werkzeug.security.generate_password_hash` y ajusta `app.py` para rechazar texto plano.

## Estructura relevante

- `app.py`: rutas Flask y lógica de reservas.
- `db.py`: conexión y consultas a SQL Server.
- `templates/`: vistas HTML (`login.html`, `admin_register.html`, `index.html`, `reservar.html`).

## Próximos pasos sugeridos

- Persistir reservas en la tabla `dbo.reservas`.
- Implementar roles para restringir acciones administrativas.
- Agregar tests y documentación de endpoints.
