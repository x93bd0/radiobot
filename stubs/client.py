"""
    Stub file
"""

from abc import ABCMeta, abstractmethod
from typing import Any

from pyrogram.client import Client
from .module import MetaModule


class MainException(Exception):
    """
    An exception raised from the inside
    of the MainClient logic (non-related to modules)
    """


class MetaClient(Client, metaclass=ABCMeta):
    """
    Stub definition for bot MainClient
    """

    modules: dict[str, MetaModule]
    defby: dict[str, MetaModule]
    config: dict[str, Any]

    @abstractmethod
    def register_configuration(
        self, module: MetaModule,
        config: dict[str, Any],
        check_collisions: bool = True
    ):
        """
        Registers a global configuration for
        a module. Before it does so, it checks
        for collisions on the already
        configuration registered configurations
        (only if check_collisions = True)
        """
