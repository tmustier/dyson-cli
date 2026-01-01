"""Type stubs for libdyson.cloud.account."""

from typing import Callable

class DysonAccountDevice:
    name: str
    serial: str
    credential: str
    product_type: str

class DysonAccount:
    def login_email_otp(self, email: str, region: str) -> Callable[[str, str], dict[str, str]]: ...
    def devices(self) -> list[DysonAccountDevice]: ...
