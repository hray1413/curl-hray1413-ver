import os
import json
import traceback
from pathlib import Path
from datetime import datetime, timedelta

import discord
from discord.ext import commands

# 使用项目统一 logger（请确保 utils/logger.py 已存在）
from utils.logger import log, log_exception

class UsageLogger(commands.Cog):
    """
    使用记录 Cog：
    - 监听 slash command（application_command）交互
    - 将日志以纯文本格式发送到 .env 中配置的 LOG_CHANNEL_ID（如果机器人有权限）
    - 同时把交互信息以 JSONL 追加到本地 logs/usage.log
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id = None
        lc = os.getenv("LOG_CHANNEL_ID")
        if lc:
            try:
                self.log_channel_id = int(lc)
            except Exception:
                log("WARN", "其他", "[UsageLogger] LOG_CHANNEL_ID 无效，已忽略。")
        # 本地日志文件（确保项目根目录下存在 logs/）
        self._logs_dir = Path(__file__).parent.parent / "logs"
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._logs_dir / "usage.log"

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        监听 interaction 事件，记录 application_command 类型（Slash commands）。
        发送的文本格式（简体）:
        __指令使用__
        > 内容：<类似/hello那样，支持多行>
        > 使用者名称：`名称`
        > 使用者ID：
        > 服务器名称：`名称`
        > 服务器 ID：
        > 频道：
        > 日期（UTC+0800）：
        ————————————
        """
        try:
            # 仅记录 Slash commands（应用命令）
            if interaction.type is not discord.InteractionType.application_command:
                return

            user = interaction.user
            guild = interaction.guild
            channel = interaction.channel

            # 获取命令名与选项（兼容不同 discord.py 版本）
            data = getattr(interaction, "data", {}) or {}
            cmd_name = data.get("name") or getattr(interaction.command, "name", None) or "unknown"
            raw_options = data.get("options", [])

            def walk_opts(opts, prefix=""):
                rows = []
                for opt in (opts or []):
                    k = opt.get("name")
                    v = opt.get("value")
                    if v is None and opt.get("options"):
                        rows.append(f"{prefix}{k}:")
                        rows.extend(walk_opts(opt.get("options"), prefix=prefix + "  "))
                    else:
                        rows.append(f"{prefix}{k}: {v}")
                return rows

            options = walk_opts(raw_options)

            # 构造内容文本（支持多行）
            content_lines = [f"/{cmd_name}"]
            if options:
                content_lines.append("")  # 空行分隔
                content_lines.extend(options)
            content_text = "\n".join(content_lines) if content_lines else "（无内容）"

            # 将多行内容每行前加 '> '（引用样式）
            def quote_multiline(text: str) -> str:
                return "\n".join([("> " + line) for line in text.splitlines()]) if text else "> （无内容）"

            quoted_content = quote_multiline(content_text)

            # 使用者名称 name#discriminator
            uname = f"{user.name}#{user.discriminator}" if getattr(user, "discriminator", None) else f"{user}"

            # 日期：UTC+0800
            now_utc_plus8 = datetime.utcnow() + timedelta(hours=8)
            date_str = now_utc_plus8.strftime("%Y/%m/%d %H:%M:%S")

            # 频道信息
            channel_info = "N/A"
            try:
                if channel is not None:
                    ch_name = getattr(channel, "name", None)
                    ch_id = getattr(channel, "id", None)
                    if ch_name:
                        channel_info = f"{ch_name}"
                    elif ch_id:
                        channel_info = str(ch_id)
            except Exception:
                channel_info = "N/A"

            # 服务器信息
            guild_name = getattr(guild, "name", "N/A")
            guild_id = getattr(guild, "id", "N/A")

            # 组装最终文本，按照用户要求的格式（简体）
            lines = []
            lines.append("__指令使用__")
            lines.append(f"> 内容：")
            lines.append(quoted_content)
            lines.append(f"> 使用者名称：`{uname}`")
            lines.append(f"> 使用者ID：{user.id}")
            lines.append(f"> 服务器名称：`{guild_name}`")
            lines.append(f"> 服务器 ID：{guild_id}")
            lines.append(f"> 频道：{channel_info}")
            lines.append(f"> 日期（UTC+0800）：{date_str}")
            lines.append("————————————")
            final_text = "\n".join(lines)

            # 尝试发送到指定日志频道（如果配置了）
            if self.log_channel_id:
                try:
                    ch = self.bot.get_channel(self.log_channel_id)
                    if ch is None:
                        # fetch_channel 可能抛出 Forbidden（Missing Access），要捕获
                        try:
                            ch = await self.bot.fetch_channel(self.log_channel_id)
                        except discord.Forbidden:
                            log("ERR", "错误", f"[UsageLogger] 无法 fetch channel {self.log_channel_id}: Missing Access (403)")
                            ch = None
                        except Exception:
                            log_exception("ERROR", "错误", f"[UsageLogger] fetch_channel({self.log_channel_id}) 失败")
                            ch = None

                    if ch is None:
                        log("WARN", "其他", f"[UsageLogger] 找不到频道 ID {self.log_channel_id}（get_channel / fetch_channel 均失败）")
                    else:
                        # 如果频道属于 guild，检查机器人在该频道的权限
                        target_guild = getattr(ch, "guild", None)
                        if target_guild:
                            me = target_guild.me or target_guild.get_member(self.bot.user.id)
                            if me is None:
                                log("WARN", "其他", f"[UsageLogger] 无法取得在目标服务器的机器人成员对象 (guild_id={target_guild.id})")
                            else:
                                perms = ch.permissions_for(me)
                                if not perms.send_messages:
                                    log("ERR", "错误", f"[UsageLogger] 在频道 {ch.id} 没有发送权限，跳过")
                                    ch = None

                        # 若 ch 仍有效，则发送纯文本日志
                        if ch:
                            try:
                                # 如果消息过长，Discord 可能会抛出 HTTPException；捕获并记录
                                await ch.send(content=final_text)
                            except discord.Forbidden:
                                log("ERR", "错误", f"[UsageLogger] 发送到频道 {self.log_channel_id} 被拒绝 (Forbidden)")
                            except discord.HTTPException as e:
                                log_exception("ERROR", "错误", f"[UsageLogger] 发送到频道 {self.log_channel_id} HTTPException: {e}")
                            except Exception:
                                log_exception("ERROR", "错误", f"[UsageLogger] 发送到频道 {self.log_channel_id} 时发生未知错误")
                except Exception:
                    log_exception("ERROR", "错误", "[UsageLogger] 发送日志到频道时出错")
            else:
                # 没有配置频道，打印一条简短控制台记录（避免安静失败）
                log("INFO", "使用", f"{user} 在 {guild} 使用命令 /{cmd_name}")

            # 追加到本地日志文件（JSON 行格式，便于后续分析）
            try:
                j = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user.id,
                    "user_name": uname,
                    "guild_id": getattr(guild, "id", None),
                    "guild_name": getattr(guild, "name", None),
                    "channel_id": getattr(channel, "id", None),
                    "channel_name": getattr(channel, "name", None),
                    "command": cmd_name,
                    "options": options,
                }
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(j, ensure_ascii=False) + "\n")
            except Exception:
                log_exception("ERROR", "错误", "[UsageLogger] 写入本地日志文件时出错：")

        except Exception:
            log_exception("ERROR", "错误", "[UsageLogger] 处理 interaction 时发生未处理异常：")

# 扩展入口，确保 discord.py 可以 load_extension 成功
async def setup(bot: commands.Bot):
    await bot.add_cog(UsageLogger(bot))