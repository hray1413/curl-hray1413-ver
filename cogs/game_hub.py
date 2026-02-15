from __future__ import annotations

import asyncio
import json
import random
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------
# Persistence & Safety
# ---------------------------
DATA_GAME_DIR = Path("data") / "game"
SCORES_FILE = DATA_GAME_DIR / "2048.json"
DATA_GAME_DIR.mkdir(parents=True, exist_ok=True)
file_lock = threading.Lock() # 防止多用戶同時寫入導致 JSON 損壞

def _load_scores() -> List[Dict[str, Any]]:
    try:
        if not SCORES_FILE.exists(): return []
        with SCORES_FILE.open("r", encoding="utf-8") as f:
            arr = json.load(f)
            return arr if isinstance(arr, list) else []
    except Exception:
        return []

def _save_score_record(record: Dict[str, Any]):
    """使用 Lock 確保線程安全的同步寫入"""
    with file_lock:
        try:
            scores = _load_scores()
            scores.append(record)
            with SCORES_FILE.open("w", encoding="utf-8") as f:
                json.dump(scores, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 存檔失敗: {e}")

# ---------------------------
# 2048 Game Logic (Optimized)
# ---------------------------
@dataclass
class GameState:
    board: List[List[int]] = field(default_factory=lambda: [[0]*4 for _ in range(4)])
    score: int = 0
    moves: int = 0
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def _rotate_90_clockwise(self, matrix: List[List[int]]) -> List[List[int]]:
        return [list(row) for row in zip(*matrix[::-1])]

    def _compress_and_merge_line(self, line: List[int]):
        new = [v for v in line if v != 0]
        res, gained, i = [], 0, 0
        while i < len(new):
            if i + 1 < len(new) and new[i] == new[i+1]:
                merged = new[i] * 2
                res.append(merged)
                gained += merged
                i += 2
            else:
                res.append(new[i])
                i += 1
        return res + [0] * (4 - len(res)), gained

    def move(self, direction: str) -> bool:
        """核心優化：統一旋轉矩陣處理所有方向"""
        rotations = {"left": 0, "up": 1, "right": 2, "down": 3}
        reverse_map = {0: 0, 1: 3, 2: 2, 3: 1}
        
        curr_board = deepcopy(self.board)
        for _ in range(rotations[direction]):
            curr_board = self._rotate_90_clockwise(curr_board)

        new_board, total_gain, changed = [], 0, False
        for r in range(4):
            new_line, gain = self._compress_and_merge_line(curr_board[r])
            if new_line != curr_board[r]: changed = True
            new_board.append(new_line)
            total_gain += gain

        if not changed: return False

        # 轉回原始方向
        for _ in range(reverse_map[rotations[direction]]):
            new_board = self._rotate_90_clockwise(new_board)

        self.board = new_board
        self.score += total_gain
        self.moves += 1
        return True

    def spawn_tile(self) -> bool:
        empties = [(r, c) for r in range(4) for c in range(4) if self.board[r][c] == 0]
        if not empties: return False
        r, c = random.choice(empties)
        self.board[r][c] = 4 if random.random() < 0.1 else 2
        return True

    def is_game_over(self) -> bool:
        for r in range(4):
            for c in range(4):
                if self.board[r][c] == 0: return False
                if c < 3 and self.board[r][c] == self.board[r][c+1]: return False
                if r < 3 and self.board[r][c] == self.board[r+1][c]: return False
        return True

    def board_as_text(self) -> str:
        return "\n".join(" ".join(str(n if n > 0 else ".").rjust(4) for n in row) for row in self.board)

# ---------------------------
# Discord UI (Unified)
# ---------------------------
class Game2048View(discord.ui.View):
    def __init__(self, parent_cog: GameHub, owner_id: int, state: GameState):
        super().__init__(timeout=300)
        self.parent_cog = parent_cog
        self.owner_id = owner_id
        self.state = state

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("這不是你的遊戲。", ephemeral=True)
            return False
        return True

    def _create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎮 2048",
            description=f"```\n{self.state.board_as_text()}\n```",
            color=discord.Color.green() if not self.state.is_game_over() else discord.Color.red()
        )
        embed.add_field(name="分數 / 步數", value=f"{self.state.score} / {self.state.moves}")
        if self.state.is_game_over():
            embed.add_field(name="結果", value="遊戲結束！", inline=False)
        return embed

    async def _handle_move(self, interaction: discord.Interaction, direction: str):
        if self.state.move(direction):
            self.state.spawn_tile()
            
        if self.state.is_game_over():
            for child in self.children: child.disabled = True
            await self.parent_cog._record_score(self.owner_id, self.state.score, self.state.moves, interaction)

        await interaction.response.edit_message(embed=self._create_embed(), view=self)

    @discord.ui.button(label="⬆️", style=discord.ButtonStyle.secondary)
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, "up")

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, "left")

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, "right")

    @discord.ui.button(label="⬇️", style=discord.ButtonStyle.secondary)
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, "down")

# ---------------------------
# Main Cog
# ---------------------------
class GameHub(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    遊戲 = app_commands.Group(name="游戲", description="小遊戲集合")

    @遊戲.command(name="2048", description="開始 2048")
    async def cmd_2048(self, interaction: discord.Interaction):
        state = GameState()
        state.spawn_tile()
        state.spawn_tile()
        view = Game2048View(self, interaction.user.id, state)
        await interaction.response.send_message(embed=view._create_embed(), view=view)

    async def _record_score(self, owner_id: int, score: int, moves: int, interaction: discord.Interaction):
        record = {
            "user_id": owner_id,
            "username": str(interaction.user),
            "score": score,
            "moves": moves,
            "ts": datetime.utcnow().isoformat()
        }
        # 在後台線程執行磁碟 I/O，不阻塞 Bot
        await asyncio.to_thread(_save_score_record, record)

async def setup(bot: commands.Bot):
    await bot.add_cog(GameHub(bot))