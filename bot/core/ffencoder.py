from re import findall
from math import floor
from time import time
from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, rename as aiorename
from asyncio import sleep as asleep, gather, create_subprocess_shell, create_task
from asyncio.subprocess import PIPE

from bot import Var, ffpids_cache, LOGS
from .func_utils import mediainfo, convertBytes, convertTime, sendMessage, editMessage
from .reporter import rep
from .tguploader import TgUploader  # Corrected import

ffargs = {
    '1080': Var.FFCODE_1080,
    '720': Var.FFCODE_720,
    '480': Var.FFCODE_480,
    'Hdri': Var.FFCODE_Hdri,  # HDRip processing
}

class FFEncoder:
    def __init__(self, message, path, name, qual):
        self.__proc = None
        self.is_cancelled = False
        self.message = message
        self.__name = name
        self.__qual = qual
        self.dl_path = path
        self.__total_time = None
        self.out_path = ospath.join("encode", f"{self.__name}_{qual}.mkv")  # Unique filenames
        self.__prog_file = 'prog.txt'
        self.__start_time = time()

    async def start_encode(self):
        """Starts the FFmpeg encoding process."""
        if ospath.exists(self.__prog_file):
            await aioremove(self.__prog_file)

        if self.__qual != 'Hdri':
            async with aiopen(self.__prog_file, 'w+'):
                LOGS.info("Progress Temp Generated!")

        dl_npath, out_npath = ospath.join("encode", "ffanimeadvin.mkv"), ospath.join("encode", "ffanimeadvout.mkv")
        await aiorename(self.dl_path, dl_npath)

        progress_file = self.__prog_file if self.__qual != 'Hdri' else "null"
        ffcode = ffargs[self.__qual].format(dl_npath, progress_file, out_npath)

        LOGS.info(f'FFCode: {ffcode}')
        self.__proc = await create_subprocess_shell(ffcode, stdout=PIPE, stderr=PIPE)
        proc_pid = self.__proc.pid
        ffpids_cache.append(proc_pid)

        if self.__qual == 'Hdri':
            await self.__proc.wait()
            return_code = 0
        else:
            _, return_code = await gather(create_task(self.progress()), self.__proc.wait())

        ffpids_cache.remove(proc_pid)
        await aiorename(dl_npath, self.dl_path)

        if self.is_cancelled:
            return

        if return_code == 0 and ospath.exists(out_npath):
            await aiorename(out_npath, self.out_path)
            await self.upload_file()  # Ensure upload finishes before next encode
            return self.out_path
        else:
            error_msg = (await self.__proc.stderr.read()).decode().strip()
            await rep.report(error_msg, "error")

    async def upload_file(self):
        """Uploads the encoded file before proceeding to the next quality."""
        LOGS.info(f"Uploading {self.__qual}p...")
        await sendMessage(self.message.chat.id, f"Uploading {self.__qual}p...")

        uploader = TgUploader(self.message)  # Corrected instantiation
        await uploader.upload(self.out_path, self.__qual)  # Fixed method call

        if not self.is_cancelled:
            await self.next_encode()

    async def next_encode(self):
        """Ensures encoding follows HDRip → 480p → 720p → 1080p."""
        next_qual = {
            "Hdri": "480",
            "480": "720",
            "720": "1080"
        }.get(self.__qual)

        if not next_qual:
            return  # No next step

        LOGS.info(f"Starting Next Encode: {next_qual}p")
        await sendMessage(self.message.chat.id, f"Starting {next_qual}p Encoding...")

        encoder = FFEncoder(self.message, self.out_path, self.__name, next_qual)
        await encoder.start_encode()

    async def cancel_encode(self):
        """Cancels encoding process."""
        self.is_cancelled = True
        if self.__proc:
            try:
                self.__proc.kill()
            except:
                pass

    async def progress(self):
        """Tracks FFmpeg progress in real-time."""
        self.__total_time = await mediainfo(self.dl_path, get_duration=True)
        if isinstance(self.__total_time, str):
            self.__total_time = 1.0

        while not self.is_cancelled and self.__proc.returncode is None:
            if ospath.exists(self.__prog_file):
                async with aiopen(self.__prog_file, 'r') as p:
                    text = await p.read()

                if text:
                    t = findall(r"out_time_ms=(\d+)", text)
                    s = findall(r"total_size=(\d+)", text)

                    time_done = floor(int(t[-1]) / 1000000) if t else 1
                    ensize = int(s[-1]) if s else 0

                    elapsed = time() - self.__start_time
                    speed = ensize / max(elapsed, 1)
                    percent = round((time_done / self.__total_time) * 100, 2)
                    tsize = ensize / (max(percent, 0.01) / 100)
                    eta = (tsize - ensize) / max(speed, 0.01)

                    bar = floor(percent / 8) * "█" + (12 - floor(percent / 8)) * "▒"

                    progress_str = f"""<blockquote>‣ <b>Anime Name :</b> <b><i>{self.__name}</i></b></blockquote>
<blockquote>‣ <b>Status :</b> <i>Encoding</i>
    <code>[{bar}]</code> {percent}%</blockquote> 
<blockquote>   ‣ <b>Size :</b> {convertBytes(ensize)} out of ~ {convertBytes(tsize)}
    ‣ <b>Speed :</b> {convertBytes(speed)}/s
    ‣ <b>Time Taken :</b> {convertTime(elapsed)}
    ‣ <b>Time Left :</b> {convertTime(eta)}</blockquote>
<blockquote>‣ <b>File(s) Encoded:</b> <code>{Var.QUALS.index(self.__qual)} / {len(Var.QUALS)}</code></blockquote>"""

                    await editMessage(self.message, progress_str)

                    if "progress=end" in text:
                        break
            await asleep(8)