import os
from enum import Enum

class StructureEnum(str, Enum):
    Core = '[CORE]'
    ConfigService = '[CONFIG SERVICE]'
    Logger = '[LOGGER]'
    VoiceService = '[VOICE SERVICE]'
    # Extend as needed

def get_structure_label(name: str) -> str:
    """
    Convert a name (e.g., 'voice_service') into a StructureEnum tag.
    Returns '[CORE]' by default when no match is found.
    """
    camel_case = ''.join(part.capitalize() for part in name.split('_'))

    try:
        return StructureEnum[camel_case].value
    except KeyError:
        return StructureEnum['Core'].value

def get_label_from_file(file_path: str) -> str:
    base = os.path.splitext(os.path.basename(file_path))[0]
    return get_structure_label(base)
