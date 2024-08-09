"""
    Basic tester
"""

from typing import Optional
from stub import MetaModule


async def test_setup(self: MetaModule) -> Optional[Exception]:
    """
    Called after setup

    Arguments
    ---------
    self
        The module to be tested
    
    Returns
    -------
    Exception, optional
        None if everything went well, in the other case
        it must return an exception
    """



async def test_install(self: MetaModule) -> Optional[Exception]:
    """
    Called after install

    Arguments
    ---------
    self
        The module to be tested
    
    Returns
    -------
    Exception, optional
        None if everything went well, in the other case
        it must return an exception
    """


async def test_post_install(self: MetaModule) -> Optional[Exception]:
    """
    Called after post_install

    Arguments
    ---------
    self
        The module to be tested
    
    Returns
    -------
    Exception, optional
        None if everything went well, in the other case
        it must return an exception
    """


test_module: str = 'YourModule'
steps: dict[str, Optional[callable]] = {
    'setup': test_setup,
    'install': test_install,
    'post_install': test_post_install
}
