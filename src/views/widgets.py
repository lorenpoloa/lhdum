"""Widgets personalizados de lhdum.

La apariencia de todos los componentes proviene exclusivamente de
:func:`src.utils.theme_loader.load_tcss_from_config`; aquí solo se define la
estructura y el comportamiento.
"""

from __future__ import annotations

from typing import Any, Iterable

from textual.widgets import DataTable, Footer, Header
from textual.widgets.data_table import CellDoesNotExist, RowDoesNotExist


class RetroHeader(Header):
    """Cabecera de la aplicación con reloj, estilo retro."""

    def __init__(self, *, show_clock: bool = True, **kwargs: Any) -> None:
        super().__init__(show_clock=show_clock, **kwargs)


class LhdumFooter(Footer):
    """Footer estándar de Textual; los colores vienen del tema externo."""


class UserTable(DataTable):
    """Tabla densa de usuarios con cursor por filas y búsqueda incremental."""

    def __init__(self, *, id: str | None = "user_table", **kwargs: Any) -> None:
        super().__init__(
            id=id,
            cursor_type="row",
            zebra_stripes=True,
            show_row_labels=False,
            cell_padding=1,
            **kwargs,
        )

    def on_mount(self) -> None:
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Añade las columnas una sola vez, antes de cargar filas."""

        if self.columns:
            return

        self.add_column("UID", key="uid", width=7)
        self.add_column("Usuario", key="username", width=18)
        self.add_column("Grupo", key="group", width=16)
        self.add_column("Home", key="home", width=26)
        self.add_column("Shell", key="shell", width=22)

    @property
    def selected_username(self) -> str | None:
        """Nombre del usuario bajo el cursor, o ``None`` si no hay filas."""

        if self.row_count == 0:
            return None

        try:
            cell_key = self.coordinate_to_cell_key(self.cursor_coordinate)
        except CellDoesNotExist:
            return None

        return cell_key.row_key.value

    def select_username(self, username: str) -> bool:
        """Mueve el cursor a la fila del usuario indicado."""

        try:
            row_index = self.get_row_index(username)
        except RowDoesNotExist:
            return False

        self.move_cursor(row=row_index)
        return True

    @staticmethod
    def _matches(user: dict[str, Any], query: str) -> bool:
        """Coincidencia por usuario, UID, grupo, home o shell."""

        haystack = (
            user["username"],
            str(user["uid"]),
            user["group"],
            user["home"],
            user["shell"],
        )
        return any(query in value.lower() for value in haystack)

    def populate(
        self,
        users: Iterable[dict[str, Any]],
        filter_text: str = "",
    ) -> None:
        """Reemplaza las filas manteniendo el usuario seleccionado si sigue visible."""

        self._ensure_columns()

        selected = self.selected_username
        query = filter_text.strip().lower()

        self.clear(columns=False)

        for user in users:
            if query and not self._matches(user, query):
                continue

            self.add_row(
                str(user["uid"]),
                user["username"],
                user["group"],
                user["home"],
                user["shell"],
                key=user["username"],
            )

        if self.row_count == 0:
            return

        if selected and self.select_username(selected):
            return

        self.move_cursor(row=0)
