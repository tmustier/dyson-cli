"""Main CLI entry point for dyson-cli."""

import json
import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .config import (
    CONFIG_FILE,
    get_device,
    load_config,
    save_config,
    set_default_device,
)

console = Console()

# Device type mapping (from libdyson)
DEVICE_TYPE_NAMES = {
    "455": "Dyson Pure Hot+Cool Link",
    "469": "Dyson Pure Cool Link Desk",
    "475": "Dyson Pure Cool Link Tower",
    "520": "Dyson Pure Cool Desk",
    "527": "Dyson Pure Hot+Cool",
    "438": "Dyson Pure Cool Tower",
    "358": "Dyson Pure Humidify+Cool",
    "358E": "Dyson Pure Humidify+Cool Formaldehyde",
    "527E": "Dyson Purifier Hot+Cool Formaldehyde",
    "664": "Dyson Purifier Big+Quiet Formaldehyde",
}


def get_device_type_name(product_type: str) -> str:
    """Get human-readable device type name."""
    return DEVICE_TYPE_NAMES.get(product_type, f"Dyson Device ({product_type})")


@click.group()
@click.version_option()
def cli():
    """Control Dyson devices from the command line."""
    pass


@cli.command()
@click.option("--email", prompt="Dyson account email", help="Your Dyson account email")
@click.option(
    "--region",
    type=click.Choice(["US", "CA", "CN", "EU", "AU", "RU"]),
    default="EU",
    help="Dyson account region",
)
def setup(email: str, region: str):
    """Set up device credentials via Dyson account."""
    try:
        from libdyson.cloud import DysonAccount
        from libdyson.exceptions import DysonLoginFailure
    except ImportError:
        console.print("[red]Error: libdyson not installed. Run: pip install libdyson[/red]")
        sys.exit(1)

    account = DysonAccount()

    console.print(f"Sending OTP to {email}...")
    try:
        account.login_email_otp(email, region)
    except DysonLoginFailure as e:
        console.print(f"[red]Login failed: {e}[/red]")
        sys.exit(1)

    otp = click.prompt("Enter the OTP code from your email")

    console.print("Verifying OTP...")
    try:
        account.verify_email_otp(email, otp, region)
    except DysonLoginFailure as e:
        console.print(f"[red]Verification failed: {e}[/red]")
        sys.exit(1)

    console.print("Fetching devices...")
    devices = account.devices()

    if not devices:
        console.print("[yellow]No devices found in your Dyson account.[/yellow]")
        sys.exit(0)

    config = load_config()
    config["devices"] = []

    for device in devices:
        device_info = {
            "name": device.name,
            "serial": device.serial,
            "credential": device.credential,
            "product_type": device.product_type,
        }
        config["devices"].append(device_info)
        console.print(
            f"  Found: {device.name} ({get_device_type_name(device.product_type)})"
        )

    if config["devices"] and not config.get("default_device"):
        config["default_device"] = config["devices"][0]["name"]

    save_config(config)
    console.print(f"\n[green]✓ Saved {len(devices)} device(s) to {CONFIG_FILE}[/green]")


@cli.command("list")
def list_devices():
    """List configured devices."""
    config = load_config()
    devices = config.get("devices", [])

    if not devices:
        console.print("[yellow]No devices configured. Run 'dyson setup' first.[/yellow]")
        return

    table = Table(title="Configured Devices")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Serial", style="dim")
    table.add_column("Default", style="yellow")

    default = config.get("default_device")
    for device in devices:
        is_default = "✓" if device.get("name") == default else ""
        table.add_row(
            device.get("name", "Unknown"),
            get_device_type_name(device.get("product_type", "")),
            device.get("serial", "Unknown"),
            is_default,
        )

    console.print(table)


