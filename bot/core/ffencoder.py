from re import findall
from math import floor
from time import time
from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, rename as aiorename
from shlex import split as ssplit
from asyncio import sleep as asleep, gather, create_subprocess_shell, create_task
from asyncio.subprocess import PIPE

from bot import Var, bot_loop, ffpids_cache, LOGS
from .func_utils import mediainfo, convertBytes, convertTime, sendMessage, editMessage
from .reporter import rep

ffargs = {
    '1080': Var.FFCODE_1080,
    '720': Var.FFCODE_720,
    '480': Var.FFCODE_480,
    'Hdri': Var.FFCODE_Hdri,
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
        self.out_path = ospath.join("encode", name)
        self.__prog_file = 'prog.txt'
        self.__start_time = time()

    async def start_encode(self):
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
            await self.next_encode()
            return self.out_path
        else:
            error_msg = (await self.__proc.stderr.read()).decode().strip()
            await rep.report(error_msg, "error")

    async def next_encode(self):
        """Ensure encoding follows HDRip → 480p → 720p → 1080p"""
        if self.__qual == "Hdri":
            next_qual = "480"
        elif self.__qual == "480":
            next_qual = "720"
        elif self.__qual == "720":
            next_qual = "1080"
        else:
            return

        LOGS.info(f"Starting Next Encode: {next_qual}p")
        await sendMessage(self.message.chat.id, f"Starting {next_qual}p Encoding...")

        encoder = FFEncoder(self.message, self.out_path, f"encoded_{next_qual}.mkv", next_qual)
        await encoder.start_encode()

    async def cancel_encode(self):
        self.is_cancelled = True
        if self.__proc is not None:
            try:
                self.__proc.kill()
            except:
                pass

    async def progress(self):
        """Track FFmpeg progress."""
        self.progress = {}
        while not self.is_cancelled and self.__proc.returncode is None:
            if ospath.exists(self.__prog_file):
                async with aiopen(self.__prog_file, 'r') as f:
                    text = await f.read()
                    times = findall(r'time=(\d+:\d+:\d+\.\d+)', text)
                    if times:
                        try:
                            self.__total_time = convertTime(times[-1])
                            elapsed = time() - self.__start_time
                            percent = min(100, floor((elapsed / self.__total_time) * 100))
                            await editMessage(self.message, f"Encoding... {percent}%")
                        except ValueError as e:
                            LOGS.error(f"Error: {e}")
                            await rep.report(f"FFmpeg progress error: {e}", "error")
                            break
            await asleep(10)