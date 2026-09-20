class ProviderError(Exception):
    pass


class ProviderCredentialsError(ProviderError):
    pass


class ProviderPermissionError(ProviderError):
    def __init__(self, operation: str, region: str | None = None) -> None:
        self.operation = operation
        self.region = region
        super().__init__(f"permission denied for {operation}" + (f" in {region}" if region else ""))


class ProviderRegionUnavailableError(ProviderError):
    def __init__(self, region: str | None = None) -> None:
        self.region = region
        super().__init__(f"region unavailable{f' ({region})' if region else ''}")


class ProviderThrottledError(ProviderError):
    pass


class ProviderTransientError(ProviderError):
    pass


class ProviderMalformedResponseError(ProviderError):
    pass


class OperationNotAllowedError(ProviderError):
    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"AWS operation is not allow-listed: {operation}")
