from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    message = "Bad request"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = 404
    message = "Not found"


class PermissionDeniedError(DomainError):
    status_code = 403
    message = "Permission denied"


class ConflictError(DomainError):
    status_code = 409
    message = "Conflict"


class AuthenticationError(DomainError):
    status_code = 401
    message = "Invalid credentials"


class ConfigurationError(DomainError):
    status_code = 500
    message = "Configuration error"


class ExternalToolError(DomainError):
    status_code = 500
    message = "External tool failed"
