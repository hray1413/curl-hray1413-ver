"""
cogs/bot_global_moderation.py

全局机器人管理 Cog（仅 OWNER 可用）

功能说明：
- 全局封禁/解封：/bot ban, /bot unban
- 全局禁言/取消禁言：/bot mute, /bot unmute
- 全局记录警告/移除最近一条警告：/bot warn, /bot unwarn
- 列表查询：/bot list_bans, /bot list_mutes, /bot list_warns
- 全局 app command check：阻止被封禁或禁言用户使用任何 app command
- 广播发送：所有会使用 _broadcast_embed()，优先使用 data/channel.json 映射的频道，
  若映射缺失或失效会按名称查找 CH_NAME（不区分大小写），若仍无且 bot 有权限会创建频道并写入映射。
- data files:
  - data/global_ban.json
  - data/global_mute.json
  - data/global_warn.json
  - data/channel.json

注意：
- OWNER 判定由环境变量 OWNER 决定（支持 user id 或 "name" / "name#discriminator"）。
- 所有对外通知会尝试 DM 目标用户（若可达）并广播到映射/创建的公告频道。
- 请确保机器人在目标服务器具有 Manage Channels 权限以便自动创建频道时使用。
"""

from __future__ import annotations

import os
import json
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord import app_commands
from discord.ext import commands

try:
    from utils.logger import log, log_exception
except Exception:
    def log(status, kind, message, **_):
        print(f"[LOG {status} {kind}] {message}")
    def log_exception(status, kind, message, exc=None, **_):
        print(f"[LOG EXC] {message}")
        if exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)


DATA_DIR = Path("data")
BAN_FILE = DATA_DIR / "global_ban.json"
MUTE_FILE = DATA_DIR / "global_mute.json"
WARN_FILE = DATA_DIR / "global_warn.json"
DATA_CHANNEL_FILE = DATA_DIR / "channel.json"  # mapping: { "<guild_id>": <channel_id>, ... }

CH_NAME = "极光BOT-更新"  # 通知频道名称（可修改）


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Dict[str, Any]:
    _ensure_data_dir()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_exception("ERROR", "IO", f"读取 JSON 文件 {path} 时出错", exc=e)
        return {}


def _save_json(path: Path, data: Dict[str, Any]):
    _ensure_data_dir()
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_exception("ERROR", "IO", f"写入 JSON 文件 {path} 时出错", exc=e)


def _load_channel_map() -> Dict[str, int]:
    _ensure_data_dir()
    if not DATA_CHANNEL_FILE.exists():
        return {}
    try:
        with DATA_CHANNEL_FILE.open("r", encoding="utf-8") as f:
            obj = json.load(f)
            if isinstance(obj, dict):
                out: Dict[str, int] = {}
                for k, v in obj.items():
                    try:
                        out[str(k)] = int(v)
                    except Exception:
                        continue
                return out
    except Exception as e:
        log_exception("ERROR", "IO", f"读取 channel map {DATA_CHANNEL_FILE} 失败", exc=e)
    return {}


