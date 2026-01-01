"""Main CLI entry point for dyson-cli."""

import json
import sys
import time
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Callable, TypeVar


import click
from rich.console import Console
from rich.table import Table

from .config import (
    CONFIG_FILE,
    DeviceConfig,
    get_device,
    load_config,
    save_config,
    set_default_device,
)

# Exit codes (following CLI guidelines)
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_CONNECTION_ERROR = 3
EXIT_DEVICE_NOT_FOUND = 4

F = TypeVar("F", bound=Callable[..., Any])


class CLIContext:
    """Shared CLI context for global options."""

    def __init__(self) -> None:
        self.quiet: bool = False
        self.verbose: bool = False
        self.dry_run: bool = False
        self.console: Console = Console()

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print unless quiet mode is enabled."""
        if not self.quiet:
            self.console.print(*args, **kwargs)

    def print_verbose(self, *args: Any, **kwargs: Any) -> None:
        """Print only in verbose mode."""
        if self.verbose and not self.quiet:
            self.console.print(*args, style="dim", **kwargs)

    def status(self, message: str) -> AbstractContextManager[Any]:
        """Return a status context manager for progress indication."""
        if self.quiet:
            return nullcontext()
        return self.console.status(message)


pass_context = click.make_pass_decorator(CLIContext, ensure=True)

# Legacy console for backward compatibility during transition
console = Console()


def device_option(f: F) -> F:
    """Decorator for --device/-d option with DYSON_DEVICE env var fallback."""
    decorated: F = click.option(
        "--device",
        "-d",
        envvar="DYSON_DEVICE",
        help="Device name or serial (env: DYSON_DEVICE)",
    )(f)
    return decorated


def dry_run_option(f: F) -> F:
    """Decorator for --dry-run/-n option."""
    decorated: F = click.option(
        "--dry-run",
        "-n",
        is_flag=True,
        help="Show what would happen without executing",
    )(f)
    return decorated


def validate_speed(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    """Validate speed argument early (before connecting)."""
    if value is None:
        return value
    if value.lower() == "auto":
        return value
    try:
        speed_int = int(value)
        if not 1 <= speed_int <= 10:
            raise click.BadParameter("Speed must be 1-10 or 'auto'")
        return value
    except ValueError:
        raise click.BadParameter("Speed must be a number 1-10 or 'auto'")


# Device type mapping (from libdyson)
DEVICE_TYPE_NAMES = {
    "455": "Dyson Pure Hot+Cool Link",
    "469": "Dyson Pure Cool Link Desk",
    "475": "Dyson Pure Cool Link Tower",
    "520": "Dyson Pure Cool Desk",
    "527": "Dyson Pure Hot+Cool",
    "527K": "Dyson Purifier Hot+Cool Formaldehyde (HP09)",
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
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.option("--verbose", "-v", is_flag=True, help="Show connection details and timing")
@click.option(
    "--no-color",
    is_flag=True,
    envvar="NO_COLOR",
    help="Disable colored output",
)
@click.pass_context
def cli(ctx: click.Context, quiet: bool, verbose: bool, no_color: bool) -> None:
    """Control Dyson devices from the command line.

    Environment variables:
      DYSON_DEVICE  Default device name (overridden by -d)
      NO_COLOR      Disable colors when set
    """
    ctx.ensure_object(CLIContext)
    cli_ctx: CLIContext = ctx.obj
    cli_ctx.quiet = quiet
    cli_ctx.verbose = verbose
    if no_color:
        cli_ctx.console = Console(no_color=True)


@cli.command()
@click.option("--email", prompt="Dyson account email", help="Your Dyson account email")
@click.option(
    "--region",
    type=click.Choice(["US", "CA", "CN", "GB", "AU", "DE", "FR", "IT", "ES", "NL", "IE"]),
    default="GB",
    help="Dyson account region (country code)",
)
def setup(email: str, region: str):
    """Set up device credentials via Dyson account."""
    try:
        from libdyson.cloud.account import DysonAccount
        from libdyson.exceptions import DysonLoginFailure, DysonServerError
    except ImportError:
        console.print("[red]Error: libdyson not installed. Run: pip install libdyson[/red]")
        sys.exit(1)

    account = DysonAccount()

    console.print(f"Sending OTP to {email}...")
    try:
        verify_func = account.login_email_otp(email, region)
    except DysonServerError as e:
        console.print(f"[red]Server error. Try a different region (e.g., GB, US, DE)[/red]")
        sys.exit(1)
    except DysonLoginFailure as e:
        console.print(f"[red]Login failed: {e}[/red]")
        sys.exit(1)

    console.print("[green]OTP sent! Check your email.[/green]")
    otp = click.prompt("Enter the OTP code from your email")
    password = click.prompt("Enter your Dyson account password", hide_input=True)

    console.print("Verifying...")
    try:
        verify_func(otp, password)
    except DysonLoginFailure as e:
        console.print(f"[red]Verification failed: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    console.print("Fetching devices...")
    devices = account.devices()

    if not devices:
        console.print("[yellow]No devices found in your Dyson account.[/yellow]")
        sys.exit(0)

    config = load_config()
    config["devices"] = []

    for device in devices:
        device_info: DeviceConfig = {
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
@click.option("--check", "-c", is_flag=True, help="Check if devices are reachable")
def list_devices(check: bool):
    """List configured devices."""
    config = load_config()
    devices = config.get("devices", [])

    if not devices:
        console.print("[yellow]No devices configured. Run 'dyson setup' first.[/yellow]")
        return

    table = Table(title="Configured Devices")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("IP", style="dim")
    table.add_column("Default", style="yellow")
    if check:
        table.add_column("Status", style="green")

    default = config.get("default_device")
    for device in devices:
        is_default = "✓" if device.get("name") == default else ""
        ip = device.get("ip", "Not configured")
        
        status = None
        device_ip = device.get("ip")
        if check and device_ip:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                sock.connect((device_ip, 1883))
                status = "[green]Online[/green]"
            except Exception:
                status = "[red]Offline[/red]"
            finally:
                sock.close()
        
        row = [
            device.get("name", "Unknown"),
            get_device_type_name(device.get("product_type", "")),
            ip,
            is_default,
        ]
        if check:
            row.append(status or "[dim]Skipped[/dim]")
        table.add_row(*row)

    console.print(table)


@cli.command()
@device_option
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@pass_context
def status(ctx: CLIContext, device: str | None, as_json: bool):
    """Show device status."""
    device_config = get_device(device)
    if not device_config:
        ctx.print("[red]No device found. Run 'dyson setup' first.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[yellow]No IP address configured. Trying auto-discovery...[/yellow]")
        try:
            from libdyson.discovery import DysonDiscovery

            with ctx.status("Discovering devices..."):
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
                    ctx.print(f"[green]Discovered device at {ip}[/green]")
                    break
        except Exception as e:
            ctx.print(f"[red]Discovery failed: {e}[/red]")

    if not ip:
        ctx.print("[red]Could not find device IP. Please add 'ip' to config manually.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    ctx.print_verbose(f"Connecting to {device_config['name']} at {ip}...")

    try:
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(2)  # Wait for state update

        # Raw state for JSON output
        raw_state = {
            "name": device_config["name"],
            "serial": device_config["serial"],
            "type": get_device_type_name(device_config["product_type"]),
            "connected": dyson_device.is_connected,
            "is_on": dyson_device.is_on if hasattr(dyson_device, "is_on") else None,
            "auto_mode": getattr(dyson_device, "auto_mode", None),
            "speed": getattr(dyson_device, "speed", None),
            "oscillation": getattr(dyson_device, "oscillation", None),
            "oscillation_angle_low": getattr(dyson_device, "oscillation_angle_low", None),
            "oscillation_angle_high": getattr(dyson_device, "oscillation_angle_high", None),
            "night_mode": getattr(dyson_device, "night_mode", None),
            "heat_mode_is_on": getattr(dyson_device, "heat_mode_is_on", None),
            "heat_target": getattr(dyson_device, "heat_target", None),
            "temperature": getattr(dyson_device, "temperature", None),
            "humidity": getattr(dyson_device, "humidity", None),
        }

        dyson_device.disconnect()

        if as_json:
            # JSON goes to stdout even in quiet mode
            print(json.dumps(raw_state, indent=2))
        else:
            table = Table(title=f"{device_config['name']}")
            table.add_column("", style="cyan")
            table.add_column("", style="green")

            # Connected
            connected = "[green]✓[/green]" if raw_state["connected"] else "[red]✗[/red]"
            table.add_row("Connected", connected)

            # Fan speed
            if raw_state.get("auto_mode"):
                fan_display = "Auto"
            elif raw_state.get("speed") is not None:
                fan_display = str(raw_state["speed"])
            else:
                fan_display = "[dim]Off[/dim]"
            table.add_row("Fan Speed", fan_display)

            # Oscillation
            if raw_state.get("oscillation"):
                angle_low = int(raw_state.get("oscillation_angle_low") or 0)
                angle_high = int(raw_state.get("oscillation_angle_high") or 0)
                angle_range = angle_high - angle_low
                osc_display = f"{angle_range}° ({angle_low}°–{angle_high}°)"
            else:
                osc_display = "[dim]Off[/dim]"
            table.add_row("Oscillation", osc_display)

            # Heat (Hot+Cool models)
            if raw_state.get("heat_mode_is_on") is not None:
                if raw_state["heat_mode_is_on"]:
                    target_k = int(raw_state.get("heat_target") or 293)
                    target_c = target_k - 273
                    heat_display = f"On → {target_c:.0f}°C"
                else:
                    heat_display = "[dim]Off[/dim]"
                table.add_row("Heat", heat_display)

            # Environment
            temp = raw_state.get("temperature")
            if temp is not None:
                temp_c = int(temp) - 273
                table.add_row("Temperature", f"{temp_c:.1f}°C")

            if raw_state.get("humidity") is not None:
                table.add_row("Humidity", f"{raw_state['humidity']}%")

            # Night mode (quieter + dims display)
            night = "[green]✓[/green]" if raw_state.get("night_mode") else "[dim]Off[/dim]"
            table.add_row("Night Mode", night)

            ctx.console.print(table)

    except Exception as e:
        ctx.print(f"[red]Connection failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


@cli.command()
@device_option
@dry_run_option
@pass_context
def on(ctx: CLIContext, device: str | None, dry_run: bool):
    """Turn device on."""
    _control_power(ctx, device, power_on=True, dry_run=dry_run)


@cli.command()
@device_option
@dry_run_option
@pass_context
def off(ctx: CLIContext, device: str | None, dry_run: bool):
    """Turn device off."""
    _control_power(ctx, device, power_on=False, dry_run=dry_run)


def _control_power(ctx: CLIContext, device_name: str | None, power_on: bool, dry_run: bool = False):
    """Control device power."""
    device_config = get_device(device_name)
    if not device_config:
        ctx.print("[red]No device found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[red]No IP configured. Run 'dyson status' first to discover.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    action = "turn on" if power_on else "turn off"

    if dry_run:
        ctx.print(f"[dim]Would {action} {device_config['name']} at {ip}[/dim]")
        return

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        ctx.print_verbose(f"Connecting to {ip}...")
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(1)

        if power_on:
            dyson_device.turn_on()
            ctx.print(f"[green]✓ {device_config['name']} turned on[/green]")
        else:
            dyson_device.turn_off()
            ctx.print(f"[green]✓ {device_config['name']} turned off[/green]")

        dyson_device.disconnect()

    except Exception as e:
        ctx.print(f"[red]Failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


@cli.group()
def fan():
    """Fan control commands."""
    pass


@fan.command("speed")
@click.argument("speed", callback=validate_speed)
@device_option
@dry_run_option
@pass_context
def fan_speed(ctx: CLIContext, speed: str, device: str | None, dry_run: bool):
    """Set fan speed (1-10 or 'auto')."""
    device_config = get_device(device)
    if not device_config:
        ctx.print("[red]No device found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[red]No IP configured.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    if dry_run:
        ctx.print(f"[dim]Would set fan speed to {speed} on {device_config['name']} at {ip}[/dim]")
        return

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(1)

        if speed.lower() == "auto":
            dyson_device.enable_auto_mode()
            ctx.print("[green]✓ Fan set to auto[/green]")
        else:
            speed_int = int(speed)
            dyson_device.disable_auto_mode()
            dyson_device.set_speed(speed_int)
            ctx.print(f"[green]✓ Fan speed set to {speed_int}[/green]")

        dyson_device.disconnect()

    except Exception as e:
        ctx.print(f"[red]Failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


@fan.command("oscillate")
@click.argument("state", type=click.Choice(["on", "off"]))
@click.option("--angle", "-a", type=int, help="Oscillation range in degrees (45, 90, 180, or 350)")
@device_option
@dry_run_option
@pass_context
def fan_oscillate(ctx: CLIContext, state: str, angle: int | None, device: str | None, dry_run: bool):
    """Enable or disable oscillation. Use --angle to set range (e.g., 90 for 90 degrees)."""
    device_config = get_device(device)
    if not device_config:
        ctx.print("[red]No device found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[red]No IP configured.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    if dry_run:
        action = f"enable oscillation{f' ({angle}°)' if angle else ''}" if state == "on" else "disable oscillation"
        ctx.print(f"[dim]Would {action} on {device_config['name']} at {ip}[/dim]")
        return

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(1)

        if state == "on":
            if angle:
                # Center the oscillation around current position (or 180 degrees)
                center = 180
                half = angle // 2
                angle_low = max(5, center - half)
                angle_high = min(355, center + half)
                dyson_device.enable_oscillation(angle_low=angle_low, angle_high=angle_high)
                ctx.print(f"[green]✓ Oscillation enabled ({angle}° range)[/green]")
            else:
                dyson_device.enable_oscillation()
                ctx.print("[green]✓ Oscillation enabled[/green]")
        else:
            dyson_device.disable_oscillation()
            ctx.print("[green]✓ Oscillation disabled[/green]")

        dyson_device.disconnect()

    except Exception as e:
        ctx.print(f"[red]Failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


@cli.group()
def heat():
    """Heat control commands (Hot+Cool models only)."""
    pass


@heat.command("on")
@device_option
@dry_run_option
@pass_context
def heat_on(ctx: CLIContext, device: str | None, dry_run: bool):
    """Enable heat mode."""
    _control_heat(ctx, device, enable=True, dry_run=dry_run)


@heat.command("off")
@device_option
@dry_run_option
@pass_context
def heat_off(ctx: CLIContext, device: str | None, dry_run: bool):
    """Disable heat mode."""
    _control_heat(ctx, device, enable=False, dry_run=dry_run)


def _control_heat(ctx: CLIContext, device_name: str | None, enable: bool, dry_run: bool = False):
    """Control heat mode."""
    device_config = get_device(device_name)
    if not device_config:
        ctx.print("[red]No device found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[red]No IP configured.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    action = "enable heat mode" if enable else "disable heat mode"

    if dry_run:
        ctx.print(f"[dim]Would {action} on {device_config['name']} at {ip}[/dim]")
        return

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(1)

        if not hasattr(dyson_device, "enable_heat_mode"):
            ctx.print("[red]This device does not support heat mode.[/red]")
            sys.exit(EXIT_ERROR)

        if enable:
            dyson_device.enable_heat_mode()
            ctx.print("[green]✓ Heat mode enabled[/green]")
        else:
            dyson_device.disable_heat_mode()
            ctx.print("[green]✓ Heat mode disabled[/green]")

        dyson_device.disconnect()

    except Exception as e:
        ctx.print(f"[red]Failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


def validate_temperature(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Validate temperature argument early."""
    if value is None:
        return value
    if not 1 <= value <= 37:
        raise click.BadParameter("Temperature must be between 1 and 37°C")
    return value


