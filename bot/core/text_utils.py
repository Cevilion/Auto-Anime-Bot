from calendar import month_name
from datetime import datetime
from random import choice
from asyncio import sleep as asleep
from aiohttp import ClientSession
from anitopy import parse

from bot import Var, bot
from .ffencoder import ffargs
from .func_utils import handle_logs
from .reporter import rep

CAPTION_FORMAT = """
<b>㊂ <i>{title}</i></b>
<b>╭┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</b>
<b>⊙</b> <i>Genres:</i> <i>{genres}</i>
<b>⊙</b> <i>Status:</i> <i>RELEASING</i> 
<b>⊙</b> <i>Source:</i> <i>Subsplease</i>
<b>⊙</b> <i>Episode:</i> <i>{ep_no}</i>
<b>⊙</b> <i>Audio: Japanese</i>
<b>⊙</b> <i>Subtitle: English</i>
<b>╰┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</b>
╭┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅
⌬  <b><i>Powered By</i></b> ~ </i></b><b><i>{cred}</i></b>
╰┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅
"""

GENRES_EMOJI = {
    "Action": "👊", "Adventure": choice(['🪂', '🧗‍♀']), "Comedy": "🤣", "Drama": " 🎭",
    "Ecchi": choice(['💋', '🥵']), "Fantasy": choice(['🧞', '🧞‍♂', '🧞‍♀','🌗']), "Hentai": "🔞",
    "Horror": "☠", "Mahou Shoujo": "☯", "Mecha": "🤖", "Music": "🎸", "Mystery": "🔮",
    "Psychological": "♟", "Romance": "💞", "Sci-Fi": "🛸", "Slice of Life": choice(['☘','🍁']),
    "Sports": "⚽️", "Supernatural": "🫧", "Thriller": choice(['🥶', '🔪','🤯'])
}

ANIME_GRAPHQL_QUERY = """
query ($id: Int, $search: String, $seasonYear: Int) {
  Media(id: $id, type: ANIME, format_not_in: [MOVIE, MUSIC, MANGA, NOVEL, ONE_SHOT], search: $search, seasonYear: $seasonYear) {
    id
    title {
      romaji
      english
      native
    }
    startDate { year month day }
    endDate { year month day }
    format
    status
    genres
    episodes
    description(asHtml: false)
    coverImage { large }
    siteUrl
  }
}
"""

class AniLister:
    def __init__(self, anime_name: str, year: int) -> None:
        self.__api = "https://graphql.anilist.co"
        self.__ani_name = anime_name
        self.__ani_year = year
        self.__vars = {'search' : self.__ani_name, 'seasonYear': self.__ani_year}

    async def post_data(self):
        async with ClientSession() as sess:
            async with sess.post(self.__api, json={'query': ANIME_GRAPHQL_QUERY, 'variables': self.__vars}) as resp:
                return resp.status, await resp.json(), resp.headers

    async def get_anidata(self):
        res_code, resp_json, res_heads = await self.post_data()
        while res_code == 404 and self.__ani_year > 2020:
            self.__ani_year -= 1
            self.__vars['seasonYear'] = self.__ani_year
            res_code, resp_json, res_heads = await self.post_data()
        return resp_json.get('data', {}).get('Media', {}) if res_code == 200 else {}

class TextEditor:
    def __init__(self, name):
        self.__name = name
        self.adata = {}
        self.pdata = parse(name)

    async def load_anilist(self):
        ani_name = await self.parse_name()
        self.adata = await AniLister(ani_name, datetime.now().year).get_anidata()

    async def parse_name(self):
        anime_name = self.pdata.get("anime_title", "")
        anime_season = self.pdata.get("anime_season", "")
        anime_year = self.pdata.get("anime_year", "")
        return f"{anime_name} {anime_season} {anime_year}".strip()

    async def get_poster(self):
        return f"https://img.anili.st/media/{self.adata.get('id')}" if self.adata.get('id') else "https://telegra.ph/file/112ec08e59e73b6189a20.jpg"

    async def get_upname(self, qual=""):
        anime_name = self.pdata.get("anime_title", "")
        episode_number = self.pdata.get("episode_number", "")

        # Determine codec unless it's HDRip
        codec = "" if qual == "Hdrip" else ('HEVC' if 'libx265' in ffargs.get(qual, {}) else 'AV1' if 'libaom-av1' in ffargs.get(qual, {}) else '')

        lang = 'Multi-Audio' if 'multi-audio' in self.__name.lower() else 'Sub'
        anime_season = str(self.pdata.get('anime_season', '01'))

        # Construct filename
        title = self.adata.get('title', {}).get('english') or self.adata.get('title', {}).get('romaji') or self.adata.get('title', {}).get('native')
        quality_label = f"[{qual}p]" if qual and qual.lower() != "hdrip" else "[Hdrip]"
        codec_label = f"[{codec.upper()}]" if codec else ""

        return f"[S{anime_season}-E{episode_number}] {title} {quality_label} {codec_label} [{lang}] {Var.BRAND_UNAME}.mkv"

    async def get_caption(self):
        titles = self.adata.get("title", {})
        sd, ed = self.adata.get('startDate', {}), self.adata.get('endDate', {})

        # **Fixed month_name.get() issue**
        start_date = f"{month_name[sd.get('month', 1)]} {sd.get('day', '')}, {sd.get('year', '')}".strip()
        end_date = f"{month_name[ed.get('month', 1)]} {ed.get('day', '')}, {ed.get('year', '')}".strip()

        return CAPTION_FORMAT.format(
            title=titles.get('english') or titles.get('romaji') or titles.get('native'),
            genres=", ".join(f"{GENRES_EMOJI.get(x, '')} #{x.replace(' ', '_').replace('-', '_')}" for x in self.adata.get('genres', [])),
            status=self.adata.get("status", "N/A"),
            ep_no=self.pdata.get("episode_number", "N/A"),
            cred=Var.BRAND_UNAME,
        )