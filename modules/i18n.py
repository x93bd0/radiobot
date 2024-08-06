"""
    Internacionalization (i18n)
"""

import json
from stub import MetaClient, MetaModule


class Module(MetaModule):
    """
    Internacionalization module
    """

    def __init__(self, client: MetaClient) -> None:
        self.identifier: str = 'I18n'

        self.client: MetaClient = client
        self.default: str = 'en'

        self.strings: dict[str, dict[str, str]] = {}

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        self.client.register_configuration(self, {
            'i18n_strings': 'strings.json'
        })

    async def post_install(self) -> None:
        self.update_strings(True)


    def update_strings(self, clean_update: bool = False) -> None:
        """
        Updates all strings from the configuration
        file
        """

        with open(
            self.client.config['i18n_strings'],
            encoding='utf-8'
        ) as i18n:
            temp: dict[str, dict[str, str]] = json.load(i18n)
            self.default = next(iter(temp))

            if not clean_update:
                self.strings.update(temp)

            else:
                self.strings = temp

    def __getitem__(self, key: object) -> dict[str, str]:
        if hasattr(key, 'lang_code'):
            return self.strings.get(
                key.lang_code, self.strings[self.default])

        return self.strings[self.default]
