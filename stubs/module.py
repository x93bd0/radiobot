"""
    Stub file
"""

from abc import ABCMeta, abstractmethod
from typing import Any


class MetaModule(metaclass=ABCMeta):
    """
    Stub definition for bot modules
    """

    identifier: str
    client: 'MetaClient'

    @abstractmethod
    async def setup(self) -> None:
        """
        Set's everything up for the first
        execution
        """

    @abstractmethod
    async def install(self) -> None:
        """
        Installs the module on the MainClient
        """

    @abstractmethod
    async def post_install(self) -> None:
        """
        Used for extra configuration needed
        after the installation process is completed
        (like, using another module)
        """

    @abstractmethod
    def stub(self, root: dict[str, Any]) -> None:
        """
        Updates the new stub root with the
        module info
        """