def _save_channel_map(m: Dict[str, int]):
    _ensure_data_dir()
    try:
        with DATA_CHANNEL_FILE.open("w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_exception("ERROR", "IO", f"写入 channel map {DATA_CHANNEL_FILE} 失败", exc=e)


def _iso_now() -> str:
    return datetime.utcnow().isoformat()


def _iso_plus_days(days: Optional[int]) -> Optional[str]:
    if days is None:
        return None
    try:
        return (datetime.utcnow() + timedelta(days=float(days))).isoformat()
    except Exception:
        return None


def _iso_to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


class BotGlobalModeration(commands.Cog):
    """全局机器人管理（OWNER 专用）"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # load persisted records
        self._bans: Dict[str, Any] = _load_json(BAN_FILE)
        self._mutes: Dict[str, Any] = _load_json(MUTE_FILE)
        self._warns: Dict[str, List[Dict[str, Any]]] = _load_json(WARN_FILE)
        # channel mapping: guild_id (str) -> channel_id (int)
        self._channel_map: Dict[str, int] = _load_channel_map()

        # Register global check once
        try:
            if not getattr(self.bot, "_global_mod_check_registered", False):
                if hasattr(self.bot.tree, "add_check"):
                    self.bot.tree.add_check(self._global_app_command_check)  # type: ignore
                else:
                    try:
                        for cmd in list(self.bot.tree.walk_commands()):
                            checks = getattr(cmd, "checks", None)
                            if isinstance(checks, list):
                                checks.append(self._global_app_command_check)  # type: ignore
                    except Exception as e:
                        log_exception("WARN", "INIT", "向每个命令追加检查失败", exc=e)
                self.bot._global_mod_check_registered = True
                log("INFO", "INIT", "已注册全局 bot moderation app_command check")
        except Exception as e:
            log_exception("ERROR", "INIT", "注册全局 app_command check 失败", exc=e)

    # Persistence helpers
    def _save_all(self):
        _save_json(BAN_FILE, self._bans)
        _save_json(MUTE_FILE, self._mutes)
        _save_json(WARN_FILE, self._warns)
        # channel map is saved when changed

    # OWNER check
    def _is_owner(self, user: discord.abc.Snowflake) -> bool:
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

    # expiry helpers
    def _is_expired(self, rec: Dict[str, Any]) -> bool:
        exp = rec.get("expires")
        if not exp:
            return False
        dt = _iso_to_dt(exp)
        if not dt:
            return False
        return datetime.utcnow() >= dt

    def _cleanup_expired(self):
        removed = []
        for uid, rec in list(self._bans.items()):
            if self._is_expired(rec):
                self._bans.pop(uid, None)
                removed.append(("ban", uid))
        for uid, rec in list(self._mutes.items()):
            if self._is_expired(rec):
                self._mutes.pop(uid, None)
                removed.append(("mute", uid))
        if removed:
            self._save_all()
            log("INFO", "CLEANUP", f"清理过期记录: {removed}")

    # Global app command check
    async def _global_app_command_check(self, interaction: discord.Interaction, *args, **kwargs) -> bool:
        try:
            self._cleanup_expired()
            uid = str(interaction.user.id)
            if uid in self._bans:
                raise app_commands.CheckFailure("你已被全局封禁，无法使用机器人。")
            if uid in self._mutes:
                raise app_commands.CheckFailure("你已被全局禁言，无法使用机器人。")
            return True
        except app_commands.CheckFailure:
            raise
        except Exception as e:
            log_exception("WARN", "CHECK", "全局检查内部错误，允许命令通过", exc=e)
            return True

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        try:
            if isinstance(error, app_commands.CheckFailure):
                msg = str(error)
                if "全局" in msg or "无法使用机器人" in msg:
                    try:
                        await interaction.response.send_message(msg, ephemeral=True)
                    except Exception:
                        try:
                            await interaction.followup.send(msg, ephemeral=True)
                        except Exception:
                            pass
        except Exception:
            pass

    # Broadcast helper: uses data/channel.json mapping; create channel if missing and permitted
    async def _broadcast_embed(self, embed: discord.Embed, skip_guilds: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        向所有加入的 guild 的指定频道发送 embed。
        优先使用 DATA_CHANNEL_FILE 中的映射；若无或失效则按 CH_NAME 不区分大小写查找；
        若仍未找到且 bot 有 manage_channels 权限，则尝试创建 CH_NAME 并保存映射。
        返回：{"success_count": int, "fail_count": int, "failures": [(guild_id, reason), ...]}
        """
        skip_guilds = skip_guilds or []
        success = 0
        failures: List[Tuple[int, str]] = []

        # reload channel mapping to pick up any external edits
        try:
            self._channel_map = _load_channel_map()
        except Exception as e:
            log_exception("WARN", "IO", "加载 channel map 失败，继续使用内存映射", exc=e)

        for guild in list(self.bot.guilds):
            try:
                if guild.id in skip_guilds:
                    continue
                gid_str = str(guild.id)
                target_ch: Optional[discord.TextChannel] = None

                # 1) Try mapped channel id first
                mapped_id = self._channel_map.get(gid_str)
                if mapped_id:
                    try:
                        target_ch = guild.get_channel(int(mapped_id))
                        if target_ch is None:
                            try:
                                target_ch = await guild.fetch_channel(int(mapped_id))
                            except Exception:
                                target_ch = None
                        if target_ch and not isinstance(target_ch, discord.TextChannel):
                            target_ch = None
                    except Exception:
                        target_ch = None
                    if target_ch is None and mapped_id:
                        # stale mapping, remove it and continue
                        log("WARN", "CHANNEL_MAP", f"映射频道不存在或不可用，移除映射 guild={gid_str} channel={mapped_id}")
                        self._channel_map.pop(gid_str, None)
                        try:
                            _save_channel_map(self._channel_map)
                        except Exception:
                            pass
                        mapped_id = None

                # 2) Try case-insensitive name search if no mapped channel
                if target_ch is None:
                    try:
                        target_ch = next((c for c in guild.text_channels if c.name.lower() == CH_NAME.lower()), None)
                    except Exception:
                        target_ch = discord.utils.get(guild.text_channels, name=CH_NAME)
                    if target_ch and gid_str not in self._channel_map:
                        # save mapping for future
                        self._channel_map[gid_str] = target_ch.id
                        try:
                            _save_channel_map(self._channel_map)
                        except Exception as e:
                            log_exception("WARN", "IO", f"保存 channel map 失败 guild={gid_str}", exc=e)

                # 3) If still not found, attempt to create channel if bot has permission
                if target_ch is None:
                    me = guild.me or (await guild.fetch_member(self.bot.user.id))
                    if not me:
                        failures.append((guild.id, "无法取得机器人成员对象"))
                        continue
                    if not me.guild_permissions.manage_channels:
                        failures.append((guild.id, "未找到频道且机器人无创建频道权限"))
                        continue

                    # Re-check existing channels to avoid race
                    try:
                        existing = next((c for c in guild.text_channels if c.name.lower() == CH_NAME.lower()), None)
                    except Exception:
                        existing = discord.utils.get(guild.text_channels, name=CH_NAME)
                    if existing:
                        target_ch = existing
                        self._channel_map[gid_str] = target_ch.id
                        try:
                            _save_channel_map(self._channel_map)
                        except Exception as e:
                            log_exception("WARN", "IO", f"保存 channel map 失败 guild={gid_str}", exc=e)
                    else:
                        # Attempt creation
                        try:
                            target_ch = await guild.create_text_channel(CH_NAME, reason="Created by BotGlobalModeration for announcements")
                            self._channel_map[gid_str] = target_ch.id
                            try:
                                _save_channel_map(self._channel_map)
                            except Exception as e:
                                log_exception("WARN", "IO", f"保存 channel map 失败 guild={gid_str}", exc=e)
                            log("INFO", "CHANNEL_CREATE", f"为 guild={gid_str} 创建频道 id={target_ch.id}")
                        except discord.Forbidden:
                            failures.append((guild.id, "创建频道被拒绝 (Forbidden)"))
                            continue
                        except Exception as e:
                            # Creation failed; try to find again (race)
                            log_exception("WARN", "CHANNEL_CREATE", f"创建频道出错，尝试重新查找 guild={gid_str}", exc=e)
                            try:
                                target_ch = next((c for c in guild.text_channels if c.name.lower() == CH_NAME.lower()), None)
                            except Exception:
                                target_ch = discord.utils.get(guild.text_channels, name=CH_NAME)
                            if target_ch:
                                self._channel_map[gid_str] = target_ch.id
                                try:
                                    _save_channel_map(self._channel_map)
                                except Exception as se:
                                    log_exception("WARN", "IO", f"保存 channel map 失败 guild={gid_str}", exc=se)
                            else:
                                failures.append((guild.id, f"创建频道失败: {e}"))
                                continue

                # final checks before sending
                if not target_ch:
                    failures.append((guild.id, "未能确定目标频道"))
                    continue

                me = guild.me or (await guild.fetch_member(self.bot.user.id))
                perms = target_ch.permissions_for(me)
                if not perms.send_messages:
                    failures.append((guild.id, "机器人在目标频道无发送权限"))
                    continue

                # Send embed
                try:
                    await target_ch.send(embed=embed)
                    success += 1
                except Exception as e:
                    failures.append((guild.id, f"发送失败: {e}"))
                    log_exception("ERROR", "SEND", f"向 guild={guild.id} 的频道发送 embed 失败", exc=e)
            except Exception as e:
                failures.append((guild.id, f"处理异常: {e}"))
                log_exception("ERROR", "BROADCAST", f"向 guild={guild.id} 广播时发生异常", exc=e)

        return {"success_count": success, "fail_count": len(failures), "failures": failures}

    async def _dm_user_embed(self, user: discord.User, embed: discord.Embed):
        try:
            await user.send(embed=embed)
        except Exception:
            # ignore DM failures
            pass

    # Command group (app commands)
    global_group = app_commands.Group(name="bot", description="全局机器人管理（仅 OWNER 可用）")

    @global_group.command(name="ban", description="全局封禁用户（禁止使用机器人）")
    @app_commands.describe(target="目标用户", days="封禁时长（天，可选）", reason="原因（可选）")
    async def ban(self, interaction: discord.Interaction, target: discord.User, days: Optional[int] = None, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return

        uid = str(target.id)
        expires = _iso_plus_days(days)
        self._bans[uid] = {
            "moderator": interaction.user.id,
            "moderator_name": f"{interaction.user.name}#{interaction.user.discriminator}",
            "reason": reason or "未提供",
            "ts": _iso_now(),
            "expires": expires,
        }
        self._save_all()

        embed = discord.Embed(title="🚫 全局封禁通知", color=discord.Color.red(), timestamp=datetime.utcnow())
        embed.add_field(name="操作", value="/bot ban", inline=True)
        embed.add_field(name="目标", value=f"{target} ({uid})", inline=True)
        embed.add_field(name="原因", value=reason or "未提供", inline=False)
        embed.add_field(name="到期", value=expires or "永久", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.set_footer(text="全局封禁已生效：该用户将无法使用本机器人。")

        res = await self._broadcast_embed(embed)
        await self._dm_user_embed(target, embed)

        await interaction.followup.send(f"已对 {target} 执行全局封禁并发送公告（成功 {res['success_count']}，失败 {res['fail_count']}）。", ephemeral=True)
        log("INFO", "GLOBAL", f"GLOBAL BAN by {interaction.user} -> {target} expires={expires}")

    @global_group.command(name="unban", description="解除全局封禁")
    @app_commands.describe(target="目标用户")
    async def unban(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return

        uid = str(target.id)
        if uid in self._bans:
            rec = self._bans.pop(uid, None)
            self._save_all()
            embed = discord.Embed(title="✅ 解除全局封禁", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="操作", value="/bot unban", inline=True)
            embed.add_field(name="目标", value=f"{target} ({uid})", inline=True)
            embed.add_field(name="执行者", value=f"{interaction.user} ({interaction.user.id})", inline=True)
            embed.set_footer(text="该用户已解除全局封禁，可再次使用机器人。")
            await self._broadcast_embed(embed)
            await self._dm_user_embed(target, embed)
            await interaction.followup.send(f"已解除 {target} 的全局封禁。", ephemeral=True)
            log("INFO", "GLOBAL", f"GLOBAL UNBAN by {interaction.user} -> {target}")
        else:
            await interaction.followup.send("目标用户未处于全局封禁状态。", ephemeral=True)

    @global_group.command(name="mute", description="全局禁言（禁止使用机器人）")
    @app_commands.describe(target="目标用户", days="禁言时长（天，可选）", reason="原因（可选）")
    async def mute(self, interaction: discord.Interaction, target: discord.User, days: Optional[int] = None, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return

        uid = str(target.id)
        expires = _iso_plus_days(days)
        self._mutes[uid] = {
            "moderator": interaction.user.id,
            "moderator_name": f"{interaction.user.name}#{interaction.user.discriminator}",
            "reason": reason or "未提供",
            "ts": _iso_now(),
            "expires": expires,
        }
        self._save_all()

        embed = discord.Embed(title="🔇 全局禁言通知", color=discord.Color.orange(), timestamp=datetime.utcnow())
        embed.add_field(name="操作", value="/bot mute", inline=True)
        embed.add_field(name="目标", value=f"{target} ({uid})", inline=True)
        embed.add_field(name="原因", value=reason or "未提供", inline=False)
        embed.add_field(name="到期", value=expires or "永久", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.set_footer(text="全局禁言已生效：该用户将无法使用本机器人。")

        res = await self._broadcast_embed(embed)
        await self._dm_user_embed(target, embed)

        await interaction.followup.send(f"已对 {target} 执行全局禁言并发送公告（成功 {res['success_count']}，失败 {res['fail_count']}）。", ephemeral=True)
        log("INFO", "GLOBAL", f"GLOBAL MUTE by {interaction.user} -> {target} expires={expires}")

    @global_group.command(name="unmute", description="解除全局禁言")
    @app_commands.describe(target="目标用户")
    async def unmute(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return

        uid = str(target.id)
        if uid in self._mutes:
            self._mutes.pop(uid, None)
            self._save_all()
            embed = discord.Embed(title="🔈 解除全局禁言", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="操作", value="/bot unmute", inline=True)
            embed.add_field(name="目标", value=f"{target} ({uid})", inline=True)
            embed.add_field(name="执行者", value=f"{interaction.user} ({interaction.user.id})", inline=True)
            embed.set_footer(text="该用户已解除全局禁言，可再次使用本机器人。")
            await self._broadcast_embed(embed)
            await self._dm_user_embed(target, embed)
            await interaction.followup.send(f"已解除 {target} 的全局禁言。", ephemeral=True)
            log("INFO", "GLOBAL", f"GLOBAL UNMUTE by {interaction.user} -> {target}")
        else:
            await interaction.followup.send("目标用户未处于全局禁言状态。", ephemeral=True)

    @global_group.command(name="warn", description="全局警告（记录）")
    @app_commands.describe(target="目标用户", days="警告持续天数（选填）", reason="警告原因（可选）")
    async def warn(self, interaction: discord.Interaction, target: discord.User, days: Optional[int] = None, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return

        uid = str(target.id)
        expires = _iso_plus_days(days)
        rec = {
            "moderator": interaction.user.id,
            "moderator_name": f"{interaction.user.name}#{interaction.user.discriminator}",
            "reason": reason or "未提供",
            "ts": _iso_now(),
            "expires": expires,
        }
        lst = self._warns.get(uid, [])
        lst.append(rec)
        self._warns[uid] = lst
        self._save_all()

        embed = discord.Embed(title="⚠️ 全局警告通知", color=discord.Color.gold(), timestamp=datetime.utcnow())
        embed.add_field(name="操作", value="/bot warn", inline=True)
        embed.add_field(name="目标", value=f"{target} ({uid})", inline=True)
        embed.add_field(name="原因", value=reason or "未提供", inline=False)
        embed.add_field(name="到期", value=expires or "永久", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.set_footer(text="全局警告已记录。")

        res = await self._broadcast_embed(embed)
        await self._dm_user_embed(target, embed)

        await interaction.followup.send(f"已对 {target} 记录全局警告并发送公告（成功 {res['success_count']}，失败 {res['fail_count']}）。", ephemeral=True)
        log("INFO", "GLOBAL", f"GLOBAL WARN by {interaction.user} -> {target} expires={expires}")

    @global_group.command(name="unwarn", description="移除用户最近一条全局警告")
    @app_commands.describe(target="目标用户")
    async def unwarn(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return

        uid = str(target.id)
        lst = self._warns.get(uid, [])
        if not lst:
            await interaction.followup.send("目标用户没有全局警告记录。", ephemeral=True)
            return
        removed = lst.pop()
        if lst:
            self._warns[uid] = lst
        else:
            self._warns.pop(uid, None)
        self._save_all()

        embed = discord.Embed(title="✅ 移除全局警告", color=discord.Color.green(), timestamp=datetime.utcnow())
        embed.add_field(name="操作", value="/bot unwarn", inline=True)
        embed.add_field(name="目标", value=f"{target} ({uid})", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.set_footer(text=f"移除的警告原因：{removed.get('reason')}")
        await self._broadcast_embed(embed)
        await self._dm_user_embed(target, embed)

        await interaction.followup.send(f"已移除 {target} 的最近一条全局警告（原因：{removed.get('reason')}）。", ephemeral=True)
        log("INFO", "GLOBAL", f"GLOBAL UNWARN by {interaction.user} -> {target}")

    @global_group.command(name="list_bans", description="列出全局封禁列表（OWNER 专用）")
    async def list_bans(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return
        self._cleanup_expired()
        if not self._bans:
            await interaction.followup.send("当前没有全局封禁记录。", ephemeral=True)
            return
        lines = []
        for uid, rec in self._bans.items():
            lines.append(f"- <@{uid}> by {rec.get('moderator_name')} until {rec.get('expires') or '永久'} (reason: {rec.get('reason')})")
        # send in chunks if long
        try:
            await interaction.followup.send("全局封禁列表：\n" + "\n".join(lines), ephemeral=True)
        except Exception:
            # fallback to multiple messages
            for i in range(0, len(lines), 20):
                try:
                    await interaction.followup.send("\n".join(lines[i:i+20]), ephemeral=True)
                except Exception:
                    pass

    @global_group.command(name="list_mutes", description="列出全局禁言列表（OWNER 专用）")
    async def list_mutes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return
        self._cleanup_expired()
        if not self._mutes:
            await interaction.followup.send("当前没有全局禁言记录。", ephemeral=True)
            return
        lines = []
        for uid, rec in self._mutes.items():
            lines.append(f"- <@{uid}> by {rec.get('moderator_name')} until {rec.get('expires') or '永久'} (reason: {rec.get('reason')})")
        try:
            await interaction.followup.send("全局禁言列表：\n" + "\n".join(lines), ephemeral=True)
        except Exception:
            for i in range(0, len(lines), 20):
                try:
                    await interaction.followup.send("\n".join(lines[i:i+20]), ephemeral=True)
                except Exception:
                    pass

    @global_group.command(name="list_warns", description="列出某用户的全局警告记录（OWNER 专用）")
    @app_commands.describe(target="目标用户")
    async def list_warns(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        if not self._is_owner(interaction.user):
            await interaction.followup.send("只有 OWNER 可以使用此指令。", ephemeral=True)
            return
        uid = str(target.id)
        lst = self._warns.get(uid, [])
        if not lst:
            await interaction.followup.send("该用户没有警告记录。", ephemeral=True)
            return
        lines = []
        for idx, rec in enumerate(lst, start=1):
            lines.append(f"{idx}. by {rec.get('moderator_name')} at {rec.get('ts')} until {rec.get('expires') or '永久'} reason: {rec.get('reason')}")
        try:
            await interaction.followup.send("该用户警告记录：\n" + "\n".join(lines), ephemeral=True)
        except Exception:
            for i in range(0, len(lines), 20):
                try:
                    await interaction.followup.send("\n".join(lines[i:i+20]), ephemeral=True)
                except Exception:
                    pass

async def setup(bot: commands.Bot):
    await bot.add_cog(BotGlobalModeration(bot))