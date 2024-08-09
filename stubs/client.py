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


class SettingsCollision(Exception):
    """
    Raised by `MetaClient.register_configuration` when
    it encounters any conflicting settings key
    """


class InvalidSettings(Exception):
    """
    Raised by `MetaClient.require_configuration` when
    it doens't encounter any matching setting
    """


class MetaClient(Client, metaclass=ABCMeta):
    """
    Stub definition for bot MainClient
    """

    identifier: str = 'MainClient'

    modules: dict[str, MetaModule]
    defby: dict[str, MetaModule]
    config: dict[str, Any]

    @abstractmethod
    def require_configuration(
        self, module: MetaModule,
        config: str
    ) -> None:
        """
        Checks if a global configuration is
        available in the current config registry.

        Parameters
        ----------
        module
            The module that requires that configuration
            (may be the same MetaClient)
        config
            Configuration key to search

        Raises
        ------
        InvalidSettings
            In the case of a missing configuration
        """

    @abstractmethod
    def register_configuration(
        self, module: MetaModule,
        config: dict[str, Any],
        check_collisions: bool = True
    ):
        """Registers a global configuration for a module.

        Parameters
        ----------
        module
            The module that is going to register
            the configuration
        config
            A dict containing a key-value formatted
            settings for the module
        check_collisions
            Checks for collisions in the configuration
            (already registered settings key)
        
        Raises
        ------
        SettingsCollision
            Raised if `check_collisions` is set to true, and
            there is any collision between module configurations
        """
