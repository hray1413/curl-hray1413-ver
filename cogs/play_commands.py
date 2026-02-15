"""
cogs/play_commands.py

/娛樂 群組（中文命名）：
- /娛樂 讓機器人重複你說話   -> 复述文字（以 Embed 输出，避免触发 mention）
- /娛樂 說你好               -> 向指定用户或自己打招呼
- /娛樂 隨機圖片             -> 从 data/picture 随机选择并发送一张图片
- /娛樂 隨機文字             -> 从 data/random-text.json 随机挑选并发送一条文本
- /娛樂 隨機推薦音樂         -> 从网络 API 随机推荐音乐（iTunes、Last.fm）

说明：
- 随机文字支持两种 JSON 格式：list 或 dict（按分类）。
- 随机音乐现在从网络 API 获取，支持 iTunes 和 Last.fm
- 若文件不存在或格式错误，会返回友好提示并写日志。
"""
from __future__ import annotations

import random
import json
import io
import asyncio
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

try:
    from utils.logger import log, log_exception
except Exception:
    def log(*args, **kwargs):
        print(*args, **kwargs)
    def log_exception(*args, **kwargs):
        print(*args, **kwargs)


DATA_PICTURE_DIR = Path("data") / "picture"
DATA_RANDOM_TEXT_FILE = Path("data") / "random-text.json"
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _gather_image_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXT]
    return files


def _load_random_texts(path: Path) -> Optional[Union[List[str], Dict[str, List[str]]]]:
    """
    Load random-text.json.
    Accepts:
      - List[str]
      - Dict[str, List[str]]
    Returns parsed data or None on error.
    """
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x) for x in data if isinstance(x, (str, int, float))]
        if isinstance(data, dict):
            out: Dict[str, List[str]] = {}
            for k, v in data.items():
                if isinstance(v, list):
                    out[k] = [str(x) for x in v if isinstance(x, (str, int, float))]
            return out
        return None
    except Exception as e:
        log_exception("ERROR", "PLAY", f"读取 {path} 失败", exc=e)
        return None


