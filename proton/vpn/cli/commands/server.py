
"""
Semver utils.

Copyright (c) 2023 Proton AG

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
from asyncio import CancelledError
from typing import Optional

import click

from proton.vpn.cli.core.exceptions import \
    AuthenticationRequiredError, \
    CountryCodeError, \
    CountryNameError, \
    RequiresHigherTierError
from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller, DEFAULT_CLI_NAME
from proton.vpn.cli.core.wait_for_current_tasks import wait_for_current_tasks
from proton.vpn.session.exceptions import ServerNotFoundError
from proton.vpn.session.servers.types import LogicalServer


@click.command(
    epilog="""\b
              Examples:
                  protonvpn connect --country US
                  protonvpn connect --country "United States"
                  protonvpn connect --city "New York" """)
@click.pass_context
@click.argument("server_name", required=False)
@click.option(
    "--country",
    default=None,
    help="""\b
            Connect to fastest server in specified country
            Country code (US, GB, DE) or full name ("United States")""")
@click.option(
    "--city",
    default=None,
    help="""\b
            Connect to fastest server in specified city
            City name (use quotes for multi-word: "New York", "Los Angeles")""")
@run_async
async def connect(
    ctx,
    server_name: Optional[str],
    city: Optional[str],
    country: Optional[str]
):
    """Connect to Proton VPN"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    # Silence cancelled exceptions raised by tasks we don't need to wait for after connection.
    # For example, some tasks are usually created to process a second Connected state broadcasted
    # to signal that the VPN server successfully applied the requested connection features.
    controller.set_uncaught_exceptions_to_absorb([CancelledError])
    server = None
    connection_state = None

    # attempt to find a satisfactory server, and connect to it
    try:
        server = await controller.find_logical_server(server_name, country, city)
        if not server:
            print("The selected server is currently unavailable")
            return

        connection_state = await controller.connect(server)

    except AuthenticationRequiredError:
        print("Authentication required. Please login before connecting.")
    except ServerNotFoundError as exc:
        if server_name:
            print(f"Invalid server ID '{server_name}'. "
                  "Please use a valid server ID from the server list.")
        elif city:
            print(f"City '{city}' not found or no servers available.")
        else:
            print(str(exc))
    except CountryCodeError:
        print(f"Invalid country code '{country}'. Please use a valid country code.")
    except CountryNameError:
        print(f"Invalid country name '{country}'. Please use a valid country name.")
    except RequiresHigherTierError:
        free_user = controller.user_tier == 0
        if free_user:
            _display_free_user_limitation(controller, server_name, city, country)

    if connection_state:
        # notify user of successful connection and server details
        current_connection = connection_state.context.connection
        server_ip = connection_state.context.event.context.connection_details.server_ipv4
        print(f"Connected to {current_connection.server_name} "
              f"in {_get_most_specific_server_location(server)}. "
              f"Your new IP address is {server_ip}.")
    elif server:
        # we found a server but the connection failed
        print("Connection failed. "
              "Try connecting to a different server or check your network settings.")


@click.command()
@click.pass_context
@run_async
async def disconnect(ctx):
    """Disconnect from Proton VPN"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    await controller.disconnect()

    # wait for post-disconnect notification killswitch implementation setting
    await wait_for_current_tasks()


def _get_most_specific_server_location(server: LogicalServer) -> str:
    if server.city:
        return f"{server.city}, {server.entry_country_name}"

    return server.entry_country_name


def _display_free_user_limitation(
    controller: Controller,
    server_name: Optional[str],
    city: Optional[str],
    country: Optional[str]
):
    free_user = controller.user_tier == 0
    if not free_user:
        return

    # when specifying a server name, the user requires a paying tier
    if server_name:
        proton_cli_name = controller.program_name or DEFAULT_CLI_NAME
        print(f"Server selection by ID is not available on the free plan."
              f" Please use '{proton_cli_name} connect' to connect to available free servers"
              " or upgrade to access all servers.")
        return

    # when specifying a country or city, the user requires a paying tier
    if country or city:
        proton_cli_name = controller.program_name or DEFAULT_CLI_NAME
        print("Location selection is not available on the free plan. "
              f"Please use '{proton_cli_name} connect' to connect to available free servers "
              "or upgrade to choose your location.")
        return
