"""Carga de estilos externos para ``lum-tui``.

Este módulo es el único punto de entrada para la configuración visual de la
aplicación. Lee ``config/app_style.json`` y genera una hoja TCSS (Textual CSS)
que se inyecta en la ``App`` al arrancar. De este modo, ningún widget contiene
colores, bordes o márgenes codificados directamente en Python.

Uso típico::

    from src.utils.theme_loader import load_tcss_from_config

    class LumTuiApp(App):
        CSS = load_tcss_from_config()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ``src/utils/theme_loader.py`` -> parents[2] es la raíz del proyecto.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "app_style.json"

_PALETTE_KEYS = (
    "background",
    "surface",
    "surface_focus",
    "primary",
    "secondary",
    "accent",
    "text",
    "text_muted",
    "border",
    "border_focus",
    "success",
    "warning",
    "error",
)

_TABLE_KEYS = (
    "row_odd_background",
    "row_even_background",
    "cursor_background",
    "cursor_foreground",
)


class ThemeConfigError(ValueError):
    """La configuración de estilos existe, pero no es válida."""


def _resolve_config_path(config_path: str | Path | None) -> Path:
    """Resuelve una ruta relativa contra el cwd y la raíz del proyecto.

    Se admiten ambos modos de ejecución habituales: desde la raíz del proyecto
    (``python -m src.main``) y desde ``src/`` (``python main.py``).
    """

    if config_path is None:
        return DEFAULT_CONFIG_PATH

    path = Path(config_path).expanduser()
    if path.is_absolute():
        return path

    candidates = (Path.cwd() / path, PROJECT_ROOT / path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    # Si no existe, se devuelve la ruta esperada dentro del proyecto para que
    # el mensaje de error sea útil independientemente del cwd.
    return candidates[-1].resolve()


def _require_mapping(
    config: dict[str, Any],
    key: str,
    *,
    path: Path,
) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ThemeConfigError(
            f"'{key}' debe ser un objeto JSON en {path}"
        )
    return value


def _validate_config(config: dict[str, Any], path: Path) -> None:
    """Valida las claves mínimas necesarias para generar el TCSS."""

    if not isinstance(config, dict):
        raise ThemeConfigError(f"La raíz de {path} debe ser un objeto JSON")

    palette = _require_mapping(config, "palette", path=path)
    borders = _require_mapping(config, "borders", path=path)
    table = _require_mapping(config, "table", path=path)
    typography = config.get("typography", {})
    if not isinstance(typography, dict):
        raise ThemeConfigError(f"'typography' debe ser un objeto JSON en {path}")

    missing = [key for key in _PALETTE_KEYS if key not in palette]
    if missing:
        raise ThemeConfigError(
            f"Faltan colores en 'palette' ({path}): {', '.join(missing)}"
        )

    missing = [key for key in _TABLE_KEYS if key not in table]
    if missing:
        raise ThemeConfigError(
            f"Faltan valores en 'table' ({path}): {', '.join(missing)}"
        )

    for section_name, section, keys in (
        ("palette", palette, _PALETTE_KEYS),
        ("table", table, _TABLE_KEYS),
    ):
        for key in keys:
            value = section[key]
            if not isinstance(value, str) or not value.strip():
                raise ThemeConfigError(
                    f"'{section_name}.{key}' debe ser una cadena de color no vacía "
                    f"en {path}"
                )

    for key in ("type", "panel_type"):
        value = borders.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ThemeConfigError(
                f"'borders.{key}' debe ser una cadena no vacía en {path}"
            )


def load_style_config(
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Lee y valida el JSON de estilos.

    Args:
        config_path: Ruta al JSON. Si es relativa, se busca primero respecto al
            directorio actual y después respecto a la raíz del proyecto. Si se
            omite, se usa ``config/app_style.json``.

    Returns:
        El contenido del archivo como diccionario.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ThemeConfigError: Si el JSON es inválido o le faltan claves.
    """

    path = _resolve_config_path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuración no encontrada en {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ThemeConfigError(
            f"JSON inválido en {path}: línea {exc.lineno}, columna {exc.colno}: "
            f"{exc.msg}"
        ) from exc

    _validate_config(config, path)
    return config


def _is_dark_color(color: str) -> bool:
    """Estima si un color hexadecimal es oscuro (para el tema de Textual)."""

    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return True

    try:
        red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return True

    return (0.299 * red + 0.587 * green + 0.114 * blue) < 128


def build_textual_theme(config_path: str | Path | None = None) -> Any | None:
    """Construye un tema nativo de Textual a partir de ``app_style.json``.

    El TCSS generado por :func:`load_tcss_from_config` estiliza la pantalla
    principal, pero los componentes internos de Textual (command palette,
    panel de ayuda, notificaciones, scrollbars...) usan sus propias variables
    de tema. Registrar la misma paleta como ``Theme`` mantiene toda la
    aplicación visualmente coherente.

    Args:
        config_path: Ruta opcional al archivo de configuración.

    Returns:
        Una instancia de ``textual.theme.Theme``, o ``None`` si la versión de
        Textual instalada no soporta temas (anterior a la 0.86).
    """

    try:
        from textual.theme import Theme
    except ImportError:
        return None

    config = load_style_config(config_path)
    palette = config["palette"]
    table = config["table"]

    return Theme(
        name=config.get("theme_name", "lum-tui"),
        primary=palette["primary"],
        secondary=palette["secondary"],
        accent=palette["accent"],
        warning=palette["warning"],
        error=palette["error"],
        success=palette["success"],
        foreground=palette["text"],
        background=palette["background"],
        surface=palette["surface"],
        panel=palette["surface_focus"],
        dark=_is_dark_color(palette["background"]),
        variables={
            "border": palette["border"],
            "border-focus": palette["border_focus"],
            "text-muted": palette["text_muted"],
            "surface-focus": palette["surface_focus"],
            "footer-background": palette["surface"],
            "footer-foreground": palette["text_muted"],
            "footer-key-foreground": palette["primary"],
            "block-cursor-background": table["cursor_background"],
            "block-cursor-foreground": table["cursor_foreground"],
            "block-cursor-text-style": "bold",
        },
    )


def load_tcss_from_config(
    config_path: str | Path | None = None,
) -> str:
    """Traduce ``app_style.json`` a una hoja de estilos TCSS de Textual.

    Args:
        config_path: Ruta opcional al archivo de configuración.

    Returns:
        Cadena TCSS lista para asignarse a ``App.CSS``.
    """

    config = load_style_config(config_path)

    palette = config["palette"]
    borders = config["borders"]
    table = config["table"]
    font_style = config.get("typography", {}).get("font_style", "bold")

    p = palette
    b = borders
    t = table

    return f"""
Screen {{
    background: {p["background"]};
    color: {p["text"]};
    text-style: {font_style};
}}

Header {{
    background: {p["surface"]};
    color: {p["primary"]};
    border-bottom: {b["type"]} {p["border"]};
}}

Footer {{
    background: {p["surface"]};
    color: {p["text_muted"]};
}}

#action_bar {{
    height: 3;
    layout: horizontal;
    align-vertical: middle;
    background: {p["surface"]};
    border-bottom: {b["type"]} {p["border"]};
    padding: 0 1;
}}

#search_input {{
    width: 1fr;
    background: {p["surface_focus"]};
    color: {p["text"]};
    border: {b["type"]} {p["border"]};
}}

#search_input:focus {{
    border: {b["type"]} {p["border_focus"]};
}}

#action_bar Button {{
    min-width: 12;
    margin-left: 1;
}}

DataTable {{
    background: {p["background"]};
    color: {p["text"]};
    border: {b["type"]} {p["border"]};
}}

#user_table {{
    height: 1fr;
}}

DataTable > .datatable--header {{
    background: {p["surface"]};
    color: {p["secondary"]};
    text-style: bold;
}}

DataTable > .datatable--odd-row {{
    background: {t["row_odd_background"]};
}}

DataTable > .datatable--even-row {{
    background: {t["row_even_background"]};
}}

DataTable > .datatable--cursor,
DataTable:focus > .datatable--cursor {{
    background: {t["cursor_background"]};
    color: {t["cursor_foreground"]};
    text-style: bold;
}}

#detail_panel {{
    height: 6;
    background: {p["surface"]};
    border: {b["type"]} {p["border"]};
    margin: 1 0;
    padding: 0 1;
}}

#detail_title {{
    height: 1;
    color: {p["secondary"]};
    text-style: bold;
}}

#detail_content {{
    height: 1fr;
    color: {p["text"]};
}}

Input {{
    background: {p["surface_focus"]};
    color: {p["text"]};
    border: {b["type"]} {p["border"]};
}}

Input:focus {{
    border: {b["type"]} {p["border_focus"]};
}}

Input:disabled {{
    background: {p["surface"]};
    color: {p["text_muted"]};
    border: {b["type"]} {p["border"]};
}}

Input > .input--placeholder {{
    color: {p["text_muted"]};
}}

Select {{
    background: {p["surface_focus"]};
    color: {p["text"]};
    border: {b["type"]} {p["border"]};
}}

Select:focus {{
    border: {b["type"]} {p["border_focus"]};
}}

Checkbox {{
    background: transparent;
    color: {p["text"]};
}}

Button {{
    background: {p["surface_focus"]};
    color: {p["text"]};
    border: {b["type"]} {p["border"]};
}}

Button:hover {{
    background: {p["primary"]};
    color: {p["background"]};
}}

Button:disabled {{
    background: {p["surface"]};
    color: {p["text_muted"]};
    border: {b["type"]} {p["border"]};
}}

Button.-success {{
    background: {p["success"]};
    color: {p["background"]};
}}

Button.-error {{
    background: {p["error"]};
    color: {p["background"]};
}}

ModalScreen {{
    align: center middle;
    background: rgba(0, 0, 0, 0.6);
}}

#dialog {{
    width: 66;
    max-height: 100%;
    height: auto;
    background: {p["surface"]};
    border: {b["type"]} {p["border_focus"]};
    padding: 0 2;
    overflow-y: auto;
}}

.dialog_title {{
    height: 1;
    color: {p["primary"]};
    text-style: bold;
}}

.dialog_text {{
    height: auto;
    color: {p["text"]};
    margin-bottom: 1;
}}

.field_label {{
    height: 1;
    color: {p["text_muted"]};
}}

#dialog Input,
#dialog Select {{
    width: 100%;
}}

#dialog_buttons {{
    height: 3;
    align-horizontal: right;
}}

#dialog_buttons Button {{
    min-width: 12;
    margin-left: 1;
}}

#form_error {{
    height: auto;
    color: {p["error"]};
    margin-top: 1;
}}

#alert_message {{
    height: auto;
    color: {p["text"]};
}}

#help_text {{
    height: auto;
    color: {p["text"]};
}}
"""
