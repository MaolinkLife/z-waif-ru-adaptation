import utils.cane_lib
import json
import utils.zw_logging
import os
from utils.character_controller import get_character_name
from pprint import pprint

do_log_lore = True
total_lore_default = "Here is some lore about the current topics from your lorebook, please reference them;\n\n"


# Load the LORE_BOOK, it is now JSON configurable!
# with open("Configurables/Lorebook.json", 'r', encoding="utf-8") as openfile:
#     LORE_BOOK = json.load(openfile)

def load_lorebook():
    char_name = get_character_name()
    custom_path = f"Configurables/{char_name}_Lorebook.json"
    default_path = "Configurables/Lorebook.json"
    lore_path = custom_path if os.path.exists(custom_path) else default_path

    try:
        with open(lore_path, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        utils.zw_logging.update_debug_log(f"⚠️ Failed to load lorebook: {e}")
        return []


# For retreival
# def lorebook_check(message):
#     global LORE_BOOK
#
#     # Lockout clearing
#     for lore in LORE_BOOK:
#         if lore['2'] > 0:
#             lore['2'] -= 1
#
#     # Search for new ones
#     for lore in LORE_BOOK:
#         if utils.cane_lib.keyword_check(message, [" " + lore['0']]) and lore['2'] == 0:
#             # Set our lockout
#             lore['2'] += 9
#
#             # Make our info
#
#             combo_lore = lore['0'] + ", " + lore['1']
#
#             return combo_lore
#
#     return "No lore!"

# Gathers ALL lore in a given scope (send in the message being sent, as well as any message pairs you want to check)
def lorebook_gather(messages, sent_message):
    lore_book = load_lorebook()
    
    # gather, gather, into reformed
    reformed_messages = [sent_message, ""]

    for message in messages:
        reformed_messages.append(message[0])
        reformed_messages.append(message[1])

    # gather all of our lore in one spot
    total_lore = total_lore_default

    # Reset all lore entry cooldown
    for lore in lore_book:
        lore['2'] = 0

    # Search every lore entry for each of the messages, and add the lore as needed
    for message in reformed_messages:
        # Search for new ones
        for lore in lore_book:
             if utils.cane_lib.keyword_check(message, [
                f" {lore['0']} ", f" {lore['0']}'", f" {lore['0']}s",
                f" {lore['0']}!", f" {lore['0']}.", f" {lore['0']},", f" {lore['0']}?"
            ]) and lore['2'] == 0:
                total_lore += f"{lore['0']}, {lore['1']}\n\n"
                lore['2'] = 7   # lore has procced, prevent dupes

    if do_log_lore and total_lore != total_lore_default:
        utils.zw_logging.update_debug_log(total_lore)


    return total_lore



# Check if keyword is in the lorebook
def rag_word_check(word):
    lore_book = load_lorebook() 
    # Lockout clearing
    for lore in lore_book:
        if str.lower(lore['0']) == word:
            return True

    return False

