from time import time, sleep
from traceback import format_exc
from math import floor
from os import path as ospath
from aiofiles.os import remove as aioremove
from pyrogram.errors import FloodWait

from bot import bot, Var
from .func_utils import editMessage, sendMessage, convertBytes, convertTime
from .reporter import rep

class TgUploader:
    def __init__(self, message):
        self.cancelled = False
        self.message = message
        self.__name = ""
        self.__qual = ""
        self.__client = bot
        self.__start = time()
        self.__updater = time()

        # ✅ Ensure TOTAL_QUALS is correctly initialized
        if not hasattr(Var, "TOTAL_QUALS"):
            Var.TOTAL_QUALS = Var.QUALS.copy()

    async def upload(self, path, qual):
        self.__name = ospath.basename(path)
        self.__qual = qual

        if not ospath.exists(path):  # ✅ Prevent retrying if file is missing
            await rep.report(f"[ERROR] File missing: {path}", "error")
            return  

        try:
            if qual.lower() == "hdrip":  # ✅ Mark HDRip as processed before upload
                if qual in Var.QUALS:
                    Var.QUALS.remove(qual)
                await self.update_progress()

            msg = None
            thumb_path = "thumb.jpg" if ospath.exists("thumb.jpg") else None

            # ✅ Uploading the file
            await rep.report(f"Uploading {qual} file to Telegram...", "info")
            if Var.AS_DOC:
                msg = await self.__client.send_document(
                    chat_id=Var.FILE_STORE,
                    document=path,
                    thumb=thumb_path,
                    caption=f"<i>{self.__name}</i>",
                    force_document=True,
                    progress=self.progress_status
                )
            else:
                msg = await self.__client.send_video(
                    chat_id=Var.FILE_STORE,
                    video=path,  
                    thumb=thumb_path,
                    caption=f"<i>{self.__name}</i>",
                    progress=self.progress_status
                )

            if not msg or not hasattr(msg, "id"):  # ✅ Fix "NoneType" error
                await rep.report(f"[ERROR] Upload failed for: {path}", "error")
                return

            # ✅ Successfully uploaded, now process links and other qualities
            rep(f"[INFO] Successfully Uploaded File: {self.__name}, Message ID: {msg.id}")
            await sleep(2)  # ✅ Delay to avoid Telegram API lag

            if qual in Var.QUALS:  # ✅ Remove from QUALS only after successful upload
                Var.QUALS.remove(qual)
            await self.update_progress()

            # ✅ Ensure link creation happens after upload
            await self.generate_post_link(msg)

        except FloodWait as e:
            await sleep(e.value * 1.5)
            return await self.upload(path, qual)

        except Exception as e:
            await rep.report(format_exc(), "error")
            raise e

        finally:
            if ospath.exists(path):  # ✅ Delete only if file exists
                await aioremove(path)

    async def generate_post_link(self, msg):
        """ ✅ Function to generate and send post links after upload """
        try:
            file_link = f"https://t.me/{Var.FILE_STORE}/{msg.id}"
            rep(f"[INFO] Generated File Link: {file_link}")

            # ✅ Send link to the group/channel
            await sendMessage(Var.POST_CHANNEL, f"✅ <b>{self.__name}</b>\n🔗 <a href='{file_link}'>Download</a>")

        except Exception as e:
            rep(f"[ERROR] Failed to create post link: {e}")

    async def progress_status(self, current, total):
        if self.cancelled:
            self.__client.stop_transmission()
            return

        now = time()
        diff = now - self.__start
        if (now - self.__updater) >= 7 or current == total:
            self.__updater = now
            percent = round(current / total * 100, 2)
            speed = current / diff if diff > 0 else 0
            eta = round((total - current) / speed) if speed > 0 else 0
            bar = floor(percent / 8) * "█" + (12 - floor(percent / 8)) * "▒"

            completed = len(Var.TOTAL_QUALS) - len(Var.QUALS)  # ✅ Ensure correct count
            total_qualities = len(Var.TOTAL_QUALS)  

            progress_str = f"""‣ <b>Anime Name :</b> <b><i>{self.__name}</i></b>

‣ <b>Status :</b> <i>Uploading</i>
    <code>[{bar}]</code> {percent}%
    
    ‣ <b>Size :</b> {convertBytes(current)} out of ~ {convertBytes(total)}
    ‣ <b>Speed :</b> {convertBytes(speed)}/s
    ‣ <b>Time Took :</b> {convertTime(diff)}
    ‣ <b>Time Left :</b> {convertTime(eta)}

‣ <b>File(s) Encoded:</b> <code>{completed} / {total_qualities}</code>"""

            await editMessage(self.message, progress_str)

    async def update_progress(self):
        """ ✅ Correct encoded file count logic """
        completed = len(Var.TOTAL_QUALS) - len(Var.QUALS)
        total_qualities = len(Var.TOTAL_QUALS)  

        progress_str = f"‣ <b>File(s) Encoded:</b> <code>{completed} / {total_qualities}</code>"
        await editMessage(self.message, progress_str)