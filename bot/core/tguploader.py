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

    async def upload(self, path, qual):
        self.__name = ospath.basename(path)
        self.__qual = qual

        if not ospath.exists(path):  # ✅ Fix: Prevent retrying missing files
            await rep.report(f"File missing: {path}", "error")
            return  

        try:
            if qual.lower() == "hdrip":  # ✅ Fix: Mark HDRip as processed immediately
                if qual in Var.QUALS:
                    Var.QUALS.remove(qual)
                self.update_progress()  # ✅ Update progress immediately

            msg = None
            if Var.AS_DOC:
                msg = await self.__client.send_document(
                    chat_id=Var.FILE_STORE,
                    document=path,
                    thumb="thumb.jpg" if ospath.exists("thumb.jpg") else None,
                    caption=f"<i>{self.__name}</i>",
                    force_document=True,
                    progress=self.progress_status
                )
            else:
                msg = await self.__client.send_video(
                    chat_id=Var.FILE_STORE,
                    video=path,  # ✅ Fix: Correct 'video' key instead of 'document'
                    thumb="thumb.jpg" if ospath.exists("thumb.jpg") else None,
                    caption=f"<i>{self.__name}</i>",
                    progress=self.progress_status
                )

            if msg is None or not hasattr(msg, "id"):  # ✅ Fix: Handle NoneType error
                await rep.report(f"Upload failed for: {path}", "error")
                return

            self.update_progress()  # ✅ Fix: Ensure progress updates after upload

        except FloodWait as e:
            sleep(e.value * 1.5)
            return await self.upload(path, qual)

        except Exception as e:
            await rep.report(format_exc(), "error")
            raise e

        finally:
            if ospath.exists(path):  # ✅ Fix: Delete file only if it still exists
                await aioremove(path)

    async def progress_status(self, current, total):
        if self.cancelled:
            self.__client.stop_transmission()
        now = time()
        diff = now - self.__start
        if (now - self.__updater) >= 7 or current == total:
            self.__updater = now
            percent = round(current / total * 100, 2)
            speed = current / diff
            eta = round((total - current) / speed)
            bar = floor(percent / 8) * "█" + (12 - floor(percent / 8)) * "▒"

            # ✅ Fix: Ensure correct progress count
            completed = len(Var.TOTAL_QUALS) - len(Var.QUALS)
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

    def update_progress(self):
        """ ✅ Fix: Correct encoded file count logic """
        completed = len(Var.TOTAL_QUALS) - len(Var.QUALS)
        total_qualities = len(Var.TOTAL_QUALS)  

        progress_str = f"‣ <b>File(s) Encoded:</b> <code>{completed} / {total_qualities}</code>"
        editMessage(self.message, progress_str)