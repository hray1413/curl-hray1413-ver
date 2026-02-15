import os
import json
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union

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
        traceback.print_exc()


DATA_DIR = Path("data")
MUTE_FILE = DATA_DIR / "mute.json"
WARN_FILE = DATA_DIR / "warn.json"

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _load_json(path: Path) -> Dict[str, Any]:
    _ensure_data_dir()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log_exception("ERROR", "错误", f"读取 JSON 文件 {path} 时出错")
        return {}

def _save_json(path: Path, data: Dict[str, Any]):
    _ensure_data_dir()
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        log_exception("ERROR", "错误", f"写入 JSON 文件 {path} 时出错")

def _parse_days_arg(days: Optional[int]) -> Optional[float]:
    if days is None:
        return None
    try:
        return float(days)
    except Exception:
        return None

def _expiry_to_iso(expiry_dt: Optional[datetime]) -> Optional[str]:
    return expiry_dt.isoformat() if expiry_dt else None

def _iso_to_dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

class ServerModeration(commands.Cog):
    """服务器管理 Cog：ban/unban/kick/warn/unwarn/mute/unmute 并记录到 data/*.json"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        _ensure_data_dir()
        # Load caches
        self._mutes = _load_json(MUTE_FILE)  # structure: {guild_id: {str(user_id): {reason, moderator, expires_iso, ts_iso}}}
        self._warns = _load_json(WARN_FILE)  # structure: {guild_id: {str(user_id): [ {reason, moderator, ts_iso, expires_iso?}, ... ]}}
        log("INFO", "其他", "ServerModeration Cog 初始化完成")

    # ---------- Helpers ----------
    def _save_mutes(self):
        _save_json(MUTE_FILE, self._mutes)

    def _save_warns(self):
        _save_json(WARN_FILE, self._warns)

    async def _get_member_safe(self, guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
        """
        尝试先从缓存取得 member，否则 fetch_member 回退（减少缓存导致的 permission 校验失败）。
        """
        try:
            m = guild.get_member(user_id)
            if m:
                return m
            # fetch_member 可能会因为权限/隐私失败，捕获异常
            try:
                return await guild.fetch_member(user_id)
            except Exception:
                return None
        except Exception:
            return None

    def _is_guild_admin(self, member: Optional[discord.Member]) -> bool:
        # 判断调用者是否在该服务器拥有管理员权限（administrator）
        try:
            if member is None:
                return False
            return bool(member.guild_permissions.administrator)
        except Exception:
            return False

    def _require_permission_for_action(self, member: Optional[discord.Member], action: str) -> bool:
        """
        根据 action 要求不同权限，管理员 (administrator) 直接通过。
        member 可以为 None（则返回 False）。
        """
        if member is None:
            return False
        try:
            if member.guild_permissions.administrator:
                return True
            perms = member.guild_permissions
            if action == "ban":
                return perms.ban_members
            if action == "kick":
                return perms.kick_members
            if action == "mute":
                # allow manage_messages OR moderate_members (timeout/kick/role manage) OR manage_roles
                return perms.manage_messages or perms.moderate_members or perms.manage_roles
            if action == "warn":
                return perms.manage_messages or perms.kick_members or perms.ban_members
            return False
        except Exception:
            return False

    def _check_hierarchy(self, moderator: discord.Member, target: Optional[discord.Member]) -> bool:
        """
        确认 moderator 在角色层级上高于 target，若 target 为 None（非服务器成员），只有当 moderator 为 admin 时允许操作。
        """
        try:
            if moderator.guild_permissions.administrator:
                return True
            if target is None:
                # 无法比较层级，拒绝（仅 admin 可操作非 Member 对象）
                return False
            return moderator.top_role > target.top_role
        except Exception:
            return False

    # ---------- Mute enforcement (message delete + DM) ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return

        guild = message.guild
        if guild is None:
            return

        guild_mutes = self._mutes.get(str(guild.id), {})
        entry = guild_mutes.get(str(message.author.id))
        if not entry:
            return

        # Check expiry
        expires_iso = entry.get("expires")
        expires_dt = _iso_to_dt(expires_iso)
        now = datetime.utcnow()
        if expires_dt and now >= expires_dt:
            # expired -> remove mute
            guild_mutes.pop(str(message.author.id), None)
            self._mutes[str(guild.id)] = guild_mutes
            self._save_mutes()
            return

        # Delete the message and DM the user (embed)
        try:
            # Attempt to delete the message
            try:
                await message.delete()
            except Exception:
                pass  # ignore deletion errors

            # Send DM
            reason = entry.get("reason", "未提供")
            expires_text = "永久" if not expires_dt else f"至 {expires_dt.isoformat()} UTC"
            try:
                dm_embed = discord.Embed(title="你已被禁言", color=discord.Color.red())
                dm_embed.add_field(name="服务器", value=guild.name, inline=False)
                dm_embed.add_field(name="原因", value=str(reason), inline=False)
                dm_embed.add_field(name="禁言时间", value=expires_text, inline=False)
                dm_embed.set_footer(text="你在该服务器发送消息的内容会被自动删除")
                await message.author.send(embed=dm_embed)
            except Exception:
                # DM 失败（可能对方关闭私信），忽略
                pass

            # log
            log("INFO", "使用", f"Muted member {message.author.id} in guild {guild.id} attempted to send message; message deleted")
        except Exception as e:
            log_exception("ERROR", "错误", "处理被禁言用户消息时出错", exc=e)

    # ---------- Slash command group ----------
    server_group = app_commands.Group(name="server", description="服务器管理（仅限服务器管理员/有相应权限的用户）")

    # ---- ban ----
    @server_group.command(name="ban", description="封禁指定用户（使用 Discord 内建封禁机制）")
    @app_commands.describe(target="要封禁的用户（提及或用户 ID）", days="封禁时长（天，可选）", reason="封禁原因（可选）")
    async def ban(self, interaction: discord.Interaction, target: discord.User, days: Optional[int] = None, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "ban"):
            await interaction.followup.send("你没有权限封禁用户（需要 Ban Members 权限）。", ephemeral=True)
            return

        # resolve member if possible
        member = guild.get_member(target.id)
        # hierarchy check if member exists; if cannot check and moderator is not admin, deny
        if member:
            if not self._check_hierarchy(moderator, member):
                await interaction.followup.send("无法对该用户执行操作（权限或角色层级不足）。", ephemeral=True)
                return
        else:
            # target not a member; only allow if moderator is admin
            if not self._is_guild_admin(moderator):
                await interaction.followup.send("无法对该用户执行操作（目标不在本服务器且你不是管理员）。", ephemeral=True)
                return

        # compute duration (days -> expiry)
        expiry_dt = None
        days_f = _parse_days_arg(days)
        if days_f:
            expiry_dt = datetime.utcnow() + timedelta(days=days_f)

        try:
            # use guild.ban
            await guild.ban(target, reason=reason or f"Banned by {interaction.user}", delete_message_days=0)
            log("INFO", "啟動", f"{interaction.user} 封禁了 {target} in guild {guild.id} reason={reason} expiry={expiry_dt}")
            await interaction.followup.send(f"已封禁用户 {target}（到期: {expiry_dt.isoformat() if expiry_dt else '永久'}）", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("机器人没有权限封禁该用户（Missing Permissions）。", ephemeral=True)
        except Exception as e:
            log_exception("ERROR", "错误", "执行封禁时出错", exc=e)
            await interaction.followup.send("封禁过程中发生错误（详见日志）。", ephemeral=True)

    # ---- unban ----
    @server_group.command(name="unban", description="解除封禁指定用户（输入用户ID）")
    @app_commands.describe(target="要解除封禁的用户（用户 ID）")
    async def unban(self, interaction: discord.Interaction, target: int):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "ban"):
            await interaction.followup.send("你没有权限解除封禁（需要 Ban Members 权限）。", ephemeral=True)
            return

        try:
            user_id = int(target)
        except Exception:
            await interaction.followup.send("请提供有效的用户 ID。", ephemeral=True)
            return

        try:
            banned_entries = await guild.bans()
            for entry in banned_entries:
                if entry.user.id == user_id:
                    await guild.unban(entry.user, reason=f"Unbanned by {interaction.user}")
                    log("INFO", "其他", f"{interaction.user} 在 {guild.id} 解封用户 {user_id}")
                    await interaction.followup.send(f"已解除对用户 {user_id} 的封禁。", ephemeral=True)
                    return
            await interaction.followup.send("目标用户不在该服务器的封禁列表中。", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("机器人没有权限解除封禁（Missing Permissions）。", ephemeral=True)
        except Exception as e:
            log_exception("ERROR", "错误", "解除封禁时出错", exc=e)
            await interaction.followup.send("解除封禁时发生错误（详见日志）。", ephemeral=True)

    # ---- kick ----
    @server_group.command(name="kick", description="踢出指定用户（使用 Discord 内建的踢出功能）")
    @app_commands.describe(target="要踢出的用户（提及或用户 ID）", reason="踢出原因（可选）")
    async def kick(self, interaction: discord.Interaction, target: discord.User, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "kick"):
            await interaction.followup.send("你没有权限踢出用户（需要 Kick Members 权限）。", ephemeral=True)
            return

        member = guild.get_member(target.id)
        if not member:
            await interaction.followup.send("目标用户不在本服务器内。", ephemeral=True)
            return

        if not self._check_hierarchy(moderator, member):
            await interaction.followup.send("无法对该用户执行操作（权限或角色层级不足）。", ephemeral=True)
            return

        try:
            await member.kick(reason=reason or f"Kicked by {interaction.user}")
            log("INFO", "其他", f"{interaction.user} 在 {guild.id} 踢出了 {target}")
            await interaction.followup.send(f"已踢出用户 {target}。", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("机器人没有权限踢出该用户（Missing Permissions）。", ephemeral=True)
        except Exception as e:
            log_exception("ERROR", "错误", "踢出时出错", exc=e)
            await interaction.followup.send("踢出过程中发生错误（详见日志）。", ephemeral=True)

    # ---- warn ----
    @server_group.command(name="warn", description="警告用户并记录（可选时长）")
    @app_commands.describe(target="要警告的用户（提及或用户 ID）", days="警告持续天数（选填）", reason="警告原因（可选）")
    async def warn(self, interaction: discord.Interaction, target: discord.User, days: Optional[int] = None, reason: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "warn"):
            await interaction.followup.send("你没有权限警告用户（需要管理/踢/封禁类权限）。", ephemeral=True)
            return

        expires_dt = None
        days_f = _parse_days_arg(days)
        if days_f:
            expires_dt = datetime.utcnow() + timedelta(days=days_f)

        # Save warn record
        guild_warns = self._warns.get(str(guild.id), {})
        user_warns = guild_warns.get(str(target.id), [])
        record = {
            "moderator": interaction.user.id,
            "moderator_name": f"{interaction.user.name}#{interaction.user.discriminator}",
            "reason": reason or "未提供",
            "timestamp": datetime.utcnow().isoformat(),
            "expires": _expiry_to_iso(expires_dt),
        }
        user_warns.append(record)
        guild_warns[str(target.id)] = user_warns
        self._warns[str(guild.id)] = guild_warns
        self._save_warns()

        # Optionally DM the user about the warn
        try:
            dm_embed = discord.Embed(title="你已收到警告", color=discord.Color.orange())
            dm_embed.add_field(name="服务器", value=guild.name, inline=False)
            dm_embed.add_field(name="原因", value=record["reason"], inline=False)
            dm_embed.add_field(name="来自", value=record["moderator_name"], inline=False)
            dm_embed.add_field(name="持续", value=("永久" if not expires_dt else f"到 {expires_dt.isoformat()} UTC"), inline=False)
            await target.send(embed=dm_embed)
        except Exception:
            pass

        log("INFO", "其他", f"{interaction.user} 警告了 {target} in guild {guild.id} reason={reason} expires={_expiry_to_iso(expires_dt)}")
        await interaction.followup.send(f"已警告用户 {target}（到期: {_expiry_to_iso(expires_dt) if expires_dt else '永久'}），并记录在 /data/warn.json。", ephemeral=True)

    # ---- unwarn ----
    @server_group.command(name="unwarn", description="移除用户最近的一条警告记录")
    @app_commands.describe(target="要移除警告的用户（提及或用户 ID）")
    async def unwarn(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "warn"):
            await interaction.followup.send("你没有权限移除警告（需要管理/踢/封禁类权限）。", ephemeral=True)
            return

        guild_warns = self._warns.get(str(guild.id), {})
        user_warns = guild_warns.get(str(target.id), [])
        if not user_warns:
            await interaction.followup.send("该用户没有警告记录。", ephemeral=True)
            return

        removed = user_warns.pop()  # remove last warn
        guild_warns[str(target.id)] = user_warns
        self._warns[str(guild.id)] = guild_warns
        self._save_warns()
        log("INFO", "其他", f"{interaction.user} 在 {guild.id} 移除 {target} 的一条警告记录")
        await interaction.followup.send(f"已移除该用户最近一条警告（原因：{removed.get('reason')}）。", ephemeral=True)

    # ---- mute ----
    @server_group.command(name="mute", description="禁言用户（不会删除发言权限但会立即删除其发送的消息并私信告知）")
    @app_commands.describe(target="要禁言的用户（提及或用户 ID）", days="禁言时长（天，可选）", reason="禁言原因（可选）")
    async def mute(self, interaction: discord.Interaction, target: discord.User, days: Optional[int] = None, reason: Optional[str] = None):
        """
        实现: 记录到 /data/mute.json，所有该服务器中被记录为 mute 的用户其发送的消息会被 on_message 检测到并删除，
        并尝试私信通知被禁言用户（带 embed）。
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "mute"):
            await interaction.followup.send("你没有权限禁言该用户（需要管理消息 / 管理角色 / 或 moderate_members 权限）。", ephemeral=True)
            return

        member = guild.get_member(target.id)
        if member and not self._check_hierarchy(moderator, member):
            await interaction.followup.send("无法对该用户执行操作（权限或角色层级不足）。", ephemeral=True)
            return

        # If target not member, only admin can mute by ID (rare)
        if not member and not self._is_guild_admin(moderator):
            await interaction.followup.send("目标用户不在本服务器内，且你不是管理员，无法执行禁言。", ephemeral=True)
            return

        days_f = _parse_days_arg(days)
        expires_dt = None
        if days_f:
            expires_dt = datetime.utcnow() + timedelta(days=days_f)

        # record into mutes JSON
        guild_mutes = self._mutes.get(str(guild.id), {})
        guild_mutes[str(target.id)] = {
            "reason": reason or "未提供",
            "moderator": interaction.user.id,
            "moderator_name": f"{interaction.user.name}#{interaction.user.discriminator}",
            "timestamp": datetime.utcnow().isoformat(),
            "expires": _expiry_to_iso(expires_dt),
        }
        self._mutes[str(guild.id)] = guild_mutes
        self._save_mutes()

        # DM the user about the mute
        try:
            dm_embed = discord.Embed(title="你已被禁言", color=discord.Color.red())
            dm_embed.add_field(name="服务器", value=guild.name, inline=False)
            dm_embed.add_field(name="原因", value=reason or "未提供", inline=False)
            dm_embed.add_field(name="禁言时间", value=("永久" if not expires_dt else f"到 {expires_dt.isoformat()} UTC"), inline=False)
            dm_embed.set_footer(text="你发送消息将会被自动删除")
            await target.send(embed=dm_embed)
        except Exception:
            pass

        log("INFO", "其他", f"{interaction.user} 在 {guild.id} 禁言了 {target} expires={_expiry_to_iso(expires_dt)}")
        await interaction.followup.send(f"已将用户 {target} 列入禁言（到期: {_expiry_to_iso(expires_dt) if expires_dt else '永久'}），记录在 /data/mute.json。", ephemeral=True)

    # ---- unmute ----
    @server_group.command(name="unmute", description="解除禁言用户")
    @app_commands.describe(target="要解除禁言的用户（提及或用户 ID）")
    async def unmute(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return

        moderator = await self._get_member_safe(guild, interaction.user.id)
        if not self._require_permission_for_action(moderator, "mute"):
            await interaction.followup.send("你没有权限解除禁言（需要管理消息 / 管理角色 / 或 moderate_members 权限）。", ephemeral=True)
            return

        guild_mutes = self._mutes.get(str(guild.id), {})
        if str(target.id) not in guild_mutes:
            await interaction.followup.send("该用户当前未被禁言。", ephemeral=True)
            return

        guild_mutes.pop(str(target.id), None)
        self._mutes[str(guild.id)] = guild_mutes
        self._save_mutes()
        log("INFO", "其他", f"{interaction.user} 在 {guild.id} 解除 {target} 的禁言")
        await interaction.followup.send(f"已解除用户 {target} 的禁言。", ephemeral=True)

    # ---- view/list commands ----
    @server_group.command(name="list_mutes", description="列出本服务器当前的禁言记录")
    async def list_mutes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return
        guild_mutes = self._mutes.get(str(guild.id), {})
        if not guild_mutes:
            await interaction.followup.send("当前没有禁言记录。", ephemeral=True)
            return
        lines = []
        for uid, rec in guild_mutes.items():
            expires = rec.get("expires") or "永久"
            lines.append(f"- <@{uid}>  原因: {rec.get('reason')}  到期: {expires}")
        await interaction.followup.send("禁言列表：\n" + "\n".join(lines), ephemeral=True)

    @server_group.command(name="list_warns", description="列出本服务器指定用户的警告记录")
    @app_commands.describe(target="要查询的用户（提及或用户 ID）")
    async def list_warns(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("该指令只能在服务器内使用。", ephemeral=True)
            return
        guild_warns = self._warns.get(str(guild.id), {})
        user_warns = guild_warns.get(str(target.id), [])
        if not user_warns:
            await interaction.followup.send("该用户没有警告记录。", ephemeral=True)
            return
        lines = []
        for idx, rec in enumerate(user_warns, start=1):
            lines.append(f"{idx}. 时间: {rec.get('timestamp')} 来自: <@{rec.get('moderator')}> 原因: {rec.get('reason')} 到期: {rec.get('expires') or '永久'}")
        await interaction.followup.send("警告记录：\n" + "\n".join(lines), ephemeral=True)

    # ---------- Cog unload ----------
    async def cog_unload(self):
        # persist caches
        try:
            self._save_mutes()
            self._save_warns()
        except Exception:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerModeration(bot))