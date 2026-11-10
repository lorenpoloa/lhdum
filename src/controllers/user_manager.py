"""Capa de acceso al sistema Linux para ``lum-tui``.

Encapsula la lectura de usuarios/grupos mediante los módulos ``pwd`` y ``grp``,
y la ejecución segura de ``useradd``/``userdel`` mediante ``subprocess``.

Principios de seguridad:

* Nunca se usa ``shell=True``: los argumentos se pasan como lista.
* Los nombres de usuario, shells, homes y grupos se validan antes de ejecutar
  comandos.
* Las operaciones de escritura se ejecutan directamente si el proceso es root,
  o mediante ``sudo -n`` (no interactivo). Así la TUI nunca se queda colgada
  esperando una contraseña; si sudo requiere contraseña se lanza
  :class:`PrivilegeError` con un mensaje accionable.
* No se permite eliminar ``root`` ni la cuenta del usuario que ejecuta la TUI.
"""

from __future__ import annotations

import grp
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

# Sintaxis POSIX indicada en la especificación, más el límite real de Linux.
USERNAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]*\$?$")
GROUP_PATTERN = USERNAME_PATTERN
MAX_NAME_LENGTH = 32

DEFAULT_SHELLS: tuple[str, ...] = (
    "/bin/bash",
    "/bin/zsh",
    "/bin/sh",
    "/usr/sbin/nologin",
)

PROTECTED_USERS = frozenset({"root"})

_PRIVILEGE_ERROR_MARKERS = (
    "not in the sudoers",
    "password is required",
    "a terminal is required",
    "no tty present",
    "not allowed to execute",
    "permission denied",
    "permiso denegado",
    "se requiere una contraseña",
)


class UserManagerError(Exception):
    """Error base de la capa de gestión de usuarios."""


class PrivilegeError(UserManagerError):
    """No hay privilegios suficientes para modificar el sistema."""


class UserValidationError(UserManagerError, ValueError):
    """Los datos introducidos no cumplen la sintaxis esperada."""


class UserNotFoundError(UserManagerError, LookupError):
    """El usuario solicitado no existe."""


class UserAlreadyExistsError(UserManagerError):
    """El usuario que se intenta crear ya existe."""


class UserOperationError(UserManagerError):
    """Un comando del sistema falló o no pudo ejecutarse."""


