"""Punto de entrada de lhdum."""

from __future__ import annotations

import sys


def main() -> int:
    """Arranca la aplicación Textual."""

    try:
        from src.utils.theme_loader import ThemeConfigError
        from src.views.screens import MainScreen
    except ModuleNotFoundError as exc:
        if exc.name == "textual":
            print(
                "lhdum: falta la dependencia 'textual'. "
                "Instala las dependencias con: python -m pip install -r requirements.txt",
                file=sys.stderr,
            )
            return 1
        raise

    try:
        app = MainScreen()
    except (FileNotFoundError, ThemeConfigError) as exc:
        print(f"lhdum: error de configuración visual: {exc}", file=sys.stderr)
        return 2

    try:
        app.run()
    except KeyboardInterrupt:
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