@cli.command()
@click.option("--device", "-d", help="Device name or serial")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status(device: Optional[str], as_json: bool):
    """Show device status."""
    device_config = get_device(device)
    if not device_config:
        console.print("[red]No device found. Run 'dyson setup' first.[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
        from libdyson import DEVICE_TYPE_PURE_HOT_COOL, DEVICE_TYPE_PURE_HOT_COOL_LINK
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    ip = device_config.get("ip")
    if not ip:
        console.print("[yellow]No IP address configured. Trying auto-discovery...[/yellow]")
        try:
            from libdyson.discovery import DysonDiscovery

            discovery = DysonDiscovery()
            discovery.start_discovery()
            time.sleep(5)
            discovery.stop_discovery()

            discovered = discovery.devices
            for serial, info in discovered.items():
                if serial == device_config["serial"]:
                    ip = info.address
                    device_config["ip"] = ip
                    config = load_config()
                    for d in config["devices"]:
                        if d["serial"] == serial:
                            d["ip"] = ip
                    save_config(config)
                    console.print(f"[green]Discovered device at {ip}[/green]")
                    break
        except Exception as e:
            console.print(f"[red]Discovery failed: {e}[/red]")

    if not ip:
        console.print("[red]Could not find device IP. Please add 'ip' to config manually.[/red]")
        sys.exit(1)

    console.print(f"Connecting to {device_config['name']} at {ip}...")

    try:
        dyson_device.connect(ip)
        time.sleep(2)  # Wait for state update

        state = {
            "name": device_config["name"],
            "serial": device_config["serial"],
            "type": get_device_type_name(device_config["product_type"]),
            "connected": dyson_device.is_connected,
            "power": dyson_device.is_on if hasattr(dyson_device, "is_on") else None,
            "fan_speed": getattr(dyson_device, "speed", None),
            "oscillation": getattr(dyson_device, "oscillation", None),
            "night_mode": getattr(dyson_device, "night_mode", None),
        }

        # Hot+Cool specific
        if hasattr(dyson_device, "heat_mode"):
            state["heat_mode"] = dyson_device.heat_mode
        if hasattr(dyson_device, "heat_target"):
            state["heat_target"] = dyson_device.heat_target

        # Environmental data
        if hasattr(dyson_device, "temperature"):
            state["temperature"] = dyson_device.temperature
        if hasattr(dyson_device, "humidity"):
            state["humidity"] = dyson_device.humidity

        dyson_device.disconnect()

        if as_json:
            console.print(json.dumps(state, indent=2))
        else:
            table = Table(title=f"Status: {state['name']}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            for key, value in state.items():
                if value is not None:
                    table.add_row(key.replace("_", " ").title(), str(value))

            console.print(table)

    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--device", "-d", help="Device name or serial")
def on(device: Optional[str]):
    """Turn device on."""
    _control_power(device, True)


@cli.command()
@click.option("--device", "-d", help="Device name or serial")
def off(device: Optional[str]):
    """Turn device off."""
    _control_power(device, False)


def _control_power(device_name: Optional[str], power_on: bool):
    """Control device power."""
    device_config = get_device(device_name)
    if not device_config:
        console.print("[red]No device found.[/red]")
        sys.exit(1)

    ip = device_config.get("ip")
    if not ip:
        console.print("[red]No IP configured. Run 'dyson status' first to discover.[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        dyson_device.connect(ip)
        time.sleep(1)

        if power_on:
            dyson_device.turn_on()
            console.print(f"[green]✓ {device_config['name']} turned on[/green]")
        else:
            dyson_device.turn_off()
            console.print(f"[green]✓ {device_config['name']} turned off[/green]")

        dyson_device.disconnect()

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)


@cli.group()
def fan():
    """Fan control commands."""
    pass


@fan.command("speed")
@click.argument("speed")
@click.option("--device", "-d", help="Device name or serial")
def fan_speed(speed: str, device: Optional[str]):
    """Set fan speed (1-10 or 'auto')."""
    device_config = get_device(device)
    if not device_config:
        console.print("[red]No device found.[/red]")
        sys.exit(1)

    ip = device_config.get("ip")
    if not ip:
        console.print("[red]No IP configured.[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        dyson_device.connect(ip)
        time.sleep(1)

        if speed.lower() == "auto":
            dyson_device.set_speed(0)  # 0 = auto in libdyson
            console.print(f"[green]✓ Fan set to auto[/green]")
        else:
            speed_int = int(speed)
            if not 1 <= speed_int <= 10:
                console.print("[red]Speed must be 1-10 or 'auto'[/red]")
                sys.exit(1)
            dyson_device.set_speed(speed_int)
            console.print(f"[green]✓ Fan speed set to {speed_int}[/green]")

        dyson_device.disconnect()

    except ValueError:
        console.print("[red]Speed must be a number 1-10 or 'auto'[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)


@fan.command("oscillate")
@click.argument("state", type=click.Choice(["on", "off"]))
@click.option("--device", "-d", help="Device name or serial")
def fan_oscillate(state: str, device: Optional[str]):
    """Enable or disable oscillation."""
    device_config = get_device(device)
    if not device_config:
        console.print("[red]No device found.[/red]")
        sys.exit(1)

    ip = device_config.get("ip")
    if not ip:
        console.print("[red]No IP configured.[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        dyson_device.connect(ip)
        time.sleep(1)

        enable = state == "on"
        dyson_device.enable_oscillation() if enable else dyson_device.disable_oscillation()
        console.print(f"[green]✓ Oscillation {'enabled' if enable else 'disabled'}[/green]")

        dyson_device.disconnect()

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)


@cli.group()
def heat():
    """Heat control commands (Hot+Cool models only)."""
    pass


@heat.command("on")
@click.option("--device", "-d", help="Device name or serial")
def heat_on(device: Optional[str]):
    """Enable heat mode."""
    _control_heat(device, True)


@heat.command("off")
@click.option("--device", "-d", help="Device name or serial")
def heat_off(device: Optional[str]):
    """Disable heat mode."""
    _control_heat(device, False)


def _control_heat(device_name: Optional[str], enable: bool):
    """Control heat mode."""
    device_config = get_device(device_name)
    if not device_config:
        console.print("[red]No device found.[/red]")
        sys.exit(1)

    ip = device_config.get("ip")
    if not ip:
        console.print("[red]No IP configured.[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        dyson_device.connect(ip)
        time.sleep(1)

        if not hasattr(dyson_device, "enable_heat_mode"):
            console.print("[red]This device does not support heat mode.[/red]")
            sys.exit(1)

        if enable:
            dyson_device.enable_heat_mode()
            console.print("[green]✓ Heat mode enabled[/green]")
        else:
            dyson_device.disable_heat_mode()
            console.print("[green]✓ Heat mode disabled[/green]")

        dyson_device.disconnect()

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)


@heat.command("target")
@click.argument("temperature", type=int)
@click.option("--device", "-d", help="Device name or serial")
def heat_target(temperature: int, device: Optional[str]):
    """Set target temperature in Celsius (1-37)."""
    device_config = get_device(device)
    if not device_config:
        console.print("[red]No device found.[/red]")
        sys.exit(1)

    ip = device_config.get("ip")
    if not ip:
        console.print("[red]No IP configured.[/red]")
        sys.exit(1)

    if not 1 <= temperature <= 37:
        console.print("[red]Temperature must be between 1 and 37°C[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        dyson_device.connect(ip)
        time.sleep(1)

        if not hasattr(dyson_device, "set_heat_target"):
            console.print("[red]This device does not support heat target.[/red]")
            sys.exit(1)

        # libdyson uses Kelvin internally
        dyson_device.set_heat_target(temperature + 273)
        console.print(f"[green]✓ Target temperature set to {temperature}°C[/green]")

        dyson_device.disconnect()

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("state", type=click.Choice(["on", "off"]))
@click.option("--device", "-d", help="Device name or serial")
def night(state: str, device: Optional[str]):
    """Enable or disable night mode."""
    device_config = get_device(device)
    if not device_config:
        console.print("[red]No device found.[/red]")
        sys.exit(1)

    ip = device_config.get("ip")
    if not ip:
        console.print("[red]No IP configured.[/red]")
        sys.exit(1)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        console.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(1)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        dyson_device.connect(ip)
        time.sleep(1)

        enable = state == "on"
        dyson_device.enable_night_mode() if enable else dyson_device.disable_night_mode()
        console.print(f"[green]✓ Night mode {'enabled' if enable else 'disabled'}[/green]")

        dyson_device.disconnect()

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)


@cli.command("default")
@click.argument("name")
def set_default(name: str):
    """Set the default device."""
    if set_default_device(name):
        console.print(f"[green]✓ Default device set to {name}[/green]")
    else:
        console.print(f"[red]Device '{name}' not found.[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
