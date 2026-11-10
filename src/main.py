"""Punto de entrada de lum-tui.

Fase 1: el backend y el cargador de temas ya están disponibles. La aplicación
Textual (``MainScreen``, widgets y modales) se cableará en la fase 2.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Arranca lum-tui (pendiente de la fase 2)."""

    print(
        "lum-tui: la interfaz TUI aún no está implementada.\n"
        "La capa de sistema ya está disponible en "
        "src/controllers/user_manager.py y el cargador de temas en "
        "src/utils/theme_loader.py.\n"
        "Completa src/views/screens.py, src/views/widgets.py y este punto de "
        "entrada para arrancar la aplicación.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
