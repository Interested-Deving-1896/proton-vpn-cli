
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
import getpass

import click
from proton.vpn.cli.core.controller import Controller
from proton.vpn.cli.core.run_async import run_async
from proton.vpn.cli.core.wait_for_current_tasks import wait_for_current_tasks


@click.command()
@click.argument('username')
@click.pass_context
@run_async
async def login(ctx, username: str):
    """Connects to a proton vpn account"""
    controller = await Controller.create(params=ctx.obj)
    await wait_for_current_tasks()
    await controller.login(username, getpass.getpass(),
                           lambda: getpass.getpass("Token: "))


@click.command()
@click.pass_context
@run_async
async def logout(ctx):
    """Disconnects from a proton vpn account"""
    controller = await Controller.create(params=ctx.obj)
    await wait_for_current_tasks()
    await controller.logout()


@click.command()
@click.pass_context
@run_async
async def info(ctx):
    """Prints account information to stdout"""
    controller = Controller(params=ctx.obj)  # We dont need the connector here
    click.echo(f'{controller.account_info()}')


@click.group()  # nosemgrep: python.lang.best-practice.pass-body.pass-body-fn
def account():
    """The group command for the account commands"""


account.add_command(login)
account.add_command(logout)
account.add_command(info)
