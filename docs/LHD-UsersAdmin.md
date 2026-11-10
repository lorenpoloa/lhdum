Proyecto: Linux User Manager TUI (lum-tui)
Este documento define la especificación técnica completa para implementar una herramienta de gestión de usuarios en Linux con interfaz de consola TUI, desarrollada en Python 3.10+ mediante el framework Textual.
La arquitectura desacopla completamente la lógica del sistema, los widgets visuales y la configuración de estilos, permitiendo la integración futura con un tema global de escritorio mediante un archivo de configuración JSON local.
1. Arquitectura General y Estructura de Archivos
El proyecto seguirá un patrón MVC (Modelo-Vista-Controlador) estricto:
Plaintext
lum-tui/
├── config/
│   └── app_style.json       # Parámetros de estilo (simula la inyección del tema global)
├── src/
│   ├── __init__.py
│   ├── main.py              # Punto de entrada de la aplicación
│   ├── models/
│   │   ├── __init__.py
│   │   └── sys_user.py      # Modelo de datos y wrapper del sistema (/etc/passwd, shadow, group)
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── user_manager.py  # Lógica de negocio y ejecución de comandos seguras (useradd, usermod)
│   ├── views/
│   │   ├── __init__.py
│   │   ├── screens.py       # Pantalla principal (MainScreen) y Modales (Create, Edit, Confirm)
│   │   └── widgets.py       # Componentes personalizados (Header retro, Footer, UserTable)
│   └── utils/
│       ├── __init__.py
│       └── theme_loader.py  # Inyector de app_style.json a CSS de Textual
├── requirements.txt
└── README.md
2. Archivo de Configuración de Estilo (config/app_style.json)
Para cumplir con el requerimiento de personalización visual externa (que será gobernada por el escritorio), la aplicación consumirá este archivo para generar el CSS dinámico de Textual al arrancar:
JSON
{
  "theme_name": "retro-cyberpunk",
  "palette": {
    "background": "#1e1e2e",
    "surface": "#252538",
    "surface_focus": "#313244",
    "primary": "#89b4fa",
    "secondary": "#cba6f7",
    "accent": "#f38ba8",
    "text": "#cdd6f4",
    "text_muted": "#6c7086",
    "border": "#45475a",
    "border_focus": "#89b4fa",
    "success": "#a6e3a1",
    "warning": "#f9e2af",
    "error": "#f38ba8"
  },
  "typography": {
    "font_style": "bold"
  },
  "borders": {
    "type": "round",
    "panel_type": "solid"
  },
  "table": {
    "row_odd_background": "#1e1e2e",
    "row_even_background": "#181825",
    "cursor_background": "#313244",
    "cursor_foreground": "#89b4fa"
  }
}
3. Especificación de Componentes y Requisitos de Código
A. Cargador de Temas (src/utils/theme_loader.py)
Debe traducir el archivo app_style.json a una cadena CSS compatible con Textual e inyectarla en la aplicación:
Python
import json
from pathlib import Path

def load_tcss_from_config(config_path: str = "config/app_style.json") -> str:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuración no encontrada en {config_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    p = cfg["palette"]
    b = cfg["borders"]
    t = cfg["table"]

    # Inyección directa de variables de color y estilos de widgets
    tcss = f"""
    Screen {{
        background: {p['background']};
        color: {p['text']};
    }}
    
    Header {{
        background: {p['surface']};
        color: {p['primary']};
        border-bottom: {b['type']} {p['border']};
    }}
    
    Footer {{
        background: {p['surface']};
        color: {p['text_muted']};
    }}

    #action_bar {{
        height: 3;
        background: {p['surface']};
        border-bottom: {b['type']} {p['border']};
        padding: 0 1;
    }}

    DataTable {{
        background: {p['background']};
        color: {p['text']};
        border: {b['type']} {p['border']};
    }}

    DataTable > .datatable--header {{
        background: {p['surface']};
        color: {p['secondary']};
        text-style: bold;
    }}

    DataTable > .datatable--cursor {{
        background: {t['cursor_background']};
        color: {t['cursor_foreground']};
        text-style: bold;
    }}

    #detail_panel {{
        height: 6;
        background: {p['surface']};
        border: {b['type']} {p['border']};
        margin: 1 0;
        padding: 0 1;
    }}

    ModalScreen {{
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }}

    #dialog {{
        width: 60;
        height: auto;
        background: {p['surface']};
        border: {b['type']} {p['border_focus']};
        padding: 1 2;
    }}
    """
    return tcss
B. Capa de Abstracción de Sistema (src/controllers/user_manager.py)
Encapsula la lectura y ejecución de operaciones del sistema Linux. Debe utilizar subprocess.run con check=True y captura de excepciones.
Python
import pwd
import grp
import subprocess
from typing import List, Dict, Any

class SystemUserManager:
    @staticmethod
    def get_all_users() -> List[Dict[str, Any]]:
        """Lee usuarios locales filtrando cuentas de sistema si es necesario."""
        users = []
        for entry in pwd.getpwall():
            # Obtener grupo principal
            try:
                main_group = grp.getgrgid(entry.pw_gid).gr_name
            except KeyError:
                main_group = str(entry.pw_gid)

            users.append({
                "username": entry.pw_name,
                "uid": entry.pw_uid,
                "gid": entry.pw_gid,
                "group": main_group,
                "home": entry.pw_dir,
                "shell": entry.pw_shell,
                "is_system": entry.pw_uid < 1000 and entry.pw_uid != 0
            })
        return sorted(users, key=lambda x: x["uid"])

    @staticmethod
    def create_user(username: str, shell: str, home: str, groups: List[str]) -> bool:
        cmd = ["sudo", "useradd", "-m", "-s", shell]
        if home:
            cmd.extend(["-d", home])
        if groups:
            cmd.extend(["-G", ",".join(groups)])
        cmd.append(username)
        
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip())
        return True

    @staticmethod
    def delete_user(username: str, remove_home: bool = False) -> bool:
        cmd = ["sudo", "userdel"]
        if remove_home:
            cmd.append("-r")
        cmd.append(username)
        
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip())
        return True