class PlayCommands(commands.Cog):
    """娱乐/小游戏命令组（中文 /娛樂）"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            DATA_PICTURE_DIR.mkdir(parents=True, exist_ok=True)
            DATA_RANDOM_TEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_exception("ERROR", "PLAY", "创建 data 目录失败", exc=e)

    # 使用中文群组名称 "娛樂"
    娛樂 = app_commands.Group(name="娛樂", description="娛樂/小游戏命令（中文）")

    # --- 讓機器人重複你說話 (echo) ---
    @娛樂.command(name="讓機器人重複你說話", description="让机器人复述你输入的话（以 Embed 输出，禁止 mention）")
    @app_commands.describe(text="要复述的文字", ephemeral="是否为私密消息，仅自己可见")
    async def echo_cn(self, interaction: discord.Interaction, text: str, ephemeral: Optional[bool] = False):
        """
        /娛樂 讓機器人重複你說話 <text> [ephemeral]
        使用 Embed 复述，并禁止任何 mentions（避免 @everyone 或 @user 被触发）。
        """
        try:
            embed = discord.Embed(title="🗣️ 复述", description=text, color=discord.Color.gold(), timestamp=datetime.utcnow())
            allowed = discord.AllowedMentions.none()
            await interaction.response.send_message(embed=embed, ephemeral=bool(ephemeral), allowed_mentions=allowed)
            log("INFO", "PLAY", f"/娛樂 讓機器人重複你說話 by {interaction.user} ephemeral={ephemeral}")
        except Exception as e:
            log_exception("ERROR", "PLAY", "echo 失败", exc=e)
            try:
                await interaction.response.send_message("复述失败，详情请查看日志。", ephemeral=True)
            except Exception:
                pass

    # --- 說你好 (say hello) ---
    @娛樂.command(name="說你好", description="向指定用户或自己打招呼")
    @app_commands.describe(user="要打招呼的用户（可选，默认向自己打招呼）")
    async def say_hello_cn(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """
        /娛樂 說你好 [user]
        向指定用户或自己打招呼。
        """
        try:
            target = user if user else interaction.user
            greetings = [
                f"你好, {target.mention}! 👋",
                f"嗨, {target.mention}! 😊",
                f"哈囉, {target.mention}! 🎉",
                f"歡迎, {target.mention}! ✨",
                f"很高興見到你, {target.mention}! 🌟"
            ]
            greeting = random.choice(greetings)
            embed = discord.Embed(
                title="👋 打招呼",
                description=greeting,
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            log("INFO", "PLAY", f"/娛樂 說你好 by {interaction.user} -> target={target}")
        except Exception as e:
            log_exception("ERROR", "PLAY", "say-hello 失败", exc=e)
            try:
                await interaction.response.send_message("打招呼失败，详情请查看日志。", ephemeral=True)
            except Exception:
                pass

    # --- 隨機圖片 (random-picture) ---
    @娛樂.command(name="隨機圖片", description="从 data/picture 随机选择并发送一张图片（可指定分类子目录）")
    @app_commands.describe(category="（可选）图片分类子目录名，如 'memes' 或 'cats'")
    async def random_picture_cn(self, interaction: discord.Interaction, category: Optional[str] = None):
        """
        /娛樂 隨機圖片 [category]
        从 data/picture 或其子目录随机挑选一张图片并发送。
        """
        await interaction.response.defer()
        try:
            directory = DATA_PICTURE_DIR
            if category:
                cat = category.strip().replace("..", "").lstrip("/\\")
                directory = DATA_PICTURE_DIR / cat

            images = _gather_image_files(directory)
            if not images:
                if category:
                    await interaction.followup.send(f"分类 `{category}` 下没有可用图片或目录不存在。请确认 data/picture/{category} 中有图片。", ephemeral=True)
                else:
                    await interaction.followup.send("目录 data/picture 中没有可用图片。请上传图片到该目录后重试。", ephemeral=True)
                return

            chosen: Path = random.choice(images)
            filename = chosen.name
            try:
                with chosen.open("rb") as f:
                    file = discord.File(fp=f, filename=filename)
                    embed = discord.Embed(
                        title="🖼️ 隨機圖片",
                        description=f"隨機挑選：`{filename}`",
                        color=discord.Color.blurple(),
                        timestamp=datetime.utcnow()
                    )
                    embed.set_image(url=f"attachment://{filename}")
                    await interaction.followup.send(embed=embed, file=file)
                    log("INFO", "PLAY", f"/娛樂 隨機圖片 by {interaction.user} -> {filename}")
            except Exception as e:
                log_exception("ERROR", "PLAY", "发送图片失败", exc=e)
                await interaction.followup.send("发送图片时发生错误（读取文件或上传失败）。", ephemeral=True)
        except Exception as e:
            log_exception("ERROR", "PLAY", "random-picture 处理失败", exc=e)
            try:
                await interaction.followup.send("处理请求时发生错误，详情请查看日志。", ephemeral=True)
            except Exception:
                pass

    # --- 隨機文字 (random-text) ---
    @娛樂.command(name="隨機文字", description="从 data/random-text.json 随机选择并发送一条文本")
    @app_commands.describe(category="（可选）分类名（如果 JSON 是对象）")
    async def random_text_cn(self, interaction: discord.Interaction, category: Optional[str] = None):
        """
        /娛樂 隨機文字 [category]
        从 data/random-text.json 随机挑选一条并发送（支持 list 或 dict）。
        """
        await interaction.response.defer()
        try:
            data = _load_random_texts(DATA_RANDOM_TEXT_FILE)
            if data is None:
                await interaction.followup.send("data/random-text.json 不存在或格式不正确。请检查文件（应为 JSON 列表或对象）。", ephemeral=True)
                return

            chosen_text: Optional[str] = None

            if category and isinstance(data, dict):
                cat = category.strip()
                lst = data.get(cat)
                if not lst:
                    await interaction.followup.send(f"分类 `{cat}` 不存在或为空。可用分类：{', '.join(sorted(data.keys())) if isinstance(data, dict) else '无'}", ephemeral=True)
                    return
                chosen_text = random.choice(lst)
            else:
                if isinstance(data, dict):
                    all_items = []
                    for lst in data.values():
                        all_items.extend(lst)
                    if not all_items:
                        await interaction.followup.send("随机文本文件中没有可用条目。", ephemeral=True)
                        return
                    chosen_text = random.choice(all_items)
                elif isinstance(data, list):
                    if not data:
                        await interaction.followup.send("随机文本文件中没有可用条目。", ephemeral=True)
                        return
                    chosen_text = random.choice(data)

            if chosen_text is None:
                await interaction.followup.send("未能挑选到文本（未知错误）。", ephemeral=True)
                return

            if len(chosen_text) > 1900:
                bio = io.BytesIO(chosen_text.encode("utf-8"))
                bio.seek(0)
                file = discord.File(fp=bio, filename="random-text.txt")
                embed = discord.Embed(title="📝 隨機文字（太长，已作为文件发送）", color=discord.Color.green(), timestamp=datetime.utcnow())
                embed.add_field(name="说明", value=f"来源: data/random-text.json {'分类:'+category if category else ''}", inline=False)
                await interaction.followup.send(embed=embed, file=file)
            else:
                embed = discord.Embed(title="📝 隨機文字", description=chosen_text, color=discord.Color.green(), timestamp=datetime.utcnow())
                embed.set_footer(text=f"来源: data/random-text.json {'分类:'+category if category else ''}")
                await interaction.followup.send(embed=embed)
            log("INFO", "PLAY", f"/娛樂 隨機文字 by {interaction.user} -> category={category}")
        except Exception as e:
            log_exception("ERROR", "PLAY", "random-text 处理失败", exc=e)
            try:
                await interaction.followup.send("处理随机文本时发生错误，详情请查看日志。", ephemeral=True)
            except Exception:
                pass

    # --- 隨機推薦音樂 (random-music from web) ---
    @娛樂.command(name="隨機推薦音樂", description="从网络随机推荐一首音乐（支持分类：流行/摇滚/电子/嘻哈/古典/爵士）")
    @app_commands.describe(
        category="音乐分类（可选）",
        source="音乐来源：lastfm(推薦) 或 itunes（暫時無法使用）"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="流行 Pop", value="pop"),
        app_commands.Choice(name="摇滚 Rock", value="rock"),
        app_commands.Choice(name="电子 Electronic", value="electronic"),
        app_commands.Choice(name="嘻哈 Hip-Hop", value="hip-hop"),
        app_commands.Choice(name="古典 Classical", value="classical"),
        app_commands.Choice(name="爵士 Jazz", value="jazz"),
        app_commands.Choice(name="随机 Random", value="random"),
    ])
    @app_commands.choices(source=[
        app_commands.Choice(name="Last.fm", value="lastfm"),
        app_commands.Choice(name="iTunes", value="itunes"),
    ])
    async def random_music_cn(
        self, 
        interaction: discord.Interaction, 
        category: Optional[str] = None,
        source: Optional[str] = "lastfm"  # 預設值已修改為 lastfm
    ):
        """
        /娛樂 隨機推薦音樂 [category] [source]
        從網路 API 隨機抓取音樂並以 Embed 展示
        """
        await interaction.response.defer()
        try:
            # 如果没指定分类，随机选一个
            if not category or category == "random":
                category = random.choice(["pop", "rock", "electronic", "hip-hop", "classical", "jazz"])
            
            music_data = None
            
            # 優先處理判斷邏輯
            if source == "itunes":
                music_data = await self._fetch_itunes_music(category)
            else:
                # 預設或明確選擇 lastfm
                music_data = await self._fetch_lastfm_music(category)
            
            if not music_data:
                await interaction.followup.send(
                    f"❌ 无法从 {source} 获取音乐推荐，请稍后再试或更换分类/来源。",
                    ephemeral=True
                )
                return
            
            # 构建 Embed
            title = music_data.get("title", "未知標題")
            artist = music_data.get("artist", "未知藝術家")
            url = music_data.get("url", "")
            thumbnail = music_data.get("thumbnail", "")
            album = music_data.get("album", "")
            genre = music_data.get("genre", category)
            preview_url = music_data.get("preview_url", "")
            
            embed = discord.Embed(
                title=f"🎧 {title}",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            if url:
                try:
                    embed.url = url
                except Exception:
                    pass
            
            embed.add_field(name="🎤 藝術家", value=artist, inline=True)
            
            if album:
                embed.add_field(name="💿 專輯", value=album, inline=True)
            
            embed.add_field(name="🎵 分類", value=genre.title(), inline=True)
            
            if preview_url:
                embed.add_field(name="🔊 試聽", value=f"[點擊試聽]({preview_url})", inline=False)
            
            if thumbnail:
                try:
                    embed.set_thumbnail(url=thumbnail)
                except Exception:
                    pass
            
            embed.set_footer(text=f"來源: {source.upper()} API | 分類: {category}")
            
            await interaction.followup.send(embed=embed)
            log("INFO", "PLAY", f"/娛樂 隨機推薦音樂 by {interaction.user} -> {title} / {artist} (from {source})")
            
        except Exception as e:
            log_exception("ERROR", "PLAY", "random-music 处理失败", exc=e)
            try:
                await interaction.followup.send(
                    "❌ 处理随机音乐时发生错误，详情请查看日志。",
                    ephemeral=True
                )
            except Exception:
                pass
    
    async def _fetch_itunes_music(self, category: str) -> Optional[Dict[str, str]]:
        """从 iTunes API 获取音乐"""
        import aiohttp
        
        # 分类到搜索关键词的映射
        genre_keywords = {
            "pop": ["pop", "top hits", "chart"],
            "rock": ["rock", "alternative", "indie"],
            "electronic": ["electronic", "edm", "dance"],
            "hip-hop": ["hip hop", "rap", "trap"],
            "classical": ["classical", "orchestra", "symphony"],
            "jazz": ["jazz", "blues", "soul"],
        }
        
        keywords = genre_keywords.get(category, ["music"])
        search_term = random.choice(keywords)
        
        try:
            async with aiohttp.ClientSession() as session:
                # iTunes Search API
                url = "https://itunes.apple.com/search"
                params = {
                    "term": search_term,
                    "media": "music",
                    "entity": "song",
                    "limit": 50,  # 获取50首，然后随机选一首
                }
                
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        log("ERROR", "PLAY", f"iTunes API 返回状态码: {resp.status}")
                        return None
                    
                    data = await resp.json()
                    results = data.get("results", [])
                    
                    if not results:
                        log("WARN", "PLAY", f"iTunes API 没有返回结果，分类: {category}")
                        return None
                    
                    # 随机选择一首歌
                    track = random.choice(results)
                    
                    return {
                        "title": track.get("trackName", "未知標題"),
                        "artist": track.get("artistName", "未知藝術家"),
                        "album": track.get("collectionName", ""),
                        "genre": track.get("primaryGenreName", category),
                        "url": track.get("trackViewUrl", ""),
                        "preview_url": track.get("previewUrl", ""),
                        "thumbnail": track.get("artworkUrl100", "").replace("100x100", "600x600"),  # 高清封面
                    }
        except asyncio.TimeoutError:
            log("ERROR", "PLAY", "iTunes API 请求超时")
            return None
        except Exception as e:
            log_exception("ERROR", "PLAY", "iTunes API 请求失败", exc=e)
            return None
    
    async def _fetch_lastfm_music(self, category: str) -> Optional[Dict[str, str]]:
        """从 Last.fm API 获取音乐（需要 API key，这里使用公开的测试 key）"""
        import aiohttp
        
        # Last.fm 公开测试 API Key（你可以替换为自己的）
        # 注册地址: https://www.last.fm/api/account/create
        API_KEY = "8903556c166b16e79eddcb783c644dd4"  # 需要替换为真实的 API key
        
        tag_map = {
            "pop": "pop",
            "rock": "rock",
            "electronic": "electronic",
            "hip-hop": "hip hop",
            "classical": "classical",
            "jazz": "jazz",
        }
        
        tag = tag_map.get(category, "music")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Last.fm API - 获取标签下的热门曲目
                url = "http://ws.audioscrobbler.com/2.0/"
                params = {
                    "method": "tag.gettoptracks",
                    "tag": tag,
                    "api_key": API_KEY,
                    "format": "json",
                    "limit": 50,
                }
                
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        log("ERROR", "PLAY", f"Last.fm API 返回状态码: {resp.status}")
                        return None
                    
                    data = await resp.json()
                    tracks = data.get("tracks", {}).get("track", [])
                    
                    if not tracks:
                        log("WARN", "PLAY", f"Last.fm API 没有返回结果，标签: {tag}")
                        return None
                    
                    # 随机选择一首歌
                    track = random.choice(tracks)
                    
                    # 获取歌曲详细信息（包括专辑封面）
                    track_info_params = {
                        "method": "track.getInfo",
                        "artist": track.get("artist", {}).get("name", ""),
                        "track": track.get("name", ""),
                        "api_key": API_KEY,
                        "format": "json",
                    }
                    
                    async with session.get(url, params=track_info_params, timeout=10) as info_resp:
                        if info_resp.status == 200:
                            info_data = await info_resp.json()
                            track_detail = info_data.get("track", {})
                            
                            # 获取最大的专辑封面
                            images = track_detail.get("album", {}).get("image", [])
                            thumbnail = ""
                            if images:
                                for img in reversed(images):  # 从大到小
                                    if img.get("#text"):
                                        thumbnail = img["#text"]
                                        break
                            
                            return {
                                "title": track.get("name", "未知標題"),
                                "artist": track.get("artist", {}).get("name", "未知藝術家"),
                                "album": track_detail.get("album", {}).get("title", ""),
                                "genre": category,
                                "url": track.get("url", ""),
                                "preview_url": "",  # Last.fm 不提供试听
                                "thumbnail": thumbnail,
                            }
                    
                    # 如果获取详细信息失败，返回基本信息
                    return {
                        "title": track.get("name", "未知標題"),
                        "artist": track.get("artist", {}).get("name", "未知藝術家"),
                        "album": "",
                        "genre": category,
                        "url": track.get("url", ""),
                        "preview_url": "",
                        "thumbnail": "",
                    }
                    
        except asyncio.TimeoutError:
            log("ERROR", "PLAY", "Last.fm API 请求超时")
            return None
        except Exception as e:
            log_exception("ERROR", "PLAY", "Last.fm API 请求失败", exc=e)
            return None


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayCommands(bot))