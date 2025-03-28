from time import time
from asyncio import sleep
from traceback import format_exc
from math import floor
from os import path as ospath
from aiofiles.os import remove as aioremove
from pyrogram.errors import FloodWait

from bot import bot, Var
from .func_utils import editMessage, convertBytes, convertTime
from .reporter import rep

class TgUploader:
    def __init__(self, message):
        self.message = message
        self.__name = ""
        self.__qual = ""
        self.__updater = time()
        self.__start = time()  # Start time for calculating elapsed time
        if not hasattr(Var, "TOTAL_QUALS"):
            Var.TOTAL_QUALS = Var.QUALS.copy()

    async def upload(self, path, qual):
        self.__name = ospath.basename(path)
        self.__qual = qual

        if not ospath.exists(path):
            await rep.report(f"[ERROR] File missing: {path}", "error")
            return None  

        try:
            if qual.lower() == "hdrip":
                if qual in Var.QUALS:
    Var.QUALS.remove(qual)
                await self.update_progress()

            thumb_path = "thumb.jpg" if ospath.exists("thumb.jpg") else None
            await rep.report(f"Uploading {qual} file to Telegram...", "info")

            msg = await bot.send_document(
                chat_id=Var.FILE_STORE,
                document=path,
                thumb=thumb_path,
                caption=f"<i>{self.__name}</i>",
                force_document=True,
                progress=self.progress_status
            ) if Var.AS_DOC else await bot.send_video(
                chat_id=Var.FILE_STORE,
                video=path,
                thumb=thumb_path,
                caption=f"<i>{self.__name}</i>",
                progress=self.progress_status
            )

            if not msg or not hasattr(msg, "id"):
                await rep.report(f"[ERROR] Upload failed: {path}", "error")
                return None

            await rep.report(f"Uploaded: {self.__name}, Message ID: {msg.id}", "info")
            Var.QUALS.discard(qual)
            await self.update_progress()
            return msg  # Ensure we return the message object

        except FloodWait as e:
            await sleep(e.value * 1.5)
            return await self.upload(path, qual)

        except Exception:
            await rep.report(format_exc(), "error")
            return None

        finally:
            if ospath.exists(path):
                await aioremove(path)

    async def progress_status(self, current, total):
        now = time()
        elapsed_time = now - self.__start  # Time taken since upload started
        if (now - self.__updater) >= 7 or current == total:
            self.__updater = now
            percent = round(current / total * 100, 2)
            speed = current / elapsed_time if elapsed_time > 0 else 0
            eta = round((total - current) / speed) if speed > 0 else 0
            bar = floor(percent / 8) * "█" + (12 - floor(percent / 8)) * "▒"

            completed = len(Var.TOTAL_QUALS) - len(Var.QUALS)
            total_qualities = len(Var.TOTAL_QUALS)

            progress_str = f"""‣ <b>Anime Name :</b> <b><i>{self.__name}</i></b>

‣ <b>Status :</b> <i>Uploading</i>
    <code>[{bar}]</code> {percent}%
    
    ‣ <b>Size :</b> {convertBytes(current)} / {convertBytes(total)}
    ‣ <b>Speed :</b> {convertBytes(speed)}/s
    ‣ <b>Time Left :</b> {convertTime(eta) if eta > 0 else "Calculating..."}
    ‣ <b>Time Took :</b> {convertTime(elapsed_time)}

‣ <b>File(s) Encoded:</b> <code>{completed} / {total_qualities}</code>"""

            await editMessage(self.message, progress_str)

    async def update_progress(self):
        completed = len(Var.TOTAL_QUALS) - len(Var.QUALS)
        total_qualities = len(Var.TOTAL_QUALS)
        await editMessage(self.message, f"‣ <b>File(s) Encoded:</b> <code>{completed} / {total_qualities}</code>")