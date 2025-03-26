from asyncio import sleep as asleep, gather
from pyrogram.filters import command, private, user
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, MessageNotModified

from bot import bot, bot_loop, Var, ani_cache
from bot.core.database import db
from bot.core.func_utils import (
    decode, is_fsubbed, get_fsubs, editMessage, sendMessage, 
    new_task, convertTime, getfeed
)
from bot.core.auto_animes import get_animes
from bot.core.reporter import rep
from bot.core.channel_manager import anime_channels  # ✅ Import fixed

OWNER_ID = Var.OWNER_ID  # ✅ Ensure OWNER_ID is properly set

# ✅ Unified `/setchannel` Command Handler
@bot.on_message(filters.command("setchannel") & private & user(OWNER_ID))
async def set_channel(client, message):
    if len(message.command) < 3:
        return await message.reply("Usage: `/setchannel <anime_title> <channel_id>`")

    anime_title = " ".join(message.command[1:-1])  # Handle multi-word anime titles
    channel_id = message.command[-1]

    # Validate if the channel_id starts with -100 for private channels
    if not channel_id.startswith("-100"):
        return await message.reply("Invalid channel ID format. It should start with `-100` for private channels.")

    # Ensure that the channel ID is valid
    try:
        await client.get_chat(channel_id)  # Validate the channel by checking access
    except Exception as e:
        return await message.reply(f"Failed to access the channel. Error: {e}")

    anime_channels[anime_title.lower()] = channel_id  # Save the channel mapping
    save_channels()  # Save to the channels.json file
    await message.reply(f"✅ **Set {anime_title} to post in channel:** `{channel_id}`")

@bot.on_message(command('start') & private)
@new_task
async def start_msg(client, message):
    uid = message.from_user.id
    from_user = message.from_user
    txtargs = message.text.split()
    temp = await sendMessage(message, "<i>loading...</i>")

    if not await is_fsubbed(uid):
        txt, btns = await get_fsubs(uid, txtargs)
        return await editMessage(temp, txt, InlineKeyboardMarkup(btns))

    if len(txtargs) <= 1:
        await temp.delete()
        btns = []
        for elem in Var.START_BUTTONS.split():
            try:
                bt, link = elem.split('|', maxsplit=1)
            except:
                continue
            if len(btns) and len(btns[-1]) == 1:
                btns[-1].insert(1, InlineKeyboardButton(bt, url=link))
            else:
                btns.append([InlineKeyboardButton(bt, url=link)])
        
        smsg = Var.START_MSG.format(
            first_name=from_user.first_name,
            last_name=from_user.first_name,
            mention=from_user.mention, 
            user_id=from_user.id
        )
        
        if Var.START_PHOTO:
            await message.reply_photo(
                photo=Var.START_PHOTO, 
                caption=smsg,
                reply_markup=InlineKeyboardMarkup(btns) if btns else None
            )
        else:
            await sendMessage(message, smsg, InlineKeyboardMarkup(btns) if btns else None)
        return

    try:
        arg = (await decode(txtargs[1])).split('-')
    except Exception as e:
        await rep.report(f"User: {uid} | Error: {str(e)}", "error")
        return await editMessage(temp, "<b>Input Link Code Decode Failed!</b>")
    
    if len(arg) == 2 and arg[0] == 'get':
        try:
            fid = int(int(arg[1]) / abs(int(Var.FILE_STORE)))
        except Exception as e:
            await rep.report(f"User: {uid} | Error: {str(e)}", "error")
            return await editMessage(temp, "<b>Input Link Code is Invalid!</b>")
        
        try:
            msg = await client.get_messages(Var.FILE_STORE, message_ids=fid)
            if msg.empty:
                return await editMessage(temp, "<b>File Not Found!</b>")
            nmsg = await msg.copy(message.chat.id, reply_markup=None)
            await temp.delete()
            if Var.AUTO_DEL:
                async def auto_del(msg, timer):
                    await asleep(timer)
                    await msg.delete()
                await sendMessage(message, f"<i>File will be Auto Deleted in {convertTime(Var.DEL_TIMER)}, Forward to Saved Messages Now...</i>")
                bot_loop.create_task(auto_del(nmsg, Var.DEL_TIMER))
        except Exception as e:
            await rep.report(f"User: {uid} | Error: {str(e)}", "error")
            await editMessage(temp, "<b>File Not Found!</b>")
    else:
        await editMessage(temp, "<b>Input Link is Invalid for Usage!</b>")

@bot.on_message(command('pause') & private & user(Var.ADMINS))
async def pause_fetch(client, message):
    ani_cache['fetch_animes'] = False
    await sendMessage(message, "`Successfully Paused Fetching Animes...`")

@bot.on_message(command('resume') & private & user(Var.ADMINS))
async def resume_fetch(client, message):  # ✅ Fixed duplicate function name
    ani_cache['fetch_animes'] = True
    await sendMessage(message, "`Successfully Resumed Fetching Animes...`")

@bot.on_message(command('log') & private & user(Var.ADMINS))
@new_task
async def _log(client, message):
    await message.reply_document("log.txt", quote=True)

@bot.on_message(command('addlink') & private & user(Var.ADMINS))
@new_task
async def add_link(client, message):  # ✅ Renamed function for clarity
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Link Found to Add</b>")

    Var.RSS_ITEMS.append(args[1])
    links = ', '.join(Var.RSS_ITEMS)
    await sendMessage(message, f"`Global Link Added Successfully!`\n\n**All Links:** {links}")

@bot.on_message(command('addtask') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Task Found to Add</b>")
    
    index = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
    taskInfo = await getfeed(args[1], index)

    if not taskInfo:
        return await sendMessage(message, "<b>No Task Found to Add for the Provided Link</b>")
    
    bot_loop.create_task(get_animes(taskInfo.title, taskInfo.link, True))
    await sendMessage(message, f"<i><b>Task Added Successfully!</b></i>\n\n• **Task Name:** {taskInfo.title}\n• **Task Link:** {args[1]}")