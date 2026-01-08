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
from __future__ import annotations
from typing import Optional
import enum
import click
from proton.vpn.killswitch.interface import KillSwitchState
from proton.vpn.core.settings.features import NetShield
from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller, Feature
from proton.vpn.cli.core.exceptions import AuthenticationRequiredError, \
    RequiresHigherTierError, InvalidDNS
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

    @staticmethod
    def to_list_of_str() -> list[str]:
        """Converts to a list of strings

        This is a necessary change because <8.2.0, `click.Choice`
        can only take a list of strings. With version >=8.2.0 click
        supports non-string choices (you can pass an enum class).
        This change is to make it backwards compatible, as on Fedora 43
        click is v8.1.7 and on Ubuntu 24.04 v8.1.6.
        See more here: https://click.palletsprojects.com/en/stable/api/#click.Choice
        """
        return [state.name.lower() for state in ToggleState]

    @staticmethod
    def from_str(value: str) -> ToggleState:
        """Returns enum based on provided value
        """
        return ToggleState[value.upper()]


class KillSwitchMode(enum.Enum):
    """Represent the various kill switch states that a user can select
    """
    OFF = KillSwitchState.OFF
    STANDARD = KillSwitchState.ON
    # Advanced option is temporarily removed as
    # currently is not possible to establish a connection with it enabled,
    # while being disconnected.

    def get_human_friendly_state_string(self) -> str:
        """Returns human friendly state string of the currently
        selected choice.
        """
        if self == KillSwitchMode.OFF:
            return "disabled"

        return "standard"

    @staticmethod
    def to_list_of_str() -> list[str]:
        """Converts to a list of strings

        See explanation above.
        """
        return [state.name.lower() for state in KillSwitchMode]

    @staticmethod
    def from_str(value: str) -> KillSwitchMode:
        """Returns enum based on provided value
        """
        return KillSwitchMode[value.upper()]


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

    @staticmethod
    def to_list_of_str() -> list[str]:
        """Converts to a list of strings

        The list comprehension is mainly so that click
        can display options with hyphens (-) instead of underscores (_) because
        it uses the members names and converts them to lower-case.
        This change is not related to the previous changes in other enum classes.
        """
        return [state.name.lower().replace("_", "-") for state in NetshieldMode]

    @staticmethod
    def from_str(value: str) -> NetshieldMode:
        """Returns enum based on provided value
        """
        return NetshieldMode[value.replace("-", "_").upper()]


REQUIRES_SUBSCRIPTION_PLAN = ". Requires subscription plan"

BOOL_FEATURES = [
    Feature(
        "vpn-accelerator", "VPN Accelerator",
        "features.vpn_accelerator",
        short_help=f"Toggle VPN Accelerator{REQUIRES_SUBSCRIPTION_PLAN}",
        requires_restart=True),
    Feature(
        "moderate-nat",
        "Moderate NAT",
        "features.moderate_nat",
        short_help=f"Toggle Moderate NAT{REQUIRES_SUBSCRIPTION_PLAN}",
        requires_restart=True),
    Feature(
        "ipv6",
        "IPv6",
        "ipv6",
        "Toggle IPv6",
        requires_restart=True,
        available_on_free_tier=True),
    Feature(
        "anonymous-crash-reports",
        "Anonymous crash reports",
        "anonymous_crash_reports",
        short_help="Toggle anonymous crash reports",
        available_on_free_tier=True),
    Feature(
        "port-forwarding", "Port forwarding",
        "features.port_forwarding",
        short_help=f"Toggle Port forwarding{REQUIRES_SUBSCRIPTION_PLAN}",
        requires_restart=True)
]
CUSTOM_DNS_FEATURE = Feature(
    "custom-dns", "Custom DNS",
    "custom_dns", short_help=f"Toggle Custom DNS and set DNS servers{REQUIRES_SUBSCRIPTION_PLAN}",
    requires_restart=True
)
NETSHIELD_FEATURE = Feature(
    "netshield", "NetShield",
    "features.netshield",
    short_help=f"Set NetShield mode{REQUIRES_SUBSCRIPTION_PLAN}",
    requires_restart=True)
