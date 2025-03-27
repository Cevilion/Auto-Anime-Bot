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
<b>㊂  <i>{title}</i></b>
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
    "Action": "👊",
    "Adventure": choice(['🪂', '🧗‍♀']),
    "Comedy": "🤣",
    "Drama": "🎭",
    "Ecchi": choice(['💋', '🥵']),
    "Fantasy": choice(['🧞', '🧞‍♂', '🧞‍♀', '🌗']),
    "Hentai": "🔞",
    "Horror": "☠",
    "Mahou Shoujo": "☯",
    "Mecha": "🤖",
    "Music": "🎸",
    "Mystery": "🔮",
    "Psychological": "♟",
    "Romance": "💞",
    "Sci-Fi": "🛸",
    "Slice of Life": choice(['☘', '🍁']),
    "Sports": "⚽",
    "Supernatural": "🫧",
    "Thriller": choice(['🥶', '🔪', '🤯'])
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
    genres
    episodes
    startDate {
      year
      month
      day
    }
    endDate {
      year
      month
      day
    }
    averageScore
    status
    description
    siteUrl
  }
}
"""

class AniLister:
    def __init__(self, anime_name: str, year: int) -> None:
        self.__api = "https://graphql.anilist.co"
        self.__ani_name = anime_name
        self.__ani_year = year
        self.__vars = {'search': self.__ani_name, 'seasonYear': self.__ani_year}

    def __update_vars(self, year=True) -> None:
        if year:
            self.__ani_year -= 1
            self.__vars['seasonYear'] = self.__ani_year
        else:
            self.__vars = {'search': self.__ani_name}

    async def post_data(self):
        async with ClientSession() as sess:
            async with sess.post(self.__api, json={'query': ANIME_GRAPHQL_QUERY, 'variables': self.__vars}) as resp:
                return (resp.status, await resp.json(), resp.headers)

    async def get_anidata(self):
        res_code, resp_json, res_heads = await self.post_data()
        
        while res_code == 404 and self.__ani_year > 2020:
            self.__update_vars()
            await rep.report(f"AniList Query Name: {self.__ani_name}, Retrying with {self.__ani_year}", "warning", log=False)
            res_code, resp_json, res_heads = await self.post_data()

        if res_code == 404:
            self.__update_vars(year=False)
            res_code, resp_json, res_heads = await self.post_data()

        if res_code == 200:
            return resp_json.get('data', {}).get('Media', {})

        elif res_code == 429:
            f_timer = int(res_heads.get('Retry-After', 5))
            await rep.report(f"AniList API FloodWait: {res_code}, Sleeping for {f_timer} seconds!", "error")
            await asleep(f_timer)
            return await self.get_anidata()

        else:
            await rep.report(f"AniList API Error: {res_code}", "error", log=False)
            return {}

class TextEditor:
    def __init__(self, name):
        self.__name = name
        self.adata = {}
        self.pdata = parse(name)

    async def load_anilist(self):
        cache_names = []
        for option in [(False, False), (False, True), (True, False), (True, True)]:
            ani_name = await self.parse_name(*option)
            if ani_name in cache_names:
                continue
            cache_names.append(ani_name)
            self.adata = await AniLister(ani_name, datetime.now().year).get_anidata()
            if self.adata:
                break

    @handle_logs
    async def parse_name(self, no_s=False, no_y=False):
        anime_name = self.pdata.get("anime_title")
        anime_season = self.pdata.get("anime_season")
        anime_year = self.pdata.get("anime_year")
        pname = anime_name or ""
        
        if not no_s and anime_season:
            pname += f" {anime_season}"
        if not no_y and anime_year:
            pname += f" {anime_year}"
            
        return pname.strip()

    @handle_logs
    async def get_poster(self):
        anime_id = self.adata.get('id')
        return f"https://img.anili.st/media/{anime_id}" if anime_id else "https://telegra.ph/file/112ec08e59e73b6189a20.jpg"

    @handle_logs
    async def get_caption(self):
        sd = self.adata.get('startDate', {})
        ed = self.adata.get('endDate', {})

        startdate = f"{month_name[sd.get('month', 1)]} {sd.get('day', '')}, {sd.get('year', '')}".strip(", ")
        enddate = f"{month_name[ed.get('month', 1)]} {ed.get('day', '')}, {ed.get('year', '')}".strip(", ")

        titles = self.adata.get("title", {})
        return CAPTION_FORMAT.format(
            title=titles.get('english') or titles.get('romaji') or titles.get('native'),
            genres=", ".join(f"{GENRES_EMOJI.get(x, '❓')} #{x.replace(' ', '_').replace('-', '_')}" for x in self.adata.get('genres', [])),
            ep_no=self.pdata.get("episode_number", "N/A"),
            cred=Var.BRAND_UNAME
        )