@heat.command("target")
@click.argument("temperature", type=int, callback=validate_temperature)
@device_option
@dry_run_option
@pass_context
def heat_target(ctx: CLIContext, temperature: int, device: str | None, dry_run: bool):
    """Set target temperature in Celsius (1-37)."""
    device_config = get_device(device)
    if not device_config:
        ctx.print("[red]No device found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[red]No IP configured.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    if dry_run:
        ctx.print(f"[dim]Would set target temperature to {temperature}°C on {device_config['name']} at {ip}[/dim]")
        return

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(1)

        if not hasattr(dyson_device, "set_heat_target"):
            ctx.print("[red]This device does not support heat target.[/red]")
            sys.exit(EXIT_ERROR)

        # libdyson uses Kelvin internally
        dyson_device.set_heat_target(temperature + 273)
        ctx.print(f"[green]✓ Target temperature set to {temperature}°C[/green]")

        dyson_device.disconnect()

    except Exception as e:
        ctx.print(f"[red]Failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


@cli.command()
@click.argument("state", type=click.Choice(["on", "off"]))
@device_option
@dry_run_option
@pass_context
def night(ctx: CLIContext, state: str, device: str | None, dry_run: bool):
    """Enable or disable night mode."""
    device_config = get_device(device)
    if not device_config:
        ctx.print("[red]No device found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    ip = device_config.get("ip")
    if not ip:
        ctx.print("[red]No IP configured.[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)

    enable = state == "on"
    action = "enable night mode" if enable else "disable night mode"

    if dry_run:
        ctx.print(f"[dim]Would {action} on {device_config['name']} at {ip}[/dim]")
        return

    try:
        from libdyson import get_device as libdyson_get_device
    except ImportError:
        ctx.print("[red]Error: libdyson not installed.[/red]")
        sys.exit(EXIT_ERROR)

    dyson_device = libdyson_get_device(
        device_config["serial"],
        device_config["credential"],
        device_config["product_type"],
    )

    try:
        with ctx.status(f"Connecting to {device_config['name']}..."):
            dyson_device.connect(ip)
            time.sleep(1)

        dyson_device.enable_night_mode() if enable else dyson_device.disable_night_mode()
        ctx.print(f"[green]✓ Night mode {'enabled' if enable else 'disabled'}[/green]")

        dyson_device.disconnect()

    except Exception as e:
        ctx.print(f"[red]Failed: {e}[/red]")
        sys.exit(EXIT_CONNECTION_ERROR)


@cli.command("default")
@click.argument("name")
@pass_context
def set_default(ctx: CLIContext, name: str):
    """Set the default device."""
    if set_default_device(name):
        ctx.print(f"[green]✓ Default device set to {name}[/green]")
    else:
        ctx.print(f"[red]Device '{name}' not found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)


@cli.command("remove")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@pass_context
def remove_device(ctx: CLIContext, name: str, force: bool):
    """Remove a device from the config."""
    config = load_config()
    devices = config.get("devices", [])

    # Find device
    device = None
    for d in devices:
        if d.get("name", "").lower() == name.lower() or d.get("serial", "").lower() == name.lower():
            device = d
            break

    if not device:
        ctx.print(f"[red]Device '{name}' not found.[/red]")
        sys.exit(EXIT_DEVICE_NOT_FOUND)

    if not force:
        if not click.confirm(f"Remove {device.get('name')} ({device.get('serial')})?"):
            ctx.print("Cancelled.")
            return

    config["devices"] = [d for d in devices if d.get("serial") != device.get("serial")]

    # Update default if needed
    if config.get("default_device") == device.get("name"):
        config["default_device"] = config["devices"][0]["name"] if config["devices"] else None

    save_config(config)
    ctx.print(f"[green]✓ Removed {device.get('name')}[/green]")


if __name__ == "__main__":
    cli()