C. Aplicación Principal y Pantallas (src/main.py y src/views/screens.py)
Especificación de eventos de teclado (estilo HTOP/OpenCode):
F1 / ?: Mostrar diálogo de ayuda / atajos.
F2 / a: Abrir modal "Nuevo Usuario".
F3 / e: Abrir modal "Editar Usuario".
F4 / d: Abrir modal de confirmación "Eliminar Usuario".
F5 / r: Recargar lista de usuarios.
/ / Ctrl+F: Enfocar la barra de búsqueda rápida.
q / Esc: Salir de la aplicación.
Python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static, Input, Button
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen

from utils.theme_loader import load_tcss_from_config
from controllers.user_manager import SystemUserManager

class MainScreen(App):
    BINDINGS = [
        ("f1", "help", "Ayuda"),
        ("f2", "create_user", "Crear"),
        ("f3", "edit_user", "Editar"),
        ("f4", "delete_user", "Eliminar"),
        ("f5", "refresh", "Recargar"),
        ("q", "quit", "Salir"),
    ]

    def __init__(self):
        super().__init__()
        # Cargar estilos desde la configuración
        self.CSS = load_tcss_from_config()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # Barra superior de acciones y búsqueda rápida estilo OpenCode
        with Horizontal(id="action_bar"):
            yield Input(placeholder="🔍 Buscar por usuario o UID...", id="search_input")
            yield Button("+ Nuevo", id="btn_create", variant="success")
            yield Button("🗑️ Eliminar", id="btn_delete", variant="error")

        # Tabla densa estilo HTOP
        yield DataTable(id="user_table")

        # Panel inferior de inspección rápida
        with Vertical(id="detail_panel"):
            yield Static("Detalles del usuario seleccionado:", id="detail_title")
            yield Static("Seleccione un usuario de la lista...", id="detail_content")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("UID", "Usuario", "Grupo", "Directorio Home", "Shell")
        self.load_users()

    def load_users(self, filter_text: str = "") -> None:
        table = self.query_one(DataTable)
        table.clear()
        users = SystemUserManager.get_all_users()
        
        for u in users:
            if filter_text.lower() in u["username"].lower() or str(u["uid"]).startswith(filter_text):
                table.add_row(
                    str(u["uid"]),
                    u["username"],
                    u["group"],
                    u["home"],
                    u["shell"],
                    key=u["username"]
                )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Actualiza el panel de detalles al mover el cursor en la tabla."""
        username = event.row_key.value
        # Lógica para cargar detalles adicionales en #detail_content
        detail_widget = self.query_one("#detail_content", Static)
        detail_widget.update(f"Usuario activo: [bold]{username}[/bold] | Status: OK")

    def action_refresh((self) -> None:
        self.load_users()

if __name__ == "__main__":
    app = MainScreen()
    app.run()
4. Instrucciones de Implementación para el Agente (Copilot / OpenCode)
Al entregar este prompt/documento al agente de código, indícale las siguientes reglas de trabajo:
Creación del entorno: Inicializar requirements.txt con textual>=0.40.0.
Desacoplamiento visual: Asegurarse de que ningún widget contenga estilos CSS hardcodeados en el código Python; todos los colores, márgenes y bordes deben definirse a través de la función load_tcss_from_config().
Gestión de Errores y Privilegios:
Si la herramienta no se ejecuta con sudo o privilegios root, debe mostrar una pantalla de advertencia inicial (Alert Screen) amigable en la TUI en lugar de fallar con un rastreo de pila (stack trace).
Validar que los nombres de usuario introducidos en los modales cumplan con la sintaxis POSIX (^[a-z_][a-z0-9_-]*\$?).
Formularios Modales: Implementar CreateUserModal heredando de ModalScreen con inputs para Nombre de usuario, Shell (con un Select conteniendo /bin/bash, /bin/zsh, /bin/sh, /usr/sbin/nologin) y casillas de verificación (Checkbox) para creación de directorio home.
