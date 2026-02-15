"""
cogs/help_commands.py

/幫助 - 以 Embed 方式列出所有註冊的 Slash / 應用命令（對所有人可見）

使用說明：
- 將此文件保存為 cogs/help_commands.py（或放入你的 cogs 目錄），然後熱重載：
  await bot.reload_extension("cogs.help_commands")
- 在 Discord 中使用 /幫助，機器人會回覆一則公開的 Embed，列出目前註冊的所有 app commands 及其說明。
"""
from __future__ import annotations

from typing import List, Optional
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands


def _get_command_fullpath(cmd: app_commands.Command) -> str:
    # Construct full path including parent groups, e.g. "開發 重新加載_cogs"
    parts: List[str] = []
    cur = cmd
    # Walk up parents if any
    while cur is not None:
        # For Command and Group, .name exists
        try:
            parts.insert(0, cur.name)
        except Exception:
            parts.insert(0, getattr(cur, "name", str(cur)))
        cur = getattr(cur, "parent", None)
    # join with space after a leading slash
    return "/" + " ".join(parts)


class HelpCommands(commands.Cog):
    """顯示 bot 已註冊的命令列表（Embed）"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="幫助", description="顯示所有指令（以 Embed 方式）")
    async def help_cmd(self, interaction: discord.Interaction):
        """
        /幫助
        列出目前註冊的應用命令（Slash commands）及簡短說明，公開顯示（非 ephemeral）。
        """
        try:
            # gather commands from app command tree
            commands_list: List[app_commands.Command] = list(self.bot.tree.walk_commands())

            if not commands_list:
                await interaction.response.send_message("目前沒有可用的指令。", ephemeral=False)
                return

            # Build lines
            lines: List[str] = []
            for cmd in sorted(commands_list, key=lambda c: _get_command_fullpath(c).lower()):
                try:
                    path = _get_command_fullpath(cmd)
                    desc = cmd.description or "（無說明）"
                    # sanitize newlines in description
                    desc = desc.replace("\n", " ")
                    lines.append(f"**{path}** — {desc}")
                except Exception:
                    continue

            # If too long for a single embed description, split into multiple embeds
            MAX_DESC = 3500  # keep a margin under 4096
            embeds: List[discord.Embed] = []
            cur_lines: List[str] = []
            cur_len = 0
            for line in lines:
                l_len = len(line) + 1
                if cur_len + l_len > MAX_DESC and cur_lines:
                    emb = discord.Embed(
                        title="指令總覽",
                        description="\n".join(cur_lines),
                        color=discord.Color.blurple(),
                        timestamp=datetime.utcnow()
                    )
                    emb.set_footer(text="顯示中 - 機器人指令清單")
                    embeds.append(emb)
                    cur_lines = []
                    cur_len = 0
                cur_lines.append(line)
                cur_len += l_len
            # push remaining
            if cur_lines:
                emb = discord.Embed(
                    title="指令總覽",
                    description="\n".join(cur_lines),
                    color=discord.Color.blurple(),
                    timestamp=datetime.utcnow()
                )
                emb.set_footer(text="顯示中 - 機器人指令清單")
                embeds.append(emb)

            # send (publicly)
            # Use response.send_message for the first embed, then followups for the rest
            await interaction.response.send_message(embed=embeds[0], ephemeral=False)
            if len(embeds) > 1:
                msg = await interaction.original_response()
                for extra in embeds[1:]:
                    try:
                        await msg.reply(embed=extra)
                    except Exception:
                        try:
                            await interaction.followup.send(embed=extra)
                        except Exception:
                            pass
        except Exception as e:
            # Fallback error handling: try to send a short failure message publicly
            try:
                await interaction.response.send_message("生成指令清單時發生錯誤，請查看日誌。", ephemeral=False)
            except Exception:
                pass
            # Log if logger available
            try:
                from utils.logger import log_exception
                log_exception("ERROR", "HELP", "生成 /幫助 時發生錯誤", exc=e, interaction=interaction)
            except Exception:
                # last resort: print
                print("HELP command error:", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommands(bot))