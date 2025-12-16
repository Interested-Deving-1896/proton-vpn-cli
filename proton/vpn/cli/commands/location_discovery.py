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
from proton.vpn.session.servers.types import ServerFeatureEnum
from proton.vpn.cli.core.exceptions import AuthenticationRequiredError, \
    CountryCodeError, CountryNameError


FEATURES_TO_DISPLAY = {
    ServerFeatureEnum.P2P: "P2P",
    ServerFeatureEnum.SECURE_CORE: "Secure Core",
    ServerFeatureEnum.TOR: "Tor",
}


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


@click.command(
    epilog="""\b
              Examples:
                  protonvpn cities --country PT               Display cities in Portugal
                  protonvpn cities --country US               Display cities in United States""")
@click.pass_context
@click.option(
    "--country", "country_input",
    required=True,
    help="""\b
            Display servers in specified country.
            Country code (US, GB, DE) or full name ("United States")""")
@run_async
async def cities(ctx, country_input: str):
    """Display cities within a country"""
    controller = await Controller.create(params=ctx.obj, click_ctx=ctx)

    try:
        all_countries = await controller.get_all_countries()
    except AuthenticationRequiredError:
        print("Authentication required to view complete country list. "
              "Please sign in with 'protonvpn signin'.")
        return

    try:
        country_code = controller.validate_country_input(country_input)
    except CountryCodeError:
        print(f"Invalid country code '{country_input}'. Please use a valid country code.")
        return
    except CountryNameError:
        print(f"Invalid country name '{country_input}'. Please use a valid country name.")
        return

    country = list(filter(lambda country: country.code == country_code.lower(), all_countries))

    if not country:
        print(
            f"Country '{country_input}' not found. "
            "Use 'protonvpn countries' to see available options."
        )
        return

    country = country.pop()
    table_data = []

    for city in country.cities:
        only_displayable_features = [
            feature_display_name
            for feature, feature_display_name in FEATURES_TO_DISPLAY.items()
            if feature in city.features
        ]
        sorted_human_readable_features = sorted(only_displayable_features)

        table_data.append((city.name, ", ".join(sorted_human_readable_features)))

    table = tabulate(
        table_data,
        headers=["City", "Features"],
        tablefmt="simple",
        stralign="left",
        numalign="right",
    )

    print(f"\nCities in {country.name}:\n")
    print(table, "\n")
