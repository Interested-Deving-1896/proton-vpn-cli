"""
Set features commands.

Copyright (c) 2025 Proton AG

This file is part of Proton VPN.

Proton VPN is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Proton VPN is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ProtonVPN.  If not, see <https://www.gnu.org/licenses/>.
"""
from typing import Optional
import enum
import click
from proton.vpn.killswitch.interface import KillSwitchState
from proton.vpn.core.settings.features import NetShield
from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller, Feature
from proton.vpn.cli.core.exceptions import AuthenticationRequiredError, \
    RequiresHigherTierError, InvalidDNS, InvalidServer
from proton.vpn.cli.commands.account import SIGNIN_COMMAND


class ToggleState(enum.Enum):
    """Represents simple binary options that a user can select.
    """
    OFF = False
    ON = True

    def get_human_friendly_state_string(self) -> str:
        """Returns human friendly state string of the currently
        selected choice.
        """
        if self == ToggleState.OFF:
            return "disabled"

        return "enabled"


class KillSwitchMode(enum.Enum):
    """Represent the various kill switch states that a user can select
    """
    OFF = KillSwitchState.OFF
    STANDARD = KillSwitchState.ON
    ADVANCED = KillSwitchState.PERMANENT

    def get_human_friendly_state_string(self) -> str:
        """Returns human friendly state string of the currently
        selected choice.
        """
        if self == KillSwitchMode.OFF:
            return "disabled"

        if self == KillSwitchMode.STANDARD:
            return "standard"

        return "advanced"


class NetshieldMode(enum.Enum):
    """Represent the various netshield states that a user can select
    """
    OFF = NetShield.NO_BLOCK
    MALWARE_ONLY = NetShield.BLOCK_MALICIOUS_URL
    MALWARE_ADS_TRACKERS = NetShield.BLOCK_ADS_AND_TRACKING

    def get_human_friendly_state_string(self) -> str:
        """Returns human friendly state string of the currently
        selected choice.
        """
        if self == NetshieldMode.OFF:
            return "disabled"

        if self == NetshieldMode.MALWARE_ONLY:
            return "malware only"

        return "malware, ads and trackers"


BOOL_FEATURES = [
    Feature("vpn-accelerator", "VPN Accelerator",
            "features.vpn_accelerator", short_help="Toggle VPN Accelerator", requires_restart=True),
    Feature("moderate-nat", "Moderate NAT", "features.moderate_nat",
            short_help="Toggle Moderate NAT", requires_restart=True),
    Feature("ipv6", "IPv6", "ipv6", "Toggle IPv6", requires_restart=True),
    Feature("anonymous-crash-reports", "Anonymous crash reports",
            "anonymous_crash_reports", short_help="Toggle anonymous crash reports",
            available_on_free_tier=True)
]
PORT_FORWARDING_FEATURE = Feature(
    "port-forwarding", "Port forwarding", "features.port_forwarding", requires_restart=True
)
CUSTOM_DNS_FEATURE = Feature(
    "custom-dns", "Custom DNS", "custom_dns", requires_restart=True
)
NETSHIELD_FEATURE = Feature("netshield", "NetShield", "features.netshield", requires_restart=True)
KILLSWITCH_FEATURE = Feature(
    "kill-switch", "Kill switch", "killswitch", available_on_free_tier=True
)


def _print_auth_required(controller: Controller) -> None:
    raise click.UsageError(
        "Authentication required to set feature status. "
        f"Please sign in with '{controller.program_name} {SIGNIN_COMMAND}'"
    )


def _print_requires_higher_tier(feature_human_friendly_name: str) -> None:
    raise click.UsageError(
        f"{feature_human_friendly_name} feature is not available "
        "on your current subscription plan. "
        "Please upgrade to access this feature."
    )


def _print_success_message(
    feature: Feature,
    mode: str,
    is_connection_active: Optional[bool] = None
) -> None:
    msg = f"{feature.human_friendly_name} has been set to {mode}"
    # Currently changing settings that should modify a current connection
    # are not taken into consideration.
    if feature.requires_restart and is_connection_active:
        msg += ", please establish a new VPN connection for " \
            "changes to take effect."

    click.echo(msg)


@click.group()
def config():
    """Configure Proton VPN settings"""


@config.group(name="set")
def set_group():
    """Set available settings and features
    """


