"""Pantallas y modales de lum-tui.

``MainScreen`` es la aplicación Textual principal. Los modales se encargan de
recoger y validar la entrada del usuario; las operaciones reales sobre el
sistema se delegan en :class:`SystemUserManager`.
"""

from __future__ import annotations

from typing import Any

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static

from src.controllers.user_manager import (
    PROTECTED_USERS,
    PrivilegeError,
    SystemUserManager,
    UserManagerError,
    UserValidationError,
)
from src.utils.theme_loader import build_textual_theme, load_tcss_from_config
from src.views.widgets import LumFooter, RetroHeader, UserTable

HELP_TEXT = """\
[bold]F1[/bold] / [bold]?[/bold]        Ayuda y atajos
[bold]F2[/bold] / [bold]a[/bold]        Nuevo usuario
[bold]F3[/bold] / [bold]e[/bold]        Editar usuario
[bold]F4[/bold] / [bold]d[/bold]        Eliminar usuario
[bold]F5[/bold] / [bold]r[/bold]        Recargar lista
[bold]/[/bold] / [bold]Ctrl+F[/bold]   Enfocar búsqueda rápida
[bold]q[/bold] / [bold]Esc[/bold]      Salir

La búsqueda filtra por usuario, UID, grupo, home y shell.
El panel inferior muestra los detalles del usuario bajo el cursor.\
"""

PRIVILEGE_TEXT = """\
lum-tui puede leer los usuarios del sistema, pero no crear ni eliminar
cuentas porque el proceso no se ejecuta como root y sudo no tiene
credenciales cacheadas.

Ejecuta [bold]sudo -v[/bold] en otra terminal y pulsa [bold]Reintentar[/bold],
o continúa en [bold]modo solo lectura[/bold].\
"""


