import json
import logging
from bot import bot
from pyroram import Client, filters

CHANNELS_FILE = "channels.json"

logging.basicConfig(level=logging.INFO)  # Enable logging

# Load existing channel mappings
try:
    with open(CHANNELS_FILE, "r") as f:
        anime_channels = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    anime_channels = {}

# Save channel mappings
def save_channels():
    try:
        with open(CHANNELS_FILE, "w") as f:
            json.dump(anime_channels, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channels: {e}")

# Command: /setchannel <anime_title> <channel_id>
@bot.on_message(filters.command("setchannel"))
async def set_channel(client: Client, message):
    if len(message.command) < 3:
        return await message.reply("Usage: `/setchannel <anime_title> <channel_id>`")

    anime_title = " ".join(message.command[1:-1])
    channel_id = message.command[-1]

    logging.info(f"Setting channel for anime: {anime_title}, Channel ID: {channel_id}")

    if not channel_id.startswith("-100"):
        return await message.reply("Invalid channel ID. It should start with `-100`.")

    try:
        # Validate the channel ID by checking if bot can access it
        await client.get_chat(channel_id)
    except Exception as e:
        logging.error(f"Failed to validate channel {channel_id}: {e}")
        return await message.reply(f"Could not access channel with ID `{channel_id}`. Please check the ID or permissions.")

    anime_channels[anime_title.lower()] = channel_id
    save_channels()
    await message.reply(f"Channel set for **{anime_title}**: `{channel_id}`")

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