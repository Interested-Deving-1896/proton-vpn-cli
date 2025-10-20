
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
from importlib.metadata import version, PackageNotFoundError

import click

from proton.vpn.cli.commands.account import login, logout, info
from proton.vpn.cli.commands.server import connect, disconnect
from proton.vpn.cli.core.controller import Params

try:
    __version__ = version("proton-vpn-cli")
except PackageNotFoundError:
    __version__ = "development"

PROTON_VPN_LOGO = """
%%%%%%%%%%%%     #########                ##                       ###     ############ ####    ###
%%%%%%%%   @%    ###    ###              ####                       ###   #######    ########   ###
 %%%%%%%%@%%%           ############### ##############  #######     #### #### ###    ########## ###
  %%%%%% %%       ######## ##  ####  ######## ####  #######  ###     ### ###  ######### ### #######
   %%%% %%       ###       ##  ####  ######## ####  #######  ###      #####   ###       ###   #####
    %%%%%        ###       ##   ########  #### ####### ####  ###      #####   ###       ###    ####"""  # noqa: E501 # pylint: disable=C0301


class _OrderedGroup(click.Group):
    """OrderedGroup lists commands in the order that they were added"""
    def list_commands(self, ctx):
        return self.commands


@click.group(
    cls=_OrderedGroup,
    help=f"\b {PROTON_VPN_LOGO} {__version__}",
    epilog="""\b
              NEED HELP?
              Report issues:  https://protonvpn.com/support-form""")
@click.option(
    '-v',
    '--verbose',
    help="Show detailed output during command execution",
    is_flag=True,
    default=False)
@click.pass_context
def app(ctx, verbose):
    """Groups all CLI commands"""
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