KILLSWITCH_FEATURE = Feature(
    "kill-switch", "Kill switch",
    "killswitch", available_on_free_tier=True)


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
    @group.command(name=feature.command, help=feature.short_help)
    @click.argument("state", type=click.Choice(ToggleState.to_list_of_str(), case_sensitive=False))
    @click.pass_context
    @run_async
    async def _bool_command(ctx: click.Context, state: str) -> None:
        controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
        toggle_state = ToggleState.from_str(state)
        try:
            await controller.save_config(feature, toggle_state.value)
        except AuthenticationRequiredError:
            _print_auth_required(controller)
        except RequiresHigherTierError:
            _print_requires_higher_tier(feature.human_friendly_name)
        else:
            _print_success_message(
                feature,
                toggle_state.get_human_friendly_state_string(),
                await controller.is_connection_active()
            )


for _feature in BOOL_FEATURES:
    _register_bool_feature_command(set_group, _feature)


@set_group.command(name=KILLSWITCH_FEATURE.command, help=KILLSWITCH_FEATURE.short_help)
@click.argument("mode", type=click.Choice(KillSwitchMode.to_list_of_str(), case_sensitive=False))
@click.pass_context
@run_async
async def killswitch_command(ctx: click.Context, mode: str) -> None:
    """Set Kill Switch mode"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    killswitch_mode = KillSwitchMode.from_str(mode)

    try:
        await controller.save_config(KILLSWITCH_FEATURE, killswitch_mode.value)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    else:
        _print_success_message(
            KILLSWITCH_FEATURE, killswitch_mode.get_human_friendly_state_string()
        )


@set_group.command(name=NETSHIELD_FEATURE.command, help=NETSHIELD_FEATURE.short_help)
@click.argument(
    "mode",
    type=click.Choice(NetshieldMode.to_list_of_str(), case_sensitive=False),
)
@click.pass_context
@run_async
async def netshield_command(ctx: click.Context, mode: str) -> None:
    """Set NetShield mode
    """
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    netshield_mode = NetshieldMode.from_str(mode)

    try:
        await controller.save_config(NETSHIELD_FEATURE, netshield_mode.value)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    except RequiresHigherTierError:
        _print_requires_higher_tier(NETSHIELD_FEATURE.human_friendly_name)
    else:
        _print_success_message(
            NETSHIELD_FEATURE,
            f"'{netshield_mode.get_human_friendly_state_string()}'",
            await controller.is_connection_active()
        )


@set_group.command(name=CUSTOM_DNS_FEATURE.command, help=CUSTOM_DNS_FEATURE.short_help)
@click.argument("state", type=click.Choice(ToggleState.to_list_of_str(), case_sensitive=False))
@click.option("--dns", "dns_csv", help="Comma-separated DNS servers, e.g. 1.1.1.1,9.9.9.9")
@click.pass_context
@run_async
async def custom_dns_command(ctx: click.Context, state: str, dns_csv: str | None) -> None:
    """Toggle Custom DNS and set DNS servers"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    toggle_state = ToggleState.from_str(state)

    parsed_dns_ips = []
    dns_list = [x.strip() for x in dns_csv.split(",") if x.strip()] if dns_csv else []

    if toggle_state == ToggleState.ON:
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

    custom_dns = controller.to_custom_dns(toggle_state.value, parsed_dns_ips)

    try:
        await controller.save_config(CUSTOM_DNS_FEATURE, custom_dns)
    except AuthenticationRequiredError:
        _print_auth_required(controller)
    except RequiresHigherTierError:
        _print_requires_higher_tier(CUSTOM_DNS_FEATURE.human_friendly_name)
    else:
        _print_success_message(
            CUSTOM_DNS_FEATURE,
            toggle_state.get_human_friendly_state_string(),
            await controller.is_connection_active()
        )
