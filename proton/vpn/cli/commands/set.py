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
import click
from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller, Feature
from proton.vpn.cli.core.exceptions import AuthenticationRequiredError, \
    RequiresHigherTierError
from proton.vpn.cli.commands.account import SIGNIN_COMMAND


BOOL_SET_OPTIONS = {
    "on": True,
    "off": False,
}
HUMAN_FRIENDLY_SET_OPTIONS = {
    "on": "enabled",
    "off": "disabled"
}
FEATURES = [
    Feature("port-forwarding", "Port forwarding",
            "features.port_forwarding", requires_restart=True),
    Feature("vpn-accelerator", "VPN Accelerator",
            "features.vpn_accelerator", requires_restart=True),
    Feature("moderate-nat", "Moderate NAT", "features.moderate_nat", requires_restart=True),
    Feature("ipv6", "IPv6", "ipv6", requires_restart=True),
    Feature("anonymous-crash-reports", "Anonymous crash reports",
            "anonymous_crash_reports", available_on_free_tier=True),
]


@click.group()
def config():
    """Configure Proton VPN settings."""


@config.command(
    name="set",
    epilog="""\b
              Examples:
                  protonvpn set port-forwarding on          Enable port-forwarding
                  protonvpn set vpn-accelerator on          Enable vpn-accelerator
                  protonvpn set moderate-nat on             Enable moderate-nat
                  protonvpn set ipv6 on                     Enable IPv6
                  protonvpn set anonymous-crash-reports on  Enable anonymous crash reports""")
@click.argument("feature", type=click.Choice([f.command for f in FEATURES], case_sensitive=False))
@click.argument("state", type=click.Choice(["on", "off"], case_sensitive=False))
@click.pass_context
@run_async
async def set_command(ctx: click.Context, feature: str, state: str):
    """Set available settings and features
    """
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    feature = [f for f in FEATURES if f.command == feature][0]

    try:
        await controller.save_feature(
            feature,
            BOOL_SET_OPTIONS[state]
        )
    except AuthenticationRequiredError:
        print(
            "Authentication required to set feature status. "
            f"Please sign in with '{controller.program_name} {SIGNIN_COMMAND}'."
        )
    except RequiresHigherTierError:
        print(
            f"{feature.human_friendly_name} feature is not available "
            "on your current subscription plan. "
            "Please upgrade to access this feature."
        )
    else:
        msg = f"{feature.human_friendly_name} has been " \
            f"{HUMAN_FRIENDLY_SET_OPTIONS[state]}"
        # Currently changing settings that should modify a current connection
        # are not taken into consideration.
        if feature.requires_restart:
            msg += ", please establish a new VPN connection for " \
                "changes to take effect."

        print(msg)