def _register_bool_feature_command(group: click.Group, feature: Feature):
    @group.command(name=feature.command, short_help=feature.short_help)
    @click.argument("state", type=click.Choice(ToggleState, case_sensitive=False))
    @click.pass_context
    @run_async
    async def _bool_command(ctx: click.Context, state: ToggleState) -> None:
        controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
        try:
            await controller.save_config(feature, state.value)
        except AuthenticationRequiredError:
            _print_auth_required(controller)
        except RequiresHigherTierError:
            _print_requires_higher_tier(feature.human_friendly_name)
        else:
            _print_success_message(
                feature,
                state.get_human_friendly_state_string(),
                await controller.is_connection_active()
            )


for _feature in BOOL_FEATURES:
    _register_bool_feature_command(set_group, _feature)


@set_group.command(name=PORT_FORWARDING_FEATURE.command)
@click.argument("state", type=click.Choice(KillSwitchMode, case_sensitive=False))
@click.pass_context
@run_async
async def port_forwarding_command(ctx: click.Context, state: ToggleState) -> None:
    """Toggle Port forwarding"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)

    try:
        await controller.ensure_currently_connected_server_is_p2p_compatible()
        await controller.save_config(PORT_FORWARDING_FEATURE, state.value)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    except RequiresHigherTierError:
        _print_requires_higher_tier(PORT_FORWARDING_FEATURE.human_friendly_name)
    except InvalidServer:
        raise click.UsageError(  # pylint: disable=raise-missing-from
            f"{PORT_FORWARDING_FEATURE.human_friendly_name} can only be used "
            "with P2P-compatible servers. Please connect to a P2P server first."
        )
    else:
        _print_success_message(
            PORT_FORWARDING_FEATURE,
            state.get_human_friendly_state_string(),
            await controller.is_connection_active()
        )


@set_group.command(name=KILLSWITCH_FEATURE.command)
@click.argument("mode", type=click.Choice(KillSwitchMode, case_sensitive=False))
@click.pass_context
@run_async
async def killswitch_command(ctx: click.Context, mode: KillSwitchMode) -> None:
    """Set Kill Switch mode"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)

    try:
        await controller.save_config(KILLSWITCH_FEATURE, mode.value)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    else:
        _print_success_message(KILLSWITCH_FEATURE, mode.get_human_friendly_state_string())


@set_group.command(name=NETSHIELD_FEATURE.command)
@click.argument(
    "mode",
    type=click.Choice(
        [state.name.lower().replace("_", "-") for state in NetshieldMode],
        case_sensitive=False
    )
)
@click.pass_context
@run_async
async def netshield_command(ctx: click.Context, mode: str) -> None:
    """Set NetShield level

    The list comprehension in the above `type` is mainly so that click
    can display options with hyphens (-) instead of underscores (_) because
    what it does is that is uses the members name and converts it to lower-case.
    """
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    # Convert it back to a enum object
    mode = NetshieldMode[mode.upper().replace("-", "_")]

    try:
        await controller.save_config(NETSHIELD_FEATURE, mode.value)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    except RequiresHigherTierError:
        _print_requires_higher_tier(NETSHIELD_FEATURE.human_friendly_name)
    else:
        _print_success_message(
            NETSHIELD_FEATURE,
            f"'{mode.get_human_friendly_state_string()}'",
            await controller.is_connection_active()
        )


@set_group.command(name=CUSTOM_DNS_FEATURE.command)
@click.argument("state", type=click.Choice(ToggleState, case_sensitive=False))
@click.option("--dns", "dns_csv", help="Comma-separated DNS servers, e.g. 1.1.1.1,9.9.9.9")
@click.pass_context
@run_async
async def custom_dns_command(ctx: click.Context, state: ToggleState, dns_csv: str | None) -> None:
    """Toggle Custom DNS and optionally set DNS servers"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)

    parsed_dns_ips = []
    dns_list = [x.strip() for x in dns_csv.split(",") if x.strip()] if dns_csv else []

    if state == ToggleState.ON:
        if not dns_list:
            raise click.UsageError(
                f"When enabling {CUSTOM_DNS_FEATURE.human_friendly_name} feature "
                "you must provide a list of comma separated DNS's."
            )

        try:
            parsed_dns_ips = controller.parse_dns_ips(dns_list)
        except InvalidDNS as excp:
            raise click.UsageError(
                f"Invalid DNS address '{excp.dns}'. Please provide a valid IPv4 address."
            )

    custom_dns = controller.to_custom_dns(state.value, parsed_dns_ips)

    try:
        await controller.save_config(CUSTOM_DNS_FEATURE, custom_dns)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    else:
        _print_success_message(
            CUSTOM_DNS_FEATURE,
            state.get_human_friendly_state_string(),
            await controller.is_connection_active()
        )
