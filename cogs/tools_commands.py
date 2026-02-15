"""
cogs/tools_commands.py

工具群組（合併）：
- /工具 投票            -> 创建投票（Modal），保存到 data/tools/poll.json
- /工具 用戶信息        -> 顯示並保存使用者快照到 data/tools/profile.json
- /工具 投票相關內部實作（PollModal / PollView / schedule）
- /工具 設定加入頻道    -> 設定本伺服器的加入通知頻道（僅管理員可用）
- /工具 設定離開頻道    -> 設定本伺服器的離開通知頻道（僅管理員可用）
- /工具 移除加入頻道    -> 移除本伺服器的加入通知頻道（僅管理員可用）
- /工具 移除離開頻道    -> 移除本伺服器的離開通知頻道（僅管理員可用）
- /工具 查看所有設定的頻道 -> OWNER 專用，列出所有伺服器的 join/leave 設定

存檔位置：
- 投票/用戶資料：data/tools/poll.json, data/tools/profile.json
- 加入/離開頻道：join-leave-message/join.json, join-leave-message/leave.json

權限：
- 設定/移除頻道：僅伺服器管理員（administrator）或 BOT OWNER 可操作
- 查看所有設定：僅 BOT OWNER
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

try:
    from utils.logger import log, log_exception
except Exception:
    def log(*args, **kwargs):
        print(*args, **kwargs)
    def log_exception(*args, **kwargs):
        print(*args, **kwargs)


# ---------------------------
# Files and directories
# ---------------------------
DATA_DIR = Path("data") / "tools"
POLL_FILE = DATA_DIR / "poll.json"
PROFILE_FILE = DATA_DIR / "profile.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

JL_BASE = Path("join-leave-message")
JOIN_FILE = JL_BASE / "join.json"
LEAVE_FILE = JL_BASE / "leave.json"
JL_BASE.mkdir(parents=True, exist_ok=True)


# ---------------------------
# OWNER check (env OWNER same format as other cogs)
# ---------------------------
import os
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


# ---------------------------
# Helper JSON utilities
# ---------------------------
def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_exception("ERROR", "TOOLS", f"读取 JSON {path} 失败", exc=e)
        return {}


def _save_json(path: Path, data: Dict[str, Any]):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_exception("ERROR", "TOOLS", f"写入 JSON {path} 失败", exc=e)


def _load_mapping(path: Path) -> Dict[str, int]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            out: Dict[str, int] = {}
            if isinstance(data, dict):
                for k, v in data.items():
                    try:
                        out[str(k)] = int(v)
                    except Exception:
                        continue
            return out
    except Exception as e:
        log_exception("ERROR", "JOIN_LEAVE", f"读取 {path} 失败", exc=e)
    return {}


def _save_mapping(path: Path, mapping: Dict[str, int]):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_exception("ERROR", "JOIN_LEAVE", f"寫入 {path} 失敗", exc=e)


# ---------------------------
# Poll & Profile implementation (same as before)
# ---------------------------
class PollModal(discord.ui.Modal, title="创建投票"):
    question = discord.ui.TextInput(label="投票问题", style=discord.TextStyle.short, max_length=200)
    options = discord.ui.TextInput(label="选项（逗号分隔，最多5项）", style=discord.TextStyle.long, placeholder="选项1,选项2,选项3", max_length=500)
    duration_minutes = discord.ui.TextInput(label="时长（分钟）", style=discord.TextStyle.short, placeholder="例如 60", default="60", max_length=10)
    flags = discord.ui.TextInput(label="标志（可选）", style=discord.TextStyle.short, placeholder="anonymous,multi,show_voters 例如: multi,show_voters", default="", max_length=100)

    def __init__(self, parent: "ToolsCommands", interaction: discord.Interaction):
        super().__init__()
        self.parent = parent
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        q = self.question.value.strip()
        opts_raw = self.options.value.strip()
        dur_raw = self.duration_minutes.value.strip()
        flags_raw = self.flags.value.strip().lower()
        options = [o.strip() for o in opts_raw.split(",") if o.strip()]
        if len(options) < 2:
            try:
                await interaction.response.send_message("请至少提供 2 个选项（以逗号分隔）。", ephemeral=True)
            except Exception:
                pass
            return
        if len(options) > 5:
            options = options[:5]
        try:
            duration = max(1, int(dur_raw))
        except Exception:
            duration = 60
        tokens = [t.strip() for t in flags_raw.replace("，", ",").split(",") if t.strip()]
        anon = False; multi = False; show_voters = False
        for t in tokens:
            if t in ("anonymous", "anon", "a", "匿名", "y", "yes", "true", "1"):
                anon = True
            if t in ("multi", "multi_select", "multiselect", "m", "多选", "multiple"):
                multi = True
            if t in ("show_voters", "show", "voters", "显示", "显示投票用户"):
                show_voters = True
        if anon:
            show_voters = False
        try:
            await self.parent.create_poll(interaction, q, options, duration_minutes=duration, anonymous=anon, multi_select=multi, show_voters=show_voters)
        except Exception as e:
            log_exception("ERROR", "POLL", "创建投票失败", exc=e)
            try:
                await interaction.response.send_message("创建投票时发生错误，具体见日志。", ephemeral=True)
            except Exception:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log_exception("ERROR", "POLL", "PollModal 异常", exc=error)
        try:
            await interaction.response.send_message("提交投票表单时出错。", ephemeral=True)
        except Exception:
            pass


class PollView(discord.ui.View):
    def __init__(self, parent: "ToolsCommands", poll_id: str, options: List[str], timeout: Optional[float] = None):
        super().__init__(timeout=None)
        self.parent = parent
        self.poll_id = poll_id
        self.options = options
        for idx, opt in enumerate(options):
            btn = discord.ui.Button(label=f"{opt}", style=discord.ButtonStyle.primary, custom_id=f"poll:{poll_id}:{idx}")
            btn.callback = self._make_callback(idx)
            self.add_item(btn)
        close_btn = discord.ui.Button(label="Close Poll", style=discord.ButtonStyle.danger, custom_id=f"poll:{poll_id}:close")
        close_btn.callback = self._close_callback
        self.add_item(close_btn)

    def _make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            try:
                await self.parent.handle_vote(interaction, self.poll_id, idx)
            except Exception as e:
                log_exception("ERROR", "POLL", "处理投票点击异常", exc=e)
                try:
                    await interaction.response.send_message("处理投票时出错。", ephemeral=True)
                except Exception:
                    pass
        return callback

    async def _close_callback(self, interaction: discord.Interaction):
        try:
            poll = self.parent._polls.get(self.poll_id)
            if not poll:
                await interaction.response.send_message("找不到该投票记录。", ephemeral=True)
                return
            author_id = poll.get("author_id")
            is_author = int(author_id) == interaction.user.id
            is_guild_owner = False
            if interaction.guild and interaction.guild.owner_id == interaction.user.id:
                is_guild_owner = True
            owner_env = False
            try:
                owner_env_val = os.getenv("OWNER", "")
                if owner_env_val and owner_env_val.isdigit() and int(owner_env_val) == interaction.user.id:
                    owner_env = True
            except Exception:
                owner_env = False
            if not (is_author or is_guild_owner or owner_env):
                await interaction.response.send_message("只有发起者、服务器管理员或 BOT OWNER 可提前关闭投票。", ephemeral=True)
                return
            await self.parent.close_poll(self.poll_id, closed_by=interaction.user.id)
            try:
                await interaction.response.send_message("投票已被关闭。", ephemeral=True)
            except Exception:
                pass
        except Exception as e:
            log_exception("ERROR", "POLL", "关闭投票回调错误", exc=e)
            try:
                await interaction.response.send_message("尝试关闭投票时发生错误。", ephemeral=True)
            except Exception:
                pass


# ---------------------------
# Tools Cog (Polls, Profile, Join/Leave)
# ---------------------------
class ToolsCommands(commands.Cog):
    """工具命令合集：投票、用戶資訊、加入/離開頻道設定"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # poll/profile storage
        self._polls: Dict[str, Dict[str, Any]] = _load_json(POLL_FILE) if POLL_FILE.exists() else {}
        self._profiles: Dict[str, Any] = _load_json(PROFILE_FILE) if PROFILE_FILE.exists() else {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

        # join/leave mappings
        self._joins: Dict[str, int] = _load_mapping(JOIN_FILE)
        self._leaves: Dict[str, int] = _load_mapping(LEAVE_FILE)

        # schedule existing poll closures if needed
        for pid, rec in list(self._polls.items()):
            try:
                if rec.get("closed"):
                    continue
                expires = rec.get("expires")
                if expires:
                    dt = datetime.fromisoformat(expires)
                    if dt > datetime.utcnow():
                        self._tasks[pid] = asyncio.create_task(self._schedule_close_task(pid, dt))
                    else:
                        asyncio.create_task(self.close_poll(pid, closed_by=None))
            except Exception:
                pass

    tools = app_commands.Group(name="工具", description="工具類命令（投票/用戶資料/系統設定）")

    # ---------------------------
    # Poll commands (unchanged)
    # ---------------------------
    @tools.command(name="poll", description="创建一个投票（将弹出填写界面）")
    async def poll(self, interaction: discord.Interaction):
        try:
            modal = PollModal(self, interaction)
            await interaction.response.send_modal(modal)
        except Exception as e:
            log_exception("ERROR", "POLL", "打开投票 Modal 失败", exc=e)
            try:
                await interaction.response.send_message("无法打开投票填写界面。", ephemeral=True)
            except Exception:
                pass

    async def create_poll(
        self,
        interaction: discord.Interaction,
        question: str,
        options: List[str],
        duration_minutes: int = 60,
        anonymous: bool = False,
        multi_select: bool = False,
        show_voters: bool = False,
    ):
        pid = str(int(time.time() * 1000))
        now = datetime.utcnow()
        expires_dt = now + timedelta(minutes=int(duration_minutes))
        poll = {
            "id": pid,
            "question": question,
            "options": options,
            "author_id": interaction.user.id,
            "ts": now.isoformat(),
            "expires": expires_dt.isoformat(),
            "anonymous": bool(anonymous),
            "multi": bool(multi_select),
            "show_voters": bool(show_voters),
            "votes": {},
            "counts": [0] * len(options),
            "closed": False,
            "channel_id": interaction.channel.id if interaction.channel else None,
            "message_id": None,
        }
        self._polls[pid] = poll
        _save_json(POLL_FILE, self._polls)
        embed = await self._build_poll_embed(poll)
        view = PollView(self, pid, options)
        try:
            await interaction.response.send_message(embed=embed, view=view)
            msg = await interaction.original_response()
            poll["message_id"] = msg.id
            poll["channel_id"] = msg.channel.id
            _save_json(POLL_FILE, self._polls)
            task = asyncio.create_task(self._schedule_close_task(pid, datetime.fromisoformat(poll["expires"])))
            self._tasks[pid] = task
            log("INFO", "POLL", f"创建投票 {pid} by {interaction.user} expires={poll['expires']} multi={poll['multi']} show_voters={poll['show_voters']}")
        except Exception as e:
            log_exception("ERROR", "POLL", "发送投票消息失败", exc=e)
            try:
                await interaction.followup.send("发送投票消息失败。", ephemeral=True)
            except Exception:
                pass

    async def _build_poll_embed(self, poll: Dict[str, Any]) -> discord.Embed:
        counts = [0] * len(poll.get("options", []))
        voters_per_opt: List[List[str]] = [[] for _ in range(len(poll.get("options", [])))]
        for uid, choice in poll.get("votes", {}).items():
            try:
                if poll.get("multi"):
                    if isinstance(choice, list):
                        for idx in choice:
                            if 0 <= idx < len(counts):
                                counts[idx] += 1
                                voters_per_opt[idx].append(uid)
                else:
                    idx = int(choice)
                    if 0 <= idx < len(counts):
                        counts[idx] += 1
                        voters_per_opt[idx].append(uid)
            except Exception:
                continue
        title = f"📊 {poll.get('question')}"
        embed = discord.Embed(title=title, color=discord.Color.blurple(), timestamp=datetime.utcnow())
        opts = poll.get("options", [])
        total = sum(counts)
        for i, opt in enumerate(opts):
            cnt = counts[i] if i < len(counts) else 0
            pct = f"{(cnt / total * 100):.1f}%" if total > 0 else "0.0%"
            field_value = f"{cnt} 票 • {pct}"
            if poll.get("show_voters") and not poll.get("anonymous"):
                names = []
                uids = voters_per_opt[i][:10]
                for uid in uids:
                    try:
                        user_obj = self.bot.get_user(int(uid))
                        if user_obj is None:
                            user_obj = await self.bot.fetch_user(int(uid))
                        names.append(str(user_obj))
                    except Exception:
                        names.append(f"<@{uid}>")
                if names:
                    field_value += "\n投票者: " + ", ".join(names)
                    if len(voters_per_opt[i]) > len(names):
                        field_value += f" 等 {len(voters_per_opt[i])} 人"
            embed.add_field(name=f"{i+1}. {opt}", value=field_value, inline=False)
        expires = poll.get("expires")
        closed = poll.get("closed", False)
        if closed:
            embed.set_footer(text="投票已结束")
        else:
            extras = []
            if poll.get("multi"):
                extras.append("多选")
            if poll.get("anonymous"):
                extras.append("匿名")
            if poll.get("show_voters") and not poll.get("anonymous"):
                extras.append("显示投票用户")
            footer_text = f"到期: {expires}"
            if extras:
                footer_text += " • " + " ".join(extras)
            embed.set_footer(text=footer_text)
        return embed

    async def handle_vote(self, interaction: discord.Interaction, poll_id: str, opt_idx: int):
        poll = self._polls.get(poll_id)
        if not poll:
            await interaction.response.send_message("找不到該投票。", ephemeral=True)
            return
        if poll.get("closed"):
            await interaction.response.send_message("投票已結束，無法投票。", ephemeral=True)
            return
        lock = self._locks.get(poll_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[poll_id] = lock
        async with lock:
            uid = str(interaction.user.id)
            multi = bool(poll.get("multi"))
            prev = poll["votes"].get(uid)
            if multi:
                if prev is None:
                    prev_list: List[int] = []
                elif isinstance(prev, list):
                    prev_list = prev
                else:
                    try:
                        prev_list = [int(prev)]
                    except Exception:
                        prev_list = []
                if opt_idx in prev_list:
                    prev_list = [i for i in prev_list if i != opt_idx]
                else:
                    prev_list.append(opt_idx)
                poll["votes"][uid] = prev_list
            else:
                try:
                    prev_int = int(prev) if prev is not None else None
                except Exception:
                    prev_int = None
                poll["votes"][uid] = opt_idx
            poll["counts"] = [0] * len(poll.get("options", []))
            for _uid, choice in poll.get("votes", {}).items():
                try:
                    if poll.get("multi"):
                        if isinstance(choice, list):
                            for idx in choice:
                                if 0 <= idx < len(poll["counts"]):
                                    poll["counts"][idx] += 1
                    else:
                        idx = int(choice)
                        if 0 <= idx < len(poll["counts"]):
                            poll["counts"][idx] += 1
                except Exception:
                    continue
            _save_json(POLL_FILE, self._polls)
        try:
            chan = None
            if poll.get("channel_id"):
                chan = self.bot.get_channel(int(poll["channel_id"]))
                if not chan:
                    try:
                        chan = await self.bot.fetch_channel(int(poll["channel_id"]))
                    except Exception:
                        chan = None
            msg = None
            if chan and poll.get("message_id"):
                try:
                    msg = await chan.fetch_message(int(poll["message_id"]))
                except Exception:
                    msg = None
            if msg:
                new_embed = await self._build_poll_embed(poll)
                try:
                    await msg.edit(embed=new_embed)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            await interaction.response.send_message("投票已记录。", ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send("投票已记录。", ephemeral=True)
            except Exception:
                pass
        log("INFO", "POLL", f"vote poll={poll_id} user={interaction.user.id} opt={opt_idx} multi={poll.get('multi')}")

    async def _schedule_close_task(self, poll_id: str, expires_dt: datetime):
        try:
            now = datetime.utcnow()
            delta = (expires_dt - now).total_seconds()
            if delta > 0:
                await asyncio.sleep(delta)
            await self.close_poll(poll_id, closed_by=None)
        except asyncio.CancelledError:
            return
        except Exception as e:
            log_exception("ERROR", "POLL", f"schedule_close_task 异常 poll={poll_id}", exc=e)

    async def close_poll(self, poll_id: str, closed_by: Optional[int] = None):
        poll = self._polls.get(poll_id)
        if not poll:
            return
        if poll.get("closed"):
            return
        poll["closed"] = True
        poll["closed_by"] = closed_by
        poll["closed_ts"] = datetime.utcnow().isoformat()
        _save_json(POLL_FILE, self._polls)
        try:
            chan = None
            if poll.get("channel_id"):
                chan = self.bot.get_channel(int(poll["channel_id"]))
                if not chan:
                    try:
                        chan = await self.bot.fetch_channel(int(poll["channel_id"]))
                    except Exception:
                        chan = None
            if chan and poll.get("message_id"):
                try:
                    msg = await chan.fetch_message(int(poll["message_id"]))
                    final = await self._build_poll_embed(poll)
                    final.add_field(name="状态", value="投票已结束", inline=False)
                    view = discord.ui.View()
                    for i, opt in enumerate(poll.get("options", [])):
                        b = discord.ui.Button(label=str(opt), style=discord.ButtonStyle.secondary, disabled=True)
                        view.add_item(b)
                    close_btn = discord.ui.Button(label="Closed", style=discord.ButtonStyle.danger, disabled=True)
                    view.add_item(close_btn)
                    try:
                        await msg.edit(embed=final, view=view)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass
        t = self._tasks.pop(poll_id, None)
        if t:
            try:
                t.cancel()
            except Exception:
                pass
        log("INFO", "POLL", f"poll closed {poll_id} closed_by={closed_by}")

    # ---------------------------
    # Profile command
    # ---------------------------
    @tools.command(name="profile", description="显示用户资料并保存快照（为空则显示自己）")
    @app_commands.describe(target="要查询的用户（可选，不填则为自己）")
    async def profile(self, interaction: discord.Interaction, target: Optional[discord.User] = None):
        user = target or interaction.user
        try:
            member = None
            if interaction.guild:
                try:
                    member = interaction.guild.get_member(user.id)
                    if member is None:
                        try:
                            member = await interaction.guild.fetch_member(user.id)
                        except Exception:
                            member = None
                except Exception:
                    member = None
            embed = discord.Embed(title=f"User Profile — {user}", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.set_thumbnail(url=user.display_avatar.url if getattr(user, "display_avatar", None) else (user.avatar.url if getattr(user, "avatar", None) else None))
            embed.add_field(name="用户名", value=f"{user}", inline=True)
            embed.add_field(name="用户 ID", value=str(user.id), inline=True)
            created = getattr(user, "created_at", None)
            embed.add_field(name="创建于", value=str(created) if created else "未知", inline=True)
            if member:
                joined = getattr(member, "joined_at", None)
                embed.add_field(name="加入本服务器", value=str(joined) if joined else "未知", inline=True)
                try:
                    roles = [r.name for r in member.roles if r.name != "@everyone"]
                    if roles:
                        embed.add_field(name=f"角色 ({len(roles)})", value=", ".join(roles[:10]), inline=False)
                except Exception:
                    pass
            embed.add_field(name="机器人帐户", value="是" if getattr(user, "bot", False) else "否", inline=True)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=False)
            except Exception:
                try:
                    await interaction.followup.send(embed=embed, ephemeral=False)
                except Exception:
                    pass
            snapshot = {
                "id": str(user.id),
                "display_name": str(user),
                "created_at": created.isoformat() if created else None,
                "queried_at": datetime.utcnow().isoformat(),
                "queried_by": str(interaction.user.id),
            }
            if member:
                snapshot["joined_at"] = member.joined_at.isoformat() if member.joined_at else None
                try:
                    snapshot["roles"] = [r.name for r in member.roles if r.name != "@everyone"]
                except Exception:
                    snapshot["roles"] = []
            else:
                snapshot["roles"] = []
            self._profiles[str(user.id)] = snapshot
            _save_json(PROFILE_FILE, self._profiles)
            log("INFO", "TOOLS", f"profile saved for user={user.id} by {interaction.user.id}")
        except Exception as e:
            log_exception("ERROR", "TOOLS", "profile 命令失败", exc=e)
            try:
                await interaction.response.send_message("查询用户资料时出错。", ephemeral=True)
            except Exception:
                pass

    # ---------------------------
    # Join/Leave configuration commands
    # ---------------------------
    def _is_guild_admin(self, member: discord.Member) -> bool:
        """Require administrator permission or BOT OWNER."""
        try:
            if _is_owner_user(member):
                return True
        except Exception:
            pass
        try:
            return bool(member.guild_permissions.administrator)
        except Exception:
            return False

    @tools.command(name="設定加入頻道", description="設定本伺服器的加入通知頻道（可選 channel，不填為當前頻道）")
    @app_commands.describe(channel="要設定為加入通知的頻道（留空則為本頻道）")
    async def set_join_channel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.guild:
            await interaction.response.send_message("此指令需在伺服器中使用。", ephemeral=True)
            return
        # permission: only guild admins (administrator) or BOT OWNER
        try:
            guild_member = interaction.guild.get_member(interaction.user.id) or await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            guild_member = None
        allowed = False
        if guild_member:
            allowed = self._is_guild_admin(guild_member)
        else:
            allowed = _is_owner_user(interaction.user)
        if not allowed:
            await interaction.response.send_message("你沒有權限執行此操作（需 伺服器 管理員 或 BOT OWNER）。", ephemeral=True)
            return
        ch = channel or interaction.channel
        if ch is None:
            await interaction.response.send_message("找不到頻道，請指定一個頻道或在頻道內執行此指令。", ephemeral=True)
            return
        self._joins[str(interaction.guild.id)] = ch.id
        _save_mapping(JOIN_FILE, self._joins)
        try:
            await interaction.response.send_message(f"已將本伺服器的加入通知頻道設定為 {ch.mention}。", ephemeral=False)
        except Exception:
            try:
                await interaction.followup.send(f"已將本伺服器的加入通知頻道設定為 <#{ch.id}>。", ephemeral=False)
            except Exception:
                pass
        log("INFO", "JOIN_LEAVE", f"Set join channel for guild={interaction.guild.id} -> {ch.id} by {interaction.user}")

    @tools.command(name="設定離開頻道", description="設定本伺服器的離開通知頻道（可選 channel，不填為本頻道）")
    @app_commands.describe(channel="要設定為離開通知的頻道（留空則為本頻道）")
    async def set_leave_channel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.guild:
            await interaction.response.send_message("此指令需在伺服器中使用。", ephemeral=True)
            return
        try:
            guild_member = interaction.guild.get_member(interaction.user.id) or await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            guild_member = None
        allowed = False
        if guild_member:
            allowed = self._is_guild_admin(guild_member)
        else:
            allowed = _is_owner_user(interaction.user)
        if not allowed:
            await interaction.response.send_message("你沒有權限執行此操作（需 伺服器 管理員 或 BOT OWNER）。", ephemeral=True)
            return
        ch = channel or interaction.channel
        if ch is None:
            await interaction.response.send_message("找不到頻道，請指定一個頻道或在頻道內執行此指令。", ephemeral=True)
            return
        self._leaves[str(interaction.guild.id)] = ch.id
        _save_mapping(LEAVE_FILE, self._leaves)
        try:
            await interaction.response.send_message(f"已將本伺服器的離開通知頻道設定為 {ch.mention}。", ephemeral=False)
        except Exception:
            try:
                await interaction.followup.send(f"已將本伺服器的離開通知頻道設定為 <#{ch.id}>。", ephemeral=False)
            except Exception:
                pass
        log("INFO", "JOIN_LEAVE", f"Set leave channel for guild={interaction.guild.id} -> {ch.id} by {interaction.user}")

    @tools.command(name="移除加入頻道", description="移除本伺服器的加入通知頻道（可選 channel，不填為本頻道）")
    @app_commands.describe(channel="要移除的頻道（留空則為本頻道）")
    async def remove_join_channel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.guild:
            await interaction.response.send_message("此指令需在伺服器中使用。", ephemeral=True)
            return
        try:
            guild_member = interaction.guild.get_member(interaction.user.id) or await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            guild_member = None
        allowed = False
        if guild_member:
            allowed = self._is_guild_admin(guild_member)
        else:
            allowed = _is_owner_user(interaction.user)
        if not allowed:
            await interaction.response.send_message("你沒有權限執行此操作（需 伺服器 管理員 或 BOT OWNER）。", ephemeral=True)
            return
        gid = str(interaction.guild.id)
        if gid not in self._joins:
            await interaction.response.send_message("伺服器尚未設定加入通知頻道。", ephemeral=True)
            return
        ch = channel or interaction.channel
        if channel and self._joins.get(gid) != ch.id:
            await interaction.response.send_message("指定頻道並非目前設定的加入通知頻道。", ephemeral=True)
            return
        self._joins.pop(gid, None)
        _save_mapping(JOIN_FILE, self._joins)
        try:
            await interaction.response.send_message("已移除本伺服器的加入通知頻道設定。", ephemeral=False)
        except Exception:
            try:
                await interaction.followup.send("已移除本伺服器的加入通知頻道設定。", ephemeral=False)
            except Exception:
                pass
        log("INFO", "JOIN_LEAVE", f"Removed join channel for guild={interaction.guild.id} by {interaction.user}")

    @tools.command(name="移除離開頻道", description="移除本伺服器的離開通知頻道（可選 channel，不填為本頻道）")
    @app_commands.describe(channel="要移除的頻道（留空則為本頻道）")
    async def remove_leave_channel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.guild:
            await interaction.response.send_message("此指令需在伺服器中使用。", ephemeral=True)
            return
        try:
            guild_member = interaction.guild.get_member(interaction.user.id) or await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            guild_member = None
        allowed = False
        if guild_member:
            allowed = self._is_guild_admin(guild_member)
        else:
            allowed = _is_owner_user(interaction.user)
        if not allowed:
            await interaction.response.send_message("你沒有權限執行此操作（需 伺服器 管理員 或 BOT OWNER）。", ephemeral=True)
            return
        gid = str(interaction.guild.id)
        if gid not in self._leaves:
            await interaction.response.send_message("伺服器尚未設定離開通知頻道。", ephemeral=True)
            return
        ch = channel or interaction.channel
        if channel and self._leaves.get(gid) != ch.id:
            await interaction.response.send_message("指定頻道並非目前設定的離開通知頻道。", ephemeral=True)
            return
        self._leaves.pop(gid, None)
        _save_mapping(LEAVE_FILE, self._leaves)
        try:
            await interaction.response.send_message("已移除本伺服器的離開通知頻道設定。", ephemeral=False)
        except Exception:
            try:
                await interaction.followup.send("已移除本伺服器的離開通知頻道設定。", ephemeral=False)
            except Exception:
                pass
        log("INFO", "JOIN_LEAVE", f"Removed leave channel for guild={interaction.guild.id} by {interaction.user}")

    @tools.command(name="查看所有設定的頻道", description="（僅 OWNER）查看所有伺服器的加入/離開頻道設定")
    async def view_all_mappings(self, interaction: discord.Interaction):
        if not _is_owner_user(interaction.user):
            await interaction.response.send_message("只有 OWNER 可以使用此指令。", ephemeral=True)
            return
        join_map = self._joins
        leave_map = self._leaves
        gids = set(list(join_map.keys()) + list(leave_map.keys()))
        if not gids:
            await interaction.response.send_message("目前沒有任何伺服器設定加入/離開頻道。", ephemeral=False)
            return
        lines = []
        for gid in sorted(gids, key=lambda x: int(x)):
            j = join_map.get(gid)
            l = leave_map.get(gid)
            try:
                gobj = self.bot.get_guild(int(gid))
                gname = gobj.name if gobj else f"Guild {gid}"
            except Exception:
                gname = f"Guild {gid}"
            jtxt = f"<#{j}> (`{j}`)" if j else "未設定"
            ltxt = f"<#{l}> (`{l}`)" if l else "未設定"
            lines.append(f"**{gname}** ({gid})\n- 加入: {jtxt}\n- 離開: {ltxt}")
        embed = discord.Embed(title="加入/離開頻道設定總表", description="\n\n".join(lines), color=discord.Color.blurple(), timestamp=datetime.utcnow())
        await interaction.response.send_message(embed=embed, ephemeral=False)
        log("INFO", "JOIN_LEAVE", f"Owner viewed all join/leave mappings by {interaction.user}")

    # ---------------------------
    # Event listeners: join / leave
    # ---------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            gid = str(member.guild.id)
            ch_id = self._joins.get(gid)
            if not ch_id:
                return
            ch = member.guild.get_channel(ch_id)
            if not ch:
                try:
                    ch = await member.guild.fetch_channel(ch_id)
                except Exception:
                    ch = None
            if not ch:
                self._joins.pop(gid, None)
                _save_mapping(JOIN_FILE, self._joins)
                log("WARN", "JOIN_LEAVE", f"Join channel not found for guild={gid}, mapping removed")
                return
            embed = discord.Embed(title="🎉 歡迎新成員", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="使用者", value=f"{member.mention}\n`{member.id}`", inline=False)
            embed.add_field(name="伺服器", value=f"{member.guild.name}", inline=True)
            embed.add_field(name="時間", value=datetime.utcnow().isoformat(), inline=True)
            embed.set_thumbnail(url=member.display_avatar.url if getattr(member, "display_avatar", None) else None)
            try:
                await ch.send(embed=embed)
            except Exception as e:
                log_exception("ERROR", "JOIN_LEAVE", "發送加入訊息失敗", exc=e)
        except Exception as e:
            log_exception("ERROR", "JOIN_LEAVE", "on_member_join 處理例外", exc=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            gid = str(member.guild.id)
            ch_id = self._leaves.get(gid)
            if not ch_id:
                return
            ch = member.guild.get_channel(ch_id)
            if not ch:
                try:
                    ch = await member.guild.fetch_channel(ch_id)
                except Exception:
                    ch = None
            if not ch:
                self._leaves.pop(gid, None)
                _save_mapping(LEAVE_FILE, self._leaves)
                log("WARN", "JOIN_LEAVE", f"Leave channel not found for guild={gid}, mapping removed")
                return
            embed = discord.Embed(title="👋 成員已離開", color=discord.Color.orange(), timestamp=datetime.utcnow())
            embed.add_field(name="使用者", value=f"{member}", inline=False)
            embed.add_field(name="用戶 ID", value=f"`{member.id}`", inline=True)
            embed.add_field(name="時間", value=datetime.utcnow().isoformat(), inline=True)
            try:
                await ch.send(embed=embed)
            except Exception as e:
                log_exception("ERROR", "JOIN_LEAVE", "發送離開訊息失敗", exc=e)
        except Exception as e:
            log_exception("ERROR", "JOIN_LEAVE", "on_member_remove 處理例外", exc=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(ToolsCommands(bot))