class SystemUserManager:
    """Fachada única para consultar y modificar usuarios locales."""

    # ------------------------------------------------------------------
    # Consultas (solo lectura, no requieren privilegios)
    # ------------------------------------------------------------------
    @staticmethod
    def _entry_to_dict(entry: pwd.struct_passwd) -> dict[str, Any]:
        try:
            main_group = grp.getgrgid(entry.pw_gid).gr_name
        except KeyError:
            main_group = str(entry.pw_gid)

        return {
            "username": entry.pw_name,
            "uid": entry.pw_uid,
            "gid": entry.pw_gid,
            "group": main_group,
            "home": entry.pw_dir,
            "shell": entry.pw_shell,
            "gecos": entry.pw_gecos,
            "is_system": entry.pw_uid < 1000 and entry.pw_uid != 0,
        }

    @classmethod
    def get_all_users(cls, include_system: bool = True) -> list[dict[str, Any]]:
        """Devuelve los usuarios locales ordenados por UID.

        Args:
            include_system: Si es ``False``, excluye las cuentas de sistema
                (UID < 1000 salvo root).
        """

        try:
            entries = pwd.getpwall()
        except OSError as exc:
            raise UserOperationError(
                "No se pudo leer la base de usuarios del sistema (/etc/passwd)."
            ) from exc

        users = [cls._entry_to_dict(entry) for entry in entries]
        if not include_system:
            users = [user for user in users if not user["is_system"]]

        return sorted(users, key=lambda user: (user["uid"], user["username"]))

    @classmethod
    def get_user(cls, username: str) -> dict[str, Any]:
        """Devuelve un usuario por nombre.

        Raises:
            UserValidationError: Si el nombre no es válido.
            UserNotFoundError: Si el usuario no existe.
        """

        username = username.strip()
        cls.validate_username(username)

        try:
            entry = pwd.getpwnam(username)
        except KeyError as exc:
            raise UserNotFoundError(
                f"El usuario '{username}' no existe."
            ) from exc

        return cls._entry_to_dict(entry)

    @classmethod
    def user_exists(cls, username: str) -> bool:
        """Comprueba si existe un usuario sin lanzar excepciones."""

        try:
            pwd.getpwnam(username)
        except KeyError:
            return False
        return True

    @classmethod
    def get_user_groups(cls, username: str) -> list[str]:
        """Devuelve los grupos del usuario, incluido su grupo primario."""

        username = username.strip()
        cls.validate_username(username)

        try:
            entry = pwd.getpwnam(username)
        except KeyError as exc:
            raise UserNotFoundError(
                f"El usuario '{username}' no existe."
            ) from exc

        gids = {entry.pw_gid}
        try:
            gids.update(os.getgrouplist(username, entry.pw_gid))
        except OSError:
            # ``os.getgrouplist`` no está disponible en todos los sistemas;
            # el grupo primario sigue siendo una respuesta útil.
            pass

        groups: list[str] = []
        for gid in sorted(gids):
            try:
                groups.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                groups.append(str(gid))
        return groups

    @classmethod
    def get_supplementary_groups(cls, username: str) -> list[str]:
        """Devuelve solo los grupos secundarios, sin el grupo primario."""

        user = cls.get_user(username)
        return [
            group
            for group in cls.get_user_groups(username)
            if group != user["group"]
        ]

    @staticmethod
    def get_available_shells() -> list[str]:
        """Devuelve las shells válidas para el selector del formulario."""

        shells = list(DEFAULT_SHELLS)
        shells_file = Path("/etc/shells")
        if shells_file.is_file():
            try:
                for line in shells_file.read_text(encoding="utf-8").splitlines():
                    shell = line.strip()
                    if shell and not shell.startswith("#") and shell not in shells:
                        shells.append(shell)
            except OSError:
                pass
        return shells

    # ------------------------------------------------------------------
    # Validación de entrada
    # ------------------------------------------------------------------
    @staticmethod
    def validate_username(username: str) -> None:
        """Valida un nombre de usuario con sintaxis POSIX."""

        if not username:
            raise UserValidationError("El nombre de usuario no puede estar vacío.")
        if len(username) > MAX_NAME_LENGTH:
            raise UserValidationError(
                f"El nombre de usuario no puede superar {MAX_NAME_LENGTH} caracteres."
            )
        if not USERNAME_PATTERN.fullmatch(username):
            raise UserValidationError(
                "Inválido: a-z, 0-9, '-', '_'; inicia con letra o '_'."
            )

    @staticmethod
    def validate_shell(shell: str) -> None:
        """Valida que la shell sea una ruta absoluta sin espacios."""

        if not shell or not shell.startswith("/"):
            raise UserValidationError("La shell debe ser una ruta absoluta.")
        if any(char.isspace() for char in shell) or "\x00" in shell:
            raise UserValidationError("La ruta de la shell contiene caracteres inválidos.")

    @staticmethod
    def validate_home(home: str) -> None:
        """Valida el directorio home opcional."""

        if not home:
            return
        if not home.startswith("/"):
            raise UserValidationError(
                "El directorio home debe ser una ruta absoluta."
            )
        if "\x00" in home or "\n" in home or "\r" in home:
            raise UserValidationError(
                "El directorio home contiene caracteres inválidos."
            )
        if ".." in home.split("/"):
            raise UserValidationError(
                "El directorio home no puede contener '..'."
            )

    @staticmethod
    def validate_groups(groups: Iterable[str] | None) -> list[str]:
        """Normaliza y valida una lista de grupos secundarios."""

        normalized: list[str] = []
        for group in groups or ():
            group = group.strip()
            if not group:
                continue
            if len(group) > MAX_NAME_LENGTH or not GROUP_PATTERN.fullmatch(group):
                raise UserValidationError(
                    f"Grupo inválido: '{group}'."
                )
            if group not in normalized:
                normalized.append(group)
        return normalized

    # ------------------------------------------------------------------
    # Privilegios
    # ------------------------------------------------------------------
    @staticmethod
    def is_root() -> bool:
        """Indica si el proceso se ejecuta como root."""

        return os.geteuid() == 0

    @classmethod
    def check_privileges(cls) -> None:
        """Comprueba que se pueda elevar privilegios sin intervención manual.

        Raises:
            PrivilegeError: Si no se es root ni existe sudo con credenciales
                cacheadas o regla ``NOPASSWD``.
        """

        if cls.is_root():
            return

        sudo = shutil.which("sudo")
        if sudo is None:
            raise PrivilegeError(
                "Se requieren privilegios de root o sudo para modificar usuarios. "
                "Instala sudo o ejecuta lum-tui como root."
            )

        try:
            result = subprocess.run(
                [sudo, "-n", "true"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PrivilegeError(
                f"No se pudo comprobar sudo: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = (result.stderr or "").strip()
            suffix = f" Detalle: {detail}" if detail else ""
            raise PrivilegeError(
                "Se requieren privilegios de root o sudo. Ejecuta 'sudo -v' antes "
                "de arrancar lum-tui, configura sudo sin contraseña para tu "
                f"usuario, o lanza la aplicación como root.{suffix}"
            )

    @classmethod
    def has_privileges(cls) -> bool:
        """Versión booleana de :meth:`check_privileges` para la pantalla de aviso."""

        try:
            cls.check_privileges()
        except PrivilegeError:
            return False
        return True

    # ------------------------------------------------------------------
    # Operaciones de escritura
    # ------------------------------------------------------------------
    @classmethod
    def _run_privileged(
        cls,
        command: Sequence[str],
        *,
        action: str,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Ejecuta un comando de sistema con privilegios y sin shell."""

        if cls.is_root():
            full_command = list(command)
        else:
            sudo = shutil.which("sudo")
            if sudo is None:
                raise PrivilegeError(
                    "No se encontró sudo y el proceso no se ejecuta como root."
                )
            # ``-n`` evita que sudo bloquee la TUI pidiendo contraseña por TTY.
            full_command = [sudo, "-n", *command]

        try:
            return subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise UserOperationError(
                f"No se encontró el ejecutable '{full_command[0]}'."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise UserOperationError(
                f"Se agotó el tiempo de espera al intentar {action}."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            lower = stderr.lower()

            if any(marker in lower for marker in _PRIVILEGE_ERROR_MARKERS):
                suffix = f" {stderr}" if stderr else ""
                raise PrivilegeError(
                    "No se pudieron elevar privilegios para "
                    f"{action}. Ejecuta 'sudo -v' antes de arrancar lum-tui.{suffix}"
                ) from exc

            if "already exists" in lower or "ya existe" in lower:
                raise UserAlreadyExistsError(
                    f"El usuario ya existe: {stderr}"
                ) from exc

            if "does not exist" in lower or "no existe" in lower:
                raise UserNotFoundError(
                    f"El usuario o grupo indicado no existe: {stderr}"
                ) from exc

            raise UserOperationError(
                f"Fallo al {action}: {stderr or f'código {exc.returncode}'}"
            ) from exc
        except OSError as exc:
            raise UserOperationError(
                f"No se pudo ejecutar el comando para {action}: {exc}"
            ) from exc

    @classmethod
    def create_user(
        cls,
        username: str,
        shell: str = "/bin/bash",
        home: str = "",
        groups: Iterable[str] | None = None,
        *,
        create_home: bool = True,
    ) -> bool:
        """Crea un usuario local con ``useradd``.

        Args:
            username: Nombre POSIX del usuario.
            shell: Ruta absoluta de la shell de login.
            home: Directorio home opcional (por defecto lo decide ``useradd``).
            groups: Grupos secundarios opcionales.
            create_home: Si es ``True``, añade ``-m`` para crear el home.

        Returns:
            ``True`` si el usuario se creó correctamente.

        Raises:
            UserValidationError: Si algún dato es inválido.
            UserAlreadyExistsError: Si el usuario ya existe.
            PrivilegeError: Si no hay privilegios suficientes.
            UserOperationError: Si ``useradd`` falla.
        """

        username = username.strip()
        cls.validate_username(username)
        cls.validate_shell(shell)
        cls.validate_home(home)
        normalized_groups = cls.validate_groups(groups)

        if cls.user_exists(username):
            raise UserAlreadyExistsError(
                f"El usuario '{username}' ya existe."
            )

        command = ["useradd"]
        if create_home:
            command.append("-m")
        command.extend(["-s", shell])
        if home:
            command.extend(["-d", home])
        if normalized_groups:
            command.extend(["-G", ",".join(normalized_groups)])
        command.append(username)

        cls._run_privileged(
            command,
            action=f"crear el usuario '{username}'",
        )
        return True

    @classmethod
    def modify_user(
        cls,
        username: str,
        shell: str | None = None,
        groups: Iterable[str] | None = None,
    ) -> bool:
        """Modifica la shell y/o los grupos secundarios con ``usermod``.

        Args:
            username: Nombre del usuario.
            shell: Nueva shell de login, o ``None`` para no cambiarla.
            groups: Nueva lista de grupos secundarios, o ``None`` para no
                cambiarlos. Una lista vacía elimina todos los grupos
                secundarios.

        Returns:
            ``True`` si la modificación se aplicó correctamente.

        Raises:
            UserValidationError: Si no hay cambios o algún dato es inválido.
            UserNotFoundError: Si el usuario no existe.
            UserOperationError: Si se intenta modificar una cuenta protegida.
            PrivilegeError: Si no hay privilegios suficientes.
            UserOperationError: Si ``usermod`` falla.
        """

        username = username.strip()
        cls.validate_username(username)

        if username in PROTECTED_USERS:
            raise UserOperationError(
                f"La cuenta '{username}' está protegida y no se puede modificar."
            )

        cls.get_user(username)

        command = ["usermod"]
        has_changes = False

        if shell is not None:
            cls.validate_shell(shell)
            command.extend(["-s", shell])
            has_changes = True

        if groups is not None:
            normalized_groups = cls.validate_groups(groups)
            # ``-G ""`` elimina todos los grupos secundarios.
            command.extend(["-G", ",".join(normalized_groups)])
            has_changes = True

        if not has_changes:
            raise UserValidationError("No se indicó ningún cambio para el usuario.")

        command.append(username)

        cls._run_privileged(
            command,
            action=f"modificar el usuario '{username}'",
        )
        return True

    @classmethod
    def delete_user(
        cls,
        username: str,
        remove_home: bool = False,
    ) -> bool:
        """Elimina un usuario local con ``userdel``.

        Args:
            username: Nombre del usuario.
            remove_home: Si es ``True``, añade ``-r`` para borrar su home y correo.

        Returns:
            ``True`` si el usuario se eliminó correctamente.

        Raises:
            UserValidationError: Si el nombre no es válido.
            UserNotFoundError: Si el usuario no existe.
            UserOperationError: Si se intenta borrar una cuenta protegida.
            PrivilegeError: Si no hay privilegios suficientes.
        """

        username = username.strip()
        cls.validate_username(username)

        if username in PROTECTED_USERS:
            raise UserOperationError(
                f"La cuenta '{username}' está protegida y no se puede eliminar."
            )

        user = cls.get_user(username)
        if user["uid"] == os.geteuid():
            raise UserOperationError(
                "No puedes eliminar la cuenta con la que estás ejecutando lum-tui."
            )

        command = ["userdel"]
        if remove_home:
            command.append("-r")
        command.append(username)

        cls._run_privileged(
            command,
            action=f"eliminar el usuario '{username}'",
        )
        return True
