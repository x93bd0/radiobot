<!-- Format: https://github.com/othneildrew/Best-README-Template/ -->

<a id="readme-top"></a>
[![Built With][BuiltWithPy-Badge]][BuiltWithPy-Link]
[![Stargazers][Stars-Badge]][Stars-Link]
[![License][License-Badge]][License-Link]
[![Telegram Channel][Telegram-Badge]][Telegram-Link]

<br />
<div align="center">
  <a href="https://github.com/othneildrew/Best-README-Template">
    <img src="res/pfpic.jpeg" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">RadioBot</h3>
  <p align="center">
    A Telegram bot for managing playlists on Video Chats
    <br />
    <a href="https://t.me/xradio_bot"><strong>» Main Instance «</strong></a>
    <br />
    <br />
    <a href="https://github.com/x93bd0/radiobot/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/x93bd0/radiobot/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

## About The Project
RadioBot is a simple [Telegram](https://telegram.org/) bot, for playing audio's and managing playlists on [Telegram Voice Chats](https://telegram.org/blog/voice-chats) easily. It's built with simplicity and efficiency in mind (altrought right now is isn't).

It packs some necessary features for it to be a complete audio player experience:
* Expected functionality: **Play**, **Stop**, **Next**, **Pause**, **Resume**, **Volume**
* Managing of Playlists: **See current playlist**, ([WIP]: **Export current playlist**, **Load exported playlist**)
* Playing from **numerous sites** (*using Yt-Dlp*), from **direct links** and from **Telegram audio files**
* [WIP] Internationalization
* [WIP] Ability to play audio on channels voice chats
* [WIP] Role management suite (for allowing users that aren't the group owners/moderators to control the player behaviour)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Installation
1. Get your API id & hash from my.telegram.org
2. Create a file called .env and put your id & hash there
   ```env
   # Your API ID
   TG_API_ID=1234567
   # Your API hash
   TG_API_HASH=abcdefghijklmnopqrstuwxyz1234567
   # *.session files prefix
   CLIENT_NAME=bot
   ```
3. Install requirements with pip
   ```bash
   python3 -m pip install -r requirements.txt
   ```
4. Run for the first time and login the bot & userbot (respectively)
   ```bash
   python3 __main__.py
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the LGPL-3.0 License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

x93bd - [@x93bd](https://t.me/x93bd) - x93bd0@gmail.com

Project Link: [https://github.com/x93bd0/radiobot](https://github.com/x93bd0/radiobot)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

* [Pyrogram](https://github.com/PyrogramMod/PyrogramMod)
* [PyTgCalls](https://github.com/pytgcalls/pytgcalls)
* [Yt-Dlp](https://github.com/yt-dlp/yt-dlp)
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

[BuiltWithPy-Badge]: https://img.shields.io/badge/Built_With-Python-blue?style=for-the-badge&logo=python&logoColor=white
[BuiltWithPy-Link]: https://python.org/

[Stars-Badge]: https://img.shields.io/github/stars/x93bd0/radiobot?style=for-the-badge
[Stars-Link]: https://github.com/x93bd0/radiobot/stargazers

[License-Badge]: https://img.shields.io/github/license/x93bd0/radiobot?style=for-the-badge
[License-Link]: https://github.com/x93bd0/radiobot/blob/master/LICENSE.txt

[Telegram-Badge]: https://img.shields.io/badge/Telegram_Channel-grey?style=for-the-badge&logo=telegram&logoColor=white
[Telegram-Link]: https://t.me/x93dev
