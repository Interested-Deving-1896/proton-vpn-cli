"""
Exception handling module.

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
import asyncio
import sys
import threading
from typing import List


class ExceptionHandler:  # pylint: disable=too-few-public-methods
    """
    Helper class used to silently absorb specified types of unhandled exceptions
    """

    absorbed_exceptions: List[BaseException]

    @staticmethod
    def __custom_exception_hook(exc_type, exc_value, exc_traceback):
        absorb = False
        for absorb_exc in ExceptionHandler.absorbed_exceptions:
            if issubclass(exc_type, absorb_exc):
                absorb = True
                break

        if not absorb:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

    @staticmethod
    def __asyncio_exception_handler(_, context):
        exception = context.get('exception', None)
        if exception:
            exc_info = (type(exception), exception, exception.__traceback__)
            ExceptionHandler.__custom_exception_hook(*exc_info)

    @staticmethod
    def absorb_uncaught_exceptions(exceptions: List[BaseException]):
        """
        Silences list of provided exceptions if raised and uncaught
        """
        ExceptionHandler.absorbed_exceptions = exceptions

        sys.excepthook = ExceptionHandler.__custom_exception_hook
        threading.excepthook = ExceptionHandler.__custom_exception_hook
        asyncio.get_event_loop().set_exception_handler(
            ExceptionHandler.__asyncio_exception_handler
        )
