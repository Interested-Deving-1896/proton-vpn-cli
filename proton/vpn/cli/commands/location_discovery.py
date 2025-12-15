"""
Server/Connection related commands.

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
from tabulate import tabulate
from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.controller import Controller
from proton.vpn.cli.core.exceptions import \
    AuthenticationRequiredError


@click.command()
@click.pass_context
@run_async
async def countries(ctx, controller: Controller = None):
    """Display all available countries."""
    if not controller:
        controller = await Controller.create(params=ctx.obj, click_ctx=ctx)

    try:
        all_countries = await controller.get_all_countries()
    except AuthenticationRequiredError:
        print("Authentication required to view complete country list. "
              "Please sign in with 'protonvpn signin'.")
        return

    table = tabulate(
        [(country.name, country.code.upper()) for country in all_countries],
        headers=["Country", "Code"],
        tablefmt="simple",
        stralign="left",
        numalign="right",
    )
    click.echo_via_pager(table)
