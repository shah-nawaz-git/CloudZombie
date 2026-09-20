from botocore.exceptions import (
    ConnectionError as BotocoreConnectionError,
)
from botocore.exceptions import (
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
    PartialCredentialsError,
    ProfileNotFound,
)

from app.providers.errors import (
    ProviderCredentialsError,
    ProviderError,
    ProviderPermissionError,
    ProviderRegionUnavailableError,
    ProviderThrottledError,
    ProviderTransientError,
)

PERMISSION_CODES = {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}
THROTTLING_CODES = {
    "Throttling",
    "ThrottlingException",
    "RequestLimitExceeded",
    "TooManyRequestsException",
}
CREDENTIAL_CODES = {
    "ExpiredToken",
    "ExpiredTokenException",
    "SignatureDoesNotMatch",
    "UnrecognizedClientException",
}
TRANSIENT_CODES = {"RequestExpired", "InternalError", "ServiceUnavailable", "InternalFailure"}


def client_error_code(exc: Exception) -> tuple[str, str]:
    response = getattr(exc, "response", {})
    error = response.get("Error", {})
    return str(error.get("Code", "")), str(error.get("Message", ""))


def translate_client_error(exc: Exception, operation: str, region: str | None) -> None:
    code, message = client_error_code(exc)
    lower_message = message.lower()
    if isinstance(
        exc, (NoCredentialsError, NoRegionError, PartialCredentialsError, ProfileNotFound)
    ):
        raise ProviderCredentialsError(str(exc)) from exc
    if isinstance(exc, EndpointConnectionError):
        raise ProviderRegionUnavailableError(region) from exc
    if isinstance(exc, BotocoreConnectionError):
        raise ProviderTransientError(str(exc)) from exc
    if code in PERMISSION_CODES or (code == "AuthFailure" and "not authorized" in lower_message):
        raise ProviderPermissionError(operation, region) from exc
    if code == "OptInRequired" or (code == "InvalidClientTokenId" and "region" in lower_message):
        raise ProviderRegionUnavailableError(region) from exc
    if code in THROTTLING_CODES:
        raise ProviderThrottledError(f"throttled while calling {operation}") from exc
    if code in CREDENTIAL_CODES or code == "InvalidClientTokenId":
        raise ProviderCredentialsError(message or code) from exc
    if code in TRANSIENT_CODES:
        raise ProviderTransientError(message or code) from exc
    raise ProviderError(f"{operation} failed: {message or code or exc}") from exc
