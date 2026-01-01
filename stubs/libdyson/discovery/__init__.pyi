"""Type stubs for libdyson.discovery."""

class DiscoveredDevice:
    address: str

class DysonDiscovery:
    devices: dict[str, DiscoveredDevice]

    def start_discovery(self) -> None: ...
    def stop_discovery(self) -> None: ...
