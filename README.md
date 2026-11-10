# lum-tui — Linux User Manager TUI

Herramienta de consola para administrar usuarios locales de Linux desde una
interfaz TUI construida con [Textual](https://textual.textualize.io/). El
objetivo es ofrecer una experiencia rápida y densa, inspirada en `htop`, con
búsqueda incremental, panel de inspección y operaciones de alta/baja de
usuarios ejecutadas de forma segura.

La especificación técnica completa está en
[`docs/LHD-UsersAdmin.md`](docs/LHD-UsersAdmin.md).

> **Estado actual — Fase 1 (base del proyecto).**
> Están implementados la estructura MVC, la configuración visual externa, el
> cargador de temas TCSS y la capa de sistema (`pwd`, `grp`, `useradd`,
> `userdel`). La pantalla principal, los widgets y los modales se implementarán
> en la siguiente fase (ver [Roadmap](#roadmap)).

## Características previstas

- Listado de usuarios locales leído desde `pwd` y `grp`, ordenado por UID.
- Tabla densa estilo `htop` con cursor por filas y soporte de *zebra stripes*.
- Búsqueda rápida por nombre de usuario o UID.
- Panel inferior con información ampliada del usuario seleccionado.
- Alta de usuarios mediante `useradd` y baja mediante `userdel`.
- Atajos de teclado tipo `htop`/OpenCode (`F1`–`F5`, `/`, `q`, `Esc`).
- Tema visual externalizado: ningún color, borde o margen está codificado en
  los widgets; todo se genera desde `config/app_style.json`.
- Mensajes de error amigables en la TUI, sin trazas de pila, cuando faltan
  privilegios.

## Stack

- Python 3.10+
- [Textual](https://textual.textualize.io/) (`>=0.40.0`)
- Utilidades estándar de Linux: `pwd`, `grp`, `subprocess`, `useradd`, `userdel`
- `sudo` para elevación de privilegios (o ejecución directa como root)

## Instalación

```bash
git clone <url-del-repositorio> LHD-UsersAdmin
cd LHD-UsersAdmin

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> En Debian/Ubuntu puede ser necesario instalar antes `python3-venv`:
> `sudo apt install python3-venv`.

## Ejecución

La aplicación necesita privilegios para crear o eliminar usuarios, pero no para
leerlos. El modo recomendado es cachear la credencial de `sudo` y ejecutar la
TUI como usuario normal:

```bash
sudo -v          # cachea la contraseña de sudo
python -m src.main
```

También se puede ejecutar directamente como root:

```bash
sudo -E .venv/bin/python -m src.main
```

El backend usa `sudo -n` (no interactivo) para que la TUI nunca se quede
bloqueada esperando una contraseña. Si `sudo` no tiene credenciales cacheadas ni
una regla `NOPASSWD`, la aplicación mostrará un aviso de privilegios en lugar de
fallar con un *stack trace*.

> La entrada `src/main.py` y las vistas todavía son marcadores de posición: se
> completarán en la fase 2. Mientras tanto, el backend y el cargador de temas
> pueden probarse de forma independiente.

## Configuración visual

Toda la apariencia se controla desde [`config/app_style.json`](config/app_style.json):

| Sección | Contenido |
| --- | --- |
| `theme_name` | Nombre identificativo del tema. |
| `palette` | Colores base (`background`, `surface`, `primary`, `text`, `error`, etc.). |
| `typography` | Estilo de texto global (`font_style`, por defecto `bold`). |
| `borders` | Tipo de borde de paneles y ventanas (`round`, `solid`, etc.). |
| `table` | Fondos de filas pares/impares y colores del cursor de la tabla. |

`src/utils/theme_loader.py` valida el JSON y lo traduce a TCSS en tiempo de
arranque. Se puede usar una configuración alternativa sin tocar código:

```python
from src.utils.theme_loader import load_tcss_from_config

css = load_tcss_from_config("/ruta/a/mi_tema.json")
```

Comprobación rápida del cargador (no requiere Textual instalado):

```bash
python - <<'PY'
from src.utils.theme_loader import load_tcss_from_config

print(load_tcss_from_config()[:500])
PY
```

## Arquitectura

El proyecto sigue un MVC estricto: el sistema, la lógica y la interfaz están
desacoplados.

```text
lum-tui/
├── config/
│   └── app_style.json        # Paleta y parámetros visuales externos
├── docs/
│   └── LHD-UsersAdmin.md     # Especificación técnica
├── src/
│   ├── __init__.py
│   ├── main.py               # Punto de entrada (fase 2)
│   ├── models/
│   │   └── sys_user.py       # Modelo de usuario (fase 2)
│   ├── controllers/
│   │   └── user_manager.py   # Backend Linux: pwd/grp/useradd/userdel
│   ├── views/
│   │   ├── screens.py        # MainScreen y modales (fase 2)
│   │   └── widgets.py        # Header, Footer, UserTable (fase 2)
│   └── utils/
│       └── theme_loader.py   # JSON -> TCSS
├── requirements.txt
└── README.md
```

### Capa de sistema (`src/controllers/user_manager.py`)

`SystemUserManager` expone:

- `get_all_users(include_system=True)`: lista usuarios desde `pwd`, resuelve el
  grupo primario con `grp` y marca las cuentas de sistema.
- `get_user(username)`, `user_exists(username)` y `get_user_groups(username)`.
- `get_available_shells()`: shells para el selector del formulario.
- `create_user(...)`: ejecuta `useradd` con argumentos validados.
- `delete_user(username, remove_home=False)`: ejecuta `userdel`; protege `root`
  y la cuenta desde la que se ejecuta la aplicación.
- `check_privileges()` / `has_privileges()`: comprobación previa de root o sudo.

Errores tipados: `UserValidationError`, `UserNotFoundError`,
`UserAlreadyExistsError`, `PrivilegeError` y `UserOperationError`.

## Seguridad

- **Sin `shell=True`**: todos los comandos se construyen como listas de
  argumentos, evitando inyección de shell.
- **Validación POSIX** de nombres de usuario y grupos:
  `^[a-z_][a-z0-9_-]*\$?$`, con límite de 32 caracteres.
- **Validación de rutas** de shell y home antes de invocar `useradd`.
- **`sudo -n`**: nunca se solicita contraseña dentro de la TUI.
- **Cuentas protegidas**: no se puede eliminar `root` ni el usuario actual.
- **Errores controlados**: los fallos de `sudo`/`useradd`/`userdel` se traducen
  a excepciones de dominio con mensajes claros.

## Atajos de teclado (fase 2)

| Tecla | Acción |
| --- | --- |
| `F1` / `?` | Ayuda y lista de atajos |
| `F2` / `a` | Nuevo usuario |
| `F3` / `e` | Editar usuario |
| `F4` / `d` | Eliminar usuario (con confirmación) |
| `F5` / `r` | Recargar lista |
| `/` / `Ctrl+F` | Enfocar búsqueda rápida |
| `q` / `Esc` | Salir |

## Roadmap

- [x] Estructura MVC y `requirements.txt`.
- [x] `config/app_style.json` y `src/utils/theme_loader.py`.
- [x] `SystemUserManager` con lectura y operaciones seguras.
- [ ] `src/models/sys_user.py`: modelo de datos enriquecido.
- [ ] `src/views/widgets.py`: cabecera retro, footer y tabla de usuarios.
- [ ] `src/views/screens.py`: `MainScreen`, panel de detalle y modales
      (`CreateUserModal`, `EditUserModal`, `ConfirmDeleteModal`, `HelpModal`).
- [ ] `src/main.py`: arranque de la `App`, alerta de privilegios y cableado.
- [ ] Validación POSIX en formularios y pantalla de aviso sin privilegios.
- [ ] Pruebas del backend con `unittest`/`pytest`.

## Desarrollo

```bash
# Comprobar que todos los módulos compilan
python -m compileall -q src

# Listar usuarios desde el backend
python - <<'PY'
from src.controllers.user_manager import SystemUserManager

for user in SystemUserManager.get_all_users(include_system=False)[:10]:
    print(user["uid"], user["username"], user["group"], user["shell"])
PY
```
