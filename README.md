# lhdum — Linux Hybrid Desktop Users Manager

Herramienta de consola para administrar usuarios locales de Linux desde una
interfaz TUI construida con [Textual](https://textual.textualize.io/). El
objetivo es ofrecer una experiencia rápida y densa, inspirada en `htop`, con
búsqueda incremental, panel de inspección y operaciones de alta/baja de
usuarios ejecutadas de forma segura.

La especificación técnica completa está en
[`docs/LHD-UsersAdmin.md`](docs/LHD-UsersAdmin.md).

> **Estado actual.** La aplicación está funcional: estructura MVC, tema externo,
> backend Linux, pantalla principal, búsqueda, panel de detalle y modales de
> alta, edición, eliminación y ayuda. La pantalla de aviso de privilegios
> permite continuar en modo solo lectura. Quedan pendientes las pruebas
> automatizadas.

## Características

- Listado de usuarios locales leído desde `pwd` y `grp`, ordenado por UID.
- Tabla densa estilo `htop` con cursor por filas y *zebra stripes*.
- Búsqueda incremental por usuario, UID, grupo, home o shell.
- Panel inferior con UID/GID, grupo, home, shell, grupos y tipo de cuenta.
- Alta de usuarios mediante `useradd`.
- Edición de shell y grupos secundarios mediante `usermod`.
- Baja de usuarios mediante `userdel`, con opción de borrar el home (`-r`).
- Atajos de teclado tipo `htop`/OpenCode (`F1`–`F5`, `/`, `q`, `Esc`).
- Tema visual externalizado: ningún color, borde o margen está codificado en
  los widgets; todo se genera desde `config/app_style.json`.
- Aviso amigable en la TUI cuando faltan privilegios, con opción de reintentar
  (`sudo -v`), continuar en modo solo lectura o salir.
- Validación POSIX de nombres de usuario y grupos antes de tocar el sistema.

## Stack

- Python 3.10+
- [Textual](https://textual.textualize.io/) (`>=0.40.0`; probado con `0.40.0`
  y `8.2.8`)
- Utilidades estándar de Linux: `pwd`, `grp`, `subprocess`, `useradd`,
  `usermod`, `userdel`
- `sudo` para elevación de privilegios (o ejecución directa como root)

## Instalación

```bash
git clone https://github.com/lorenpoloa/lhdum.git
cd lhdum

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> En Debian/Ubuntu puede ser necesario instalar antes `python3-venv`:
> `sudo apt install python3-venv`.

## Ejecución

La aplicación necesita privilegios para crear, editar o eliminar usuarios, pero
no para leerlos. El modo recomendado es cachear la credencial de `sudo` y
ejecutar la TUI como usuario normal:

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
una regla `NOPASSWD`, aparece un modal de aviso con tres opciones:

- **Reintentar**: vuelve a comprobar los privilegios (útil tras `sudo -v`).
- **Solo lectura**: permite consultar y buscar usuarios, pero deshabilita las
  acciones de escritura.
- **Salir**: cierra la aplicación.

> Ejecutar la TUI completa como root funciona, pero no es el modo recomendado:
> es preferible `sudo -v` y arrancar `lhdum` con el usuario normal.

La interfaz está pensada para terminales de al menos **80×24**; los modales se
adaptan y hacen scroll si la altura es menor.

## Atajos de teclado

| Tecla | Acción |
| --- | --- |
| `F1` / `?` | Ayuda y lista de atajos |
| `F2` / `a` | Nuevo usuario |
| `F3` / `e` | Editar usuario seleccionado |
| `F4` / `d` | Eliminar usuario seleccionado (con confirmación) |
| `F5` / `r` | Recargar lista |
| `/` / `Ctrl+F` | Enfocar búsqueda rápida |
| `q` / `Esc` | Salir |

La búsqueda filtra en vivo por usuario, UID, grupo, home y shell. El panel
inferior se actualiza al mover el cursor por la tabla.

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
arranque. Además, `build_textual_theme()` registra la misma paleta como tema
nativo de Textual (en versiones que lo soportan), de modo que el command
palette, el panel de ayuda, las notificaciones y los scrollbars usan los mismos
colores que la pantalla principal. El selector de temas de Textual se oculta
para que la apariencia siga dependiendo únicamente de `app_style.json`.

Se puede usar una configuración alternativa sin tocar código:

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
lhdum/
├── config/
│   └── app_style.json        # Paleta y parámetros visuales externos
├── docs/
│   └── LHD-UsersAdmin.md     # Especificación técnica
├── src/
│   ├── __init__.py
│   ├── main.py               # Punto de entrada
│   ├── models/
│   │   └── sys_user.py       # Modelo de usuario (ampliación futura)
│   ├── controllers/
│   │   └── user_manager.py   # Backend Linux: pwd/grp/useradd/usermod/userdel
│   ├── views/
│   │   ├── screens.py        # MainScreen y modales
│   │   └── widgets.py        # RetroHeader, LhdumFooter y UserTable
│   └── utils/
│       └── theme_loader.py   # JSON -> TCSS y tema nativo de Textual
├── requirements.txt
└── README.md
```

### Capa de sistema (`src/controllers/user_manager.py`)

`SystemUserManager` expone:

- `get_all_users(include_system=True)`: lista usuarios desde `pwd`, resuelve el
  grupo primario con `grp` y marca las cuentas de sistema.
- `get_user(username)`, `user_exists(username)` y `get_user_groups(username)`.
- `get_supplementary_groups(username)`: grupos secundarios sin el primario.
- `get_available_shells()`: shells para el selector del formulario.
- `create_user(...)`: ejecuta `useradd` con argumentos validados.
- `modify_user(username, shell=None, groups=None)`: ejecuta `usermod`.
- `delete_user(username, remove_home=False)`: ejecuta `userdel`; protege `root`
  y la cuenta desde la que se ejecuta la aplicación.
- `check_privileges()` / `has_privileges()`: comprobación previa de root o sudo.

Errores tipados: `UserValidationError`, `UserNotFoundError`,
`UserAlreadyExistsError`, `PrivilegeError` y `UserOperationError`.

### Interfaz (`src/views/`)

- `MainScreen`: aplicación Textual con cabecera, barra de acciones, tabla,
  panel de detalle y footer.
- `RetroHeader`, `LhdumFooter` y `UserTable`: widgets reutilizables.
- `CreateUserModal`: nombre, shell, grupos secundarios y creación de home.
- `EditUserModal`: shell y grupos secundarios.
- `ConfirmDeleteModal`: confirmación y borrado opcional del home.
- `HelpModal`: ayuda con los atajos.
- `PrivilegeAlertModal`: aviso de privilegios con reintento y modo solo lectura.

## Seguridad

- **Sin `shell=True`**: todos los comandos se construyen como listas de
  argumentos, evitando inyección de shell.
- **Validación POSIX** de nombres de usuario y grupos:
  `^[a-z_][a-z0-9_-]*\$?$`, con límite de 32 caracteres.
- **Validación de rutas** de shell y home antes de invocar `useradd`.
- **`sudo -n`**: nunca se solicita contraseña dentro de la TUI.
- **Cuentas protegidas**: no se puede eliminar `root` ni el usuario actual, y
  `root` tampoco se modifica desde la interfaz.
- **Errores controlados**: los fallos de `sudo`/`useradd`/`usermod`/`userdel` se
  traducen a excepciones de dominio con mensajes claros.
- **Modo solo lectura** cuando no hay privilegios, sin trazas de pila.

## Roadmap

- [x] Estructura MVC y `requirements.txt`.
- [x] `config/app_style.json` y `src/utils/theme_loader.py`.
- [x] `SystemUserManager` con lectura y operaciones seguras.
- [x] `src/views/widgets.py`: cabecera retro, footer y tabla de usuarios.
- [x] `src/views/screens.py`: `MainScreen`, panel de detalle y modales.
- [x] `src/main.py`: arranque de la `App`, alerta de privilegios y cableado.
- [x] Validación POSIX en formularios y pantalla de aviso sin privilegios.
- [ ] `src/models/sys_user.py`: modelo de datos tipado para futuras vistas.
- [ ] Pruebas automatizadas del backend y de los formularios.

## Desarrollo

```bash
# Comprobar que todos los módulos compilan
python -m compileall -q src

# Arrancar la aplicación
python -m src.main

# Listar usuarios desde el backend
python - <<'PY'
from src.controllers.user_manager import SystemUserManager

for user in SystemUserManager.get_all_users(include_system=False)[:10]:
    print(user["uid"], user["username"], user["group"], user["shell"])
PY
```
