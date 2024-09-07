# z-waif
Fully local &amp; open source AI Waifu. VTube Studio, Discord, Minecraft, custom made RAG (long term memory), alarm, and plenty more! Has a WebUI and hotkey shortcuts.

Uses Oobabooga, RVC, and Whisper to run AI.


|<img src="https://i.imgur.com/3a5eGQK.png" alt="drawing" width="400"/> | <img src="https://i.imgur.com/BCE1snE.png" alt="drawing" width="400"/> |
|:---:|:---:|
|<img src="https://i.imgur.com/paMSUiy.jpeg" alt="drawing" width="400"/> | <img src="https://i.imgur.com/vXx1vXm.jpeg" alt="drawing" width="400"/> |


## Requires
- Windows 10/11
- ~11 GB VRAM on a CUDA GPU (Reccomended 16GB)

## YouTube Showcase:

[![IMAGE ALT TEXT](http://img.youtube.com/vi/XBZL500hloU/0.jpg)](http://www.youtube.com/watch?v=XBZL500hloU "Z-Waif Showcase")

## YouTube Install Tutorial:

[![IMAGE ALT TEXT](http://img.youtube.com/vi/IGMregWfhGI/0.jpg)](http://www.youtube.com/watch?v=IGMregWfhGI "Z-Waif Install")

## Changelog

v1.1

- Visual System
	- Toggleable as a module
	- Able to take new images or upload them directly for the AI to see
	- Runs using Ooba, like with the text
		- Can set the port to the existing, default one, or load another instance to dual wield
	- Option to see images before being sent
		- Can retake them
		- Use C/X on the keyboard to confirm
	- Automatically shrinks images to a proper size
- Fixed bits of the Minecraft module
	- Configurable "MinecraftUsername" to set your AI's name (stops feedback loops)
	- Configurable "MinecraftUsernameFollow" to set who your AI follows when doing "#follow"

---.---.---.---

V1.0

- Initial public release of Z-Waif. Contains:
	- WebUI
	- RAG
	- Discord
	- Semi-Minecraft Functionality
	- VTuber Emotes
	- Hotkeys
	- Various other initial release items


## Links
Here is [some documentation](https://docs.google.com/document/d/1qzY09kcwfbZTaoJoQZDAWv282z88jeUCadivLnKDXCo/edit?usp=sharing) that you can look at. I am still in the process of making tutorials and documentation!

Credit to [this other AI waifu project](https://github.com/TumblerWarren/Virtual_Avatar_ChatBot) for making the original base code/skeleton used here!


## Current To-Do

- Make the RAG/Long Term Memory be multiprocessed for better performance
- Fix repetition issues at the end of speech to text Whisper by manually removing
- Look more into optimal LLMs and configs
- Fix issues where leaving the bot on for a while can cause a bit more lag between messages
- Fix issues where leaving the WebUI open a long time can freeze it and spike CPU usage
- Create more Youtube tutorials and other related content
- Create more documentation, both in the ReadMe and in the Google Doc
