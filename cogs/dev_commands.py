"""
cogs/dev_commands.py

/開發 群組：開發者 / OWNER 用的管理命令（僅使用中文命令名稱）

發送（/開發 發送）更新：
- 使用 data/channel.json 的映射（guild_id -> channel_id）優先發送。
- 若映射不存在或無效，會先搜尋名為 CH_NAME 的頻道（忽略大小寫）。
- 若仍未找到且機器人具有 Manage Channels 權限，則嘗試建立 CH_NAME 頻道，並在成功後寫入 data/channel.json。
- 成功/失敗/新建頻道次數會在命令回覆中呈現。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import json
import traceback

try:
    from utils.logger import log, log_exception
except Exception:
    def log(*args, **kwargs):
        print(*args, **kwargs)
    def log_exception(*args, **kwargs):
        print(*args, **kwargs)

DATA_CHANNEL_FILE = Path("data") / "channel.json"
DATA_CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
CH_NAME = "機器人公告"  # default notification channel name used by this cog

def _is_owner_user(user: discord.abc.Snowflake) -> bool:
    owner_env = os.getenv("OWNER", "")
    if not owner_env:
        return False
    try:
        if owner_env.isdigit():
            return int(owner_env) == int(getattr(user, "id", 0))
        uname = getattr(user, "name", "")
        disc = getattr(user, "discriminator", "")
        if f"{uname}#{disc}" == owner_env or uname == owner_env:
            return True
    except Exception:
        pass
    return False

def _load_channel_map() -> Dict[str, int]:
    try:
        if not DATA_CHANNEL_FILE.exists():
            return {}
        with DATA_CHANNEL_FILE.open("r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return {}
            obj = json.loads(data)
            if isinstance(obj, dict):
                out: Dict[str, int] = {}
                for k, v in obj.items():
                    try:
                        out[str(k)] = int(v)
                    except Exception:
                        continue
                return out
    except Exception as e:
        log_exception("ERROR", "DEV", f"读取 {DATA_CHANNEL_FILE} 失败", exc=e)
    return {}

def _save_channel_map(m: Dict[str, int]):
    try:
        with DATA_CHANNEL_FILE.open("w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_exception("ERROR", "DEV", f"寫入 {DATA_CHANNEL_FILE} 失敗", exc=e)

class DevCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cogs_path = Path(__file__).parent
        # load mapping now; will reload at each send to stay fresh
        self._channel_map = _load_channel_map()

    開發 = app_commands.Group(name="開發", description="開發者/OWNER 管理命令（中文）")

    @開發.command(name="延遲", description="查看機器人延遲（WebSocket latency）")
    async def ping_cn(self, interaction: discord.Interaction):
        ws_latency_ms = round(self.bot.latency * 1000, 1) if getattr(self.bot, "latency", None) is not None else None
        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.blurple(), timestamp=datetime.utcnow())
        embed.add_field(name="WebSocket 延遲", value=f"{ws_latency_ms} ms" if ws_latency_ms is not None else "不可用", inline=True)
        embed.set_footer(text="WebSocket latency via bot.latency")
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass
        log("INFO", "其他", f"/開發 延遲 requested by {interaction.user} -> {ws_latency_ms}ms")

    async def _require_owner(self, interaction: discord.Interaction) -> bool:
        if not _is_owner_user(interaction.user):
            try:
                await interaction.response.send_message("只有 OWNER 可以使用此指令。", ephemeral=True)
            except Exception:
                try:
                    await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
                except Exception:
                    pass
            return False
        return True

    @開發.command(name="發送", description="向所有已登記的頻道廣播公告（僅 OWNER）")
    @app_commands.describe(message="要廣播的公告內容（支持換行）")
    async def send_cn(self, interaction: discord.Interaction, message: str):
        if not await self._require_owner(interaction):
            return

        try:
            try:
                await interaction.response.defer(ephemeral=True)
            except Exception:
                pass

            # reload mapping from disk
            self._channel_map = _load_channel_map()

            success_count = 0
            fail_count = 0
            created_count = 0
            failures: List[Tuple[int, str]] = []

            for guild in list(self.bot.guilds):
                gid = str(guild.id)
                mapped = self._channel_map.get(gid)
                target_channel: Optional[discord.TextChannel] = None

                # Try mapped channel id first
                if mapped:
                    try:
                        target_channel = guild.get_channel(int(mapped))
                        if target_channel is None:
                            try:
                                target_channel = await guild.fetch_channel(int(mapped))
                            except Exception:
                                target_channel = None
                        if target_channel and not isinstance(target_channel, discord.TextChannel):
                            target_channel = None
                    except Exception:
                        target_channel = None
                    if target_channel is None:
                        # mapping stale; remove and continue to search/create
                        self._channel_map.pop(gid, None)
                        _save_channel_map(self._channel_map)
                        mapped = None

                # If no mapped channel, try case-insensitive name search
                if not target_channel:
                    try:
                        target_channel = next((c for c in guild.text_channels if c.name.lower() == CH_NAME.lower()), None)
                    except Exception:
                        target_channel = discord.utils.get(guild.text_channels, name=CH_NAME)

                    # if found by name but not mapped, save it
                    if target_channel and gid not in self._channel_map:
                        try:
                            self._channel_map[gid] = target_channel.id
                            _save_channel_map(self._channel_map)
                        except Exception as e:
                            log_exception("WARN", "DEV", f"保存頻道映射失敗 guild={gid}", exc=e)

                # If still not found, attempt to create if bot has permission
                if not target_channel:
                    me = guild.me or (await guild.fetch_member(self.bot.user.id))
                    if not me:
                        failures.append((guild.id, "無法取得機器人成員資訊"))
                        fail_count += 1
                        continue
                    if not me.guild_permissions.manage_channels:
                        failures.append((guild.id, "不存在目標頻道且機器人無建立頻道權限"))
                        fail_count += 1
                        continue

                    # re-check to avoid race
                    try:
                        existing = next((c for c in guild.text_channels if c.name.lower() == CH_NAME.lower()), None)
                    except Exception:
                        existing = discord.utils.get(guild.text_channels, name=CH_NAME)
                    if existing:
                        target_channel = existing
                        # save mapping
                        self._channel_map[gid] = target_channel.id
                        _save_channel_map(self._channel_map)
                    else:
                        try:
                            target_channel = await guild.create_text_channel(CH_NAME, reason=f"Created by /開發 發送 for guild {gid}")
                            self._channel_map[gid] = target_channel.id
                            _save_channel_map(self._channel_map)
                            created_count += 1
                        except discord.Forbidden:
                            failures.append((guild.id, "建立頻道被拒絕 (Forbidden)"))
                            fail_count += 1
                            continue
                        except Exception as e:
                            # try to re-find in case of race
                            log_exception("WARN", "DEV", f"建立頻道失敗，嘗試重新查找 guild={gid}", exc=e)
                            try:
                                target_channel = next((c for c in guild.text_channels if c.name.lower() == CH_NAME.lower()), None)
                            except Exception:
                                target_channel = discord.utils.get(guild.text_channels, name=CH_NAME)
                            if target_channel:
                                self._channel_map[gid] = target_channel.id
                                _save_channel_map(self._channel_map)
                            else:
                                failures.append((guild.id, f"建立頻道失敗: {e}"))
                                fail_count += 1
                                continue

                # final send attempt
                if not target_channel:
                    failures.append((guild.id, "未決定目標頻道"))
                    fail_count += 1
                    continue

                me = guild.me or (await guild.fetch_member(self.bot.user.id))
                perms = target_channel.permissions_for(me)
                if not perms.send_messages:
                    failures.append((guild.id, "機器人在目標頻道無發送權限"))
                    fail_count += 1
                    continue

                try:
                    emb = discord.Embed(title="📣 公告", description=message, color=discord.Color.blue(), timestamp=datetime.utcnow())
                    emb.set_footer(text=f"由 OWNER {interaction.user} 發起")
                    await target_channel.send(embed=emb)
                    success_count += 1
                except Exception as e:
                    log_exception("ERROR", "DEV", f"向 guild {gid} 的頻道發送公告失敗", exc=e)
                    failures.append((guild.id, f"發送失敗: {e}"))
                    fail_count += 1

            # ensure mapping persisted
            try:
                _save_channel_map(self._channel_map)
            except Exception:
                pass

            try:
                await interaction.followup.send(f"廣播完成。成功 {success_count}，失敗 {fail_count}（新建頻道 {created_count}）。", ephemeral=True)
            except Exception:
                try:
                    await interaction.response.send_message(f"廣播完成。成功 {success_count}，失敗 {fail_count}（新建頻道 {created_count}）。", ephemeral=True)
                except Exception:
                    pass

            log("INFO", "使用", f"/開發 發送 by {interaction.user} -> success={success_count} fail={fail_count} created={created_count}")
            if failures:
                log("WARN", "DEV", f"部分伺服器失敗清單: {failures}")
        except Exception as e:
            log_exception("ERROR", "錯誤", "執行 /開發 發送 發生錯誤", exc=e)
            try:
                await interaction.followup.send("廣播時發生錯誤，詳情請查看日誌。", ephemeral=True)
            except Exception:
                pass

    # ... 其餘命令保持不變（列出/重載/卸載/加載等），略為篇幅省略 ...
    # 為簡潔起見，未改動的命令（列出cogs、reload、unload、load 等）保留原實作。
    # 如果你需要我把整個檔案完整貼上（所有命令都包含），我可以再發完整內容。

async def setup(bot: commands.Bot):
    await bot.add_cog(DevCommands(bot))