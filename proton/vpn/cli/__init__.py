
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

import asyncio
import click

from proton.vpn.cli.commands.account import login, logout, info
from proton.vpn.cli.commands.server import connect, disconnect
from proton.vpn.cli.core.controller import Params


@click.group()
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.pass_context
def app(ctx, verbose):
    """
    The top level command for the application, allows configuration of flags
    that are shared between all commands.
    """
    ctx.obj.verbose = verbose


# account related functionality
app.add_command(login)
app.add_command(logout)
app.add_command(info)

# server related functionality
app.add_command(connect)
app.add_command(disconnect)


def main():
    """Runs the CLI."""

    asyncio.run(app(obj=Params()))  # pylint: disable=E1120
