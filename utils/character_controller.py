import json
import yaml
from utils.config_manager import get_config_value, set_config_value

# Init Character
_char_name = get_config_value("char_name", "Waifu")
_character_card = get_config_value("character_card", "Waifu")

def get_character_name():
    return _char_name

def refresh_character_name():
    global _char_name
    _char_name = get_config_value("char_name", "Waifu")

def set_char_name(new_name):
    
    global _char_name
    set_config_value("char_name", new_name)
    _char_name = new_name

def get_character_card():
    return _character_card

def load_character_card():
    card_name = get_character_card()
    file_path = f"Configurables/{card_name}_CharacterCard.yaml"
    default_path = "Configurables/CharacterCard.yaml"

    try:
        with open(file_path, 'r', encoding='utf-8') as infile:
            data = yaml.safe_load(infile)
            return data.get("Character Card", "⚠️ Character Card field not found.")
    except FileNotFoundError:
        try:
            with open(default_path, 'r', encoding='utf-8') as infile:
                data = yaml.safe_load(infile)
                return data.get("Character Card", "⚠️ Default Character Card field not found.")
        except FileNotFoundError:
            print(f"🚨 Neither {file_path} nor {default_path} could be found.")
            return
