from src.core.config import settings


def is_local_request(client_host: str | None) -> bool:
    return client_host in {"127.0.0.1", "localhost", "::1"}


def require_local_access(client_host: str | None) -> None:
    if not is_local_request(client_host):
        raise PermissionError(f"Accès local requis pour {settings.app_name}.")