class CreateUserModal(ModalScreen[dict[str, Any] | None]):
    """Formulario modal para crear un usuario local."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        shells = [(shell, shell) for shell in SystemUserManager.get_available_shells()]

        with Vertical(id="dialog"):
            yield Static("Nuevo usuario", classes="dialog_title")
            yield Static("Nombre de usuario", classes="field_label")
            yield Input(placeholder="ej. ana", id="username")
            yield Static("Shell de login", classes="field_label")
            yield Select(
                shells,
                value="/bin/bash",
                allow_blank=False,
                id="shell",
            )
            yield Static(
                "Grupos secundarios (separados por comas)",
                classes="field_label",
            )
            yield Input(placeholder="sudo,docker (opcional)", id="groups")
            yield Checkbox(
                "Crear directorio home (-m)",
                id="create_home",
                value=True,
            )
            yield Static("", id="form_error")
            with Horizontal(id="dialog_buttons"):
                yield Button("Cancelar", id="btn_cancel")
                yield Button("Crear", id="btn_submit", variant="success")

    def on_mount(self) -> None:
        self.query_one("#username", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_submit":
            self._submit()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _show_error(self, message: str) -> None:
        self.query_one("#form_error", Static).update(message)

    def _submit(self) -> None:
        username = self.query_one("#username", Input).value.strip()
        shell = self.query_one("#shell", Select).value
        groups_raw = self.query_one("#groups", Input).value
        groups = [part.strip() for part in groups_raw.split(",") if part.strip()]

        if not isinstance(shell, str) or not shell:
            self._show_error("Selecciona una shell válida.")
            return

        try:
            SystemUserManager.validate_username(username)
            SystemUserManager.validate_shell(shell)
            groups = SystemUserManager.validate_groups(groups)
        except UserValidationError as exc:
            self._show_error(str(exc))
            return

        self.dismiss(
            {
                "username": username,
                "shell": shell,
                "groups": groups,
                "create_home": self.query_one("#create_home", Checkbox).value,
            }
        )


class EditUserModal(ModalScreen[dict[str, Any] | None]):
    """Formulario modal para editar shell y grupos secundarios."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, user: dict[str, Any], groups: list[str]) -> None:
        super().__init__()
        self._user = user
        self._groups = groups

    def compose(self) -> ComposeResult:
        shell_values = SystemUserManager.get_available_shells()
        current_shell = self._user["shell"]
        if current_shell not in shell_values:
            shell_values.append(current_shell)

        shells = [(shell, shell) for shell in shell_values]

        with Vertical(id="dialog"):
            yield Static(
                f"Editar usuario {escape(self._user['username'])}",
                classes="dialog_title",
            )
            yield Static("Nombre de usuario", classes="field_label")
            yield Input(
                value=self._user["username"],
                id="username",
                disabled=True,
            )
            yield Static("Shell de login", classes="field_label")
            yield Select(
                shells,
                value=current_shell,
                allow_blank=False,
                id="shell",
            )
            yield Static(
                "Grupos secundarios (separados por comas)",
                classes="field_label",
            )
            yield Input(
                value=", ".join(self._groups),
                placeholder="sudo,docker (opcional)",
                id="groups",
            )
            yield Static("", id="form_error")
            with Horizontal(id="dialog_buttons"):
                yield Button("Cancelar", id="btn_cancel")
                yield Button("Guardar", id="btn_submit", variant="success")

    def on_mount(self) -> None:
        self.query_one("#shell", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_submit":
            self._submit()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _show_error(self, message: str) -> None:
        self.query_one("#form_error", Static).update(message)

    def _submit(self) -> None:
        username = self._user["username"]
        shell = self.query_one("#shell", Select).value
        groups_raw = self.query_one("#groups", Input).value
        groups = [part.strip() for part in groups_raw.split(",") if part.strip()]

        if not isinstance(shell, str) or not shell:
            self._show_error("Selecciona una shell válida.")
            return

        try:
            SystemUserManager.validate_username(username)
            SystemUserManager.validate_shell(shell)
            groups = SystemUserManager.validate_groups(groups)
        except UserValidationError as exc:
            self._show_error(str(exc))
            return

        self.dismiss(
            {
                "username": username,
                "shell": shell,
                "groups": groups,
            }
        )


class ConfirmDeleteModal(ModalScreen[dict[str, Any] | None]):
    """Confirmación modal para eliminar un usuario."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, username: str) -> None:
        super().__init__()
        self._username = username

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(
                f"Eliminar usuario {escape(self._username)}",
                classes="dialog_title",
            )
            yield Static(
                "Esta acción no se puede deshacer. La cuenta se eliminará del "
                "sistema mediante userdel.",
                classes="dialog_text",
            )
            yield Checkbox(
                "Eliminar también el directorio home y el correo (-r)",
                id="remove_home",
                value=False,
            )
            with Horizontal(id="dialog_buttons"):
                yield Button("Cancelar", id="btn_cancel")
                yield Button("Eliminar", id="btn_confirm_delete", variant="error")

    def on_mount(self) -> None:
        self.query_one("#btn_cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_confirm_delete":
            self.dismiss(
                {"remove_home": self.query_one("#remove_home", Checkbox).value}
            )

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpModal(ModalScreen[None]):
    """Diálogo de ayuda con los atajos de teclado."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cerrar", show=False),
        Binding("question_mark", "dismiss_modal", "Cerrar", show=False),
        Binding("f1", "dismiss_modal", "Cerrar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Atajos de teclado", classes="dialog_title")
            yield Static(HELP_TEXT, id="help_text")
            with Horizontal(id="dialog_buttons"):
                yield Button("Cerrar", id="btn_close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#btn_close", Button).focus()

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class PrivilegeAlertModal(ModalScreen[str]):
    """Aviso inicial cuando no hay privilegios para modificar usuarios."""

    BINDINGS = [
        Binding("escape", "quit_app", "Salir", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Privilegios insuficientes", classes="dialog_title")
            yield Static(PRIVILEGE_TEXT, id="alert_message")
            with Horizontal(id="dialog_buttons"):
                yield Button("Salir", id="btn_quit", variant="error")
                yield Button("Solo lectura", id="btn_readonly")
                yield Button("Reintentar", id="btn_retry", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#btn_retry", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_quit":
            self.dismiss("quit")
        elif event.button.id == "btn_readonly":
            self.dismiss("readonly")
        elif event.button.id == "btn_retry":
            self._retry()

    def action_quit_app(self) -> None:
        self.dismiss("quit")

    def _retry(self) -> None:
        try:
            SystemUserManager.check_privileges()
        except PrivilegeError as exc:
            self.query_one("#alert_message", Static).update(
                "[bold]Todavía no hay privilegios suficientes.[/bold]\n\n"
                + escape(str(exc))
            )
        else:
            self.dismiss("privileged")


class MainScreen(App):
    """Aplicación principal de lum-tui."""

    TITLE = "lum-tui"
    SUB_TITLE = "Linux User Manager"

    BINDINGS = [
        Binding("f1", "help", "Ayuda"),
        Binding("question_mark", "help", "Ayuda", show=False),
        Binding("f2", "create_user", "Crear"),
        Binding("a", "create_user", "Crear", show=False),
        Binding("f3", "edit_user", "Editar"),
        Binding("e", "edit_user", "Editar", show=False),
        Binding("f4", "delete_user", "Eliminar"),
        Binding("d", "delete_user", "Eliminar", show=False),
        Binding("f5", "refresh", "Recargar"),
        Binding("r", "refresh", "Recargar", show=False),
        Binding("slash", "focus_search", "Buscar", show=False),
        Binding("ctrl+f", "focus_search", "Buscar", show=False),
        Binding("q", "quit", "Salir"),
        Binding("escape", "quit", "Salir", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.CSS = load_tcss_from_config()
        # La misma paleta se registra como tema de Textual para que los
        # componentes internos (command palette, ayuda, notificaciones...)
        # usen los colores del JSON y no el tema por defecto.
        theme = build_textual_theme()
        if theme is not None and hasattr(self, "register_theme"):
            self.register_theme(theme)
            self.theme = theme.name
        self._users: list[dict[str, Any]] = []
        self._privileged = False

    def compose(self) -> ComposeResult:
        yield RetroHeader(show_clock=True)

        with Horizontal(id="action_bar"):
            yield Input(
                placeholder="Buscar por usuario, UID, grupo, home o shell...",
                id="search_input",
            )
            yield Button("+ Nuevo", id="btn_create", variant="success")
            yield Button("Editar", id="btn_edit")
            yield Button("Eliminar", id="btn_delete", variant="error")
            yield Button("Recargar", id="btn_refresh")

        yield UserTable()

        with Vertical(id="detail_panel"):
            yield Static(
                "Detalles del usuario seleccionado:",
                id="detail_title",
            )
            yield Static(
                "Seleccione un usuario de la lista...",
                id="detail_content",
            )

        yield LumFooter()

    def on_mount(self) -> None:
        self._privileged = SystemUserManager.has_privileges()
        # En Textual 0.40 el árbol de widgets aún puede estar terminando de
        # montarse cuando se ejecuta App.on_mount; se difiere la carga.
        self.call_after_refresh(self._initial_load)

    def _initial_load(self) -> None:
        self.load_users()
        self._set_privileged(self._privileged)
        self.query_one(UserTable).focus()

        if not self._privileged:
            self.push_screen(
                PrivilegeAlertModal(),
                self._on_privilege_result,
            )

    def get_system_commands(self, screen: Any):
        """Oculta el selector de temas de Textual.

        La apariencia la define ``config/app_style.json``; permitir cambiar a
        otro tema solo desincronizaría los componentes internos de Textual.
        """

        get_commands = getattr(super(), "get_system_commands", None)
        if get_commands is None:
            return

        for command in get_commands(screen):
            if command.title.lower() != "theme":
                yield command

    # ------------------------------------------------------------------
    # Carga y filtrado
    # ------------------------------------------------------------------
    def load_users(self) -> None:
        try:
            self._users = SystemUserManager.get_all_users()
        except UserManagerError as exc:
            self._users = []
            self.notify(
                str(exc),
                title="Error al leer usuarios",
                severity="error",
                timeout=8,
            )
        self._apply_filter()

    def _apply_filter(self) -> None:
        try:
            table = self.query_one(UserTable)
            search = self.query_one("#search_input", Input)
        except NoMatches:
            return

        table.populate(self._users, search.value)
        self._update_status()

        selected = table.selected_username
        if selected:
            self._update_details(selected)
        else:
            self._clear_details()

    def _update_status(self) -> None:
        try:
            table = self.query_one(UserTable)
        except NoMatches:
            return

        total = len(self._users)
        shown = table.row_count
        mode = "root/sudo" if self._privileged else "solo lectura"
        count = (
            f"{total} usuarios"
            if shown == total
            else f"{shown} de {total} usuarios"
        )
        self.sub_title = f"{count} · {mode}"

    def _update_details(self, username: str) -> None:
        user = next(
            (item for item in self._users if item["username"] == username),
            None,
        )
        if user is None:
            self._clear_details()
            return

        try:
            groups = SystemUserManager.get_user_groups(username)
        except UserManagerError:
            groups = [user["group"]]

        kind = "Cuenta de sistema" if user["is_system"] else "Cuenta estándar"
        content = (
            f"UID [bold]{user['uid']}[/bold]  ·  "
            f"GID [bold]{user['gid']}[/bold]  ·  "
            f"Grupo [bold]{escape(user['group'])}[/bold]  ·  {kind}\n"
            f"Home: {escape(user['home'])}\n"
            f"Shell: {escape(user['shell'])}\n"
            f"Grupos: {escape(', '.join(groups))}"
        )

        try:
            detail = self.query_one("#detail_content", Static)
        except NoMatches:
            return
        detail.update(content)

    def _clear_details(self) -> None:
        try:
            detail = self.query_one("#detail_content", Static)
        except NoMatches:
            return
        detail.update("Seleccione un usuario de la lista...")

    # ------------------------------------------------------------------
    # Eventos de widgets
    # ------------------------------------------------------------------
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search_input":
            self._apply_filter()

    def on_data_table_row_highlighted(
        self,
        event: DataTable.RowHighlighted,
    ) -> None:
        username = event.row_key.value
        if username:
            self._update_details(username)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn_create":
            self.action_create_user()
        elif button_id == "btn_edit":
            self.action_edit_user()
        elif button_id == "btn_delete":
            self.action_delete_user()
        elif button_id == "btn_refresh":
            self.action_refresh()

    # ------------------------------------------------------------------
    # Acciones / atajos
    # ------------------------------------------------------------------
    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_create_user(self) -> None:
        if not self._require_privileges():
            return
        self.push_screen(CreateUserModal(), self._on_create_result)

    def action_edit_user(self) -> None:
        username = self.query_one(UserTable).selected_username
        if not username:
            self._notify_no_selection()
            return
        if username in PROTECTED_USERS:
            self._notify_protected(username)
            return
        if not self._require_privileges():
            return

        try:
            user = SystemUserManager.get_user(username)
            groups = SystemUserManager.get_supplementary_groups(username)
        except UserManagerError as exc:
            self._notify_error_to_user(exc)
            return

        self.push_screen(
            EditUserModal(user, groups),
            self._on_edit_result,
        )

    def action_delete_user(self) -> None:
        username = self.query_one(UserTable).selected_username
        if not username:
            self._notify_no_selection()
            return
        if username in PROTECTED_USERS:
            self._notify_protected(username)
            return
        if not self._require_privileges():
            return

        self.push_screen(
            ConfirmDeleteModal(username),
            lambda result: self._on_delete_result(username, result),
        )

    def action_refresh(self) -> None:
        self.load_users()

    def action_focus_search(self) -> None:
        search = self.query_one("#search_input", Input)
        search.focus()
        search.cursor_position = len(search.value)

    def action_quit(self) -> None:
        self.exit()

    # ------------------------------------------------------------------
    # Utilidades de estado y errores
    # ------------------------------------------------------------------
    def _require_privileges(self) -> bool:
        if self._privileged:
            return True

        self.notify(
            "La aplicación está en modo solo lectura. Ejecuta 'sudo -v' y "
            "reinicia lum-tui para poder modificar usuarios.",
            title="Privilegios insuficientes",
            severity="warning",
            timeout=8,
        )
        return False

    def _notify_no_selection(self) -> None:
        self.notify(
            "Selecciona primero un usuario en la tabla.",
            title="Sin selección",
            severity="warning",
            timeout=5,
        )

    def _notify_protected(self, username: str) -> None:
        self.notify(
            f"La cuenta '{username}' está protegida y no se puede modificar.",
            title="Acción no permitida",
            severity="warning",
            timeout=6,
        )

    def _set_privileged(self, privileged: bool) -> None:
        self._privileged = privileged
        for button_id in ("btn_create", "btn_edit", "btn_delete"):
            try:
                button = self.query_one(f"#{button_id}", Button)
            except NoMatches:
                continue
            button.disabled = not privileged
        self._update_status()

    def _on_privilege_result(self, result: str | None) -> None:
        if result == "quit":
            self.exit()
            return

        if result == "privileged":
            self._set_privileged(True)
            self.notify(
                "Privilegios verificados. Modo administrador activo.",
                title="lum-tui",
                severity="information",
                timeout=5,
            )
            return

        self._set_privileged(False)
        self.notify(
            "Continuando en modo solo lectura.",
            title="lum-tui",
            severity="warning",
            timeout=5,
        )

    def _on_create_result(self, result: dict[str, Any] | None) -> None:
        if not result:
            return

        try:
            SystemUserManager.create_user(
                username=result["username"],
                shell=result["shell"],
                groups=result["groups"],
                create_home=result["create_home"],
            )
        except PrivilegeError as exc:
            self._set_privileged(False)
            self._notify_error_to_user(exc)
            return
        except UserManagerError as exc:
            self._notify_error_to_user(exc)
            return

        self.notify(
            f"Usuario '{result['username']}' creado.",
            title="Alta completada",
            severity="information",
            timeout=5,
        )
        self.load_users()
        table = self.query_one(UserTable)
        table.select_username(result["username"])
        table.focus()

    def _on_edit_result(self, result: dict[str, Any] | None) -> None:
        if not result:
            return

        try:
            SystemUserManager.modify_user(
                result["username"],
                shell=result["shell"],
                groups=result["groups"],
            )
        except PrivilegeError as exc:
            self._set_privileged(False)
            self._notify_error_to_user(exc)
            return
        except UserManagerError as exc:
            self._notify_error_to_user(exc)
            return

        self.notify(
            f"Usuario '{result['username']}' actualizado.",
            title="Edición completada",
            severity="information",
            timeout=5,
        )
        self.load_users()
        table = self.query_one(UserTable)
        table.select_username(result["username"])
        table.focus()

    def _on_delete_result(
        self,
        username: str,
        result: dict[str, Any] | None,
    ) -> None:
        if not result:
            return

        try:
            SystemUserManager.delete_user(
                username,
                remove_home=result["remove_home"],
            )
        except PrivilegeError as exc:
            self._set_privileged(False)
            self._notify_error_to_user(exc)
            return
        except UserManagerError as exc:
            self._notify_error_to_user(exc)
            return

        self.notify(
            f"Usuario '{username}' eliminado.",
            title="Baja completada",
            severity="information",
            timeout=5,
        )
        self._clear_details()
        self.load_users()
        self.query_one(UserTable).focus()

    def _notify_error_to_user(self, exc: Exception) -> None:
        self.notify(
            str(exc),
            title="No se pudo completar la operación",
            severity="error",
            timeout=10,
        )
