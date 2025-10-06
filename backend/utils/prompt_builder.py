# =========================================================
# Module: prompt_builder.py
# Purpose: Build message history before sending it to the model.
# Used in: api_service, modules.ollama
# Highlights:
# - Adds system prompt, memory, and emotions to the beginning of the history
# - Removes unnecessary fields from messages (e.g., timestamp)
# - Supports toggling inclusion of the system prompt
# =======================================================

def compose_prompt(system_prompt, memory=None, emotion=None, history=[], user_input=""):
    messages = [{"role": "system", "content": system_prompt}]
    if memory:
        messages.append({"role": "system", "content": f"[Память] {memory}"})
    if emotion:
        messages.append({"role": "system", "content": f"[Эмоции] {emotion}"})
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return messages
