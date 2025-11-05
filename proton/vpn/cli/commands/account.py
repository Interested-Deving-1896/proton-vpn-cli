
"""
Account/Authentication related commands.

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
import getpass

import click
from proton.vpn.cli.core.controller import Controller
from proton.vpn.cli.core.run_async import run_async


@click.command()
@click.argument('username')
@click.pass_context
@run_async
async def signin(ctx, username: str):
    """Sign in with Proton VPN credentials"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    await controller.login(username,
                           getpass.getpass,
                           lambda: getpass.getpass("2FA Token: "))


@click.command()
@click.pass_context
@run_async
async def signout(ctx):
    """Disconnect and remove credentials """
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    await controller.logout()


@click.command()
@click.pass_context
@run_async
async def info(ctx):
    """Display your Proton VPN account information"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)
    click.echo(f'{controller.account_info()}')
