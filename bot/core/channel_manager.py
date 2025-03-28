import json
from bot import bot
from pyrogram import Client, filters

CHANNELS_FILE = "channels.json"

# Load existing channel mappings
try:
    with open(CHANNELS_FILE, "r") as f:
        anime_channels = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    anime_channels = {}

# Save channel mappings
def save_channels():
    with open(CHANNELS_FILE, "w") as f:
        json.dump(anime_channels, f, indent=4)

# Command: /listchannels
@bot.on_message(filters.command("listchannels"))
async def list_channels(client: Client, message):
    if not anime_channels:
        return await message.reply("No channels set yet.")

    text = "**Anime → Channel Mappings:**\n"
    for title, ch_id in anime_channels.items():
        text += f"• `{title}` → `{ch_id}`\n"

    await message.reply(text)

# Command: /removechannel <anime_title>
@bot.on_message(filters.command("removechannel"))
async def remove_channel(client: Client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/removechannel <anime_title>`")

    anime_title = " ".join(message.command[1:]).lower()

    if anime_title in anime_channels:
        del anime_channels[anime_title]
        save_channels()
        await message.reply(f"Removed channel mapping for **{anime_title}**.")
    else:
        await message.reply("No mapping found for this anime.")