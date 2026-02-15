# --------------------
# 修正後的 `cogs/music.py` 完整程式碼 (由 hray1413 優化版)
# --------------------
import os
import discord
import wavelink
import typing
from discord.ext import commands
from discord import app_commands, Interaction
from typing import cast 

# --- 修正點：動態導入 TrackEndEvent ---
try:
    from wavelink.events import TrackEndEvent
except ImportError:
    try:
        from wavelink import TrackEndEvent
    except ImportError:
        class TrackEndEvent: pass
        print("WARN: 無法從 wavelink 模組找到 TrackEndEvent，請檢查 Wavelink 版本。")

# 輔助 logger 函數
try:
    from utils.logger import log, log_exception
except ImportError:
    def log(level, source, message): print(f"[{level}][{source}] {message}")
    def log_exception(level, source, message, exc=None): print(f"[{level}][{source}] {message}: {exc}")

LAVALINK_HOST = os.getenv("LAVALINK_HOST", "140.238.179.182") 
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333)) 
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "kirito") 

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # ⚠️ 這是最關鍵的一行，解決 AttributeError: 'Music' object has no attribute 'bot'
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """當 Bot 準備好時，進行 Lavalink 連接。"""
        log("INFO", "WAVELINK", "Bot 準備就緒，檢查 Lavalink 連線狀態...")
        # Wavelink 3.x 檢查節點池是否為空
        if not wavelink.Pool.nodes:
            await self.connect_nodes()
        else:
            log("INFO", "WAVELINK", "Lavalink 節點池已存在，跳過重複連接。")

    async def connect_nodes(self):
        """初始化 Wavelink 節點連接。"""
        await self.bot.wait_until_ready() 
        
        # Wavelink 3.x 建議格式：不需要 http:// 且 identifier 為選填
        node = wavelink.Node(
            uri=f"{LAVALINK_HOST}:{LAVALINK_PORT}", 
            password=LAVALINK_PASSWORD,
            inactive_player_timeout=300
        )
        try:
            # client=self.bot 確保 Cog 與主程式 Bot 實體連動
            await wavelink.Pool.connect(client=self.bot, nodes=[node], cache_states=True)
            log("INFO", "WAVELINK", f"✅ Lavalink 節點連接成功！Host: {LAVALINK_HOST}")
        except Exception as e:
            log_exception("ERROR", "WAVELINK", "❌ Lavalink 連接失敗", exc=e)

    @commands.Cog.listener() 
    async def on_wavelink_track_end(self, payload: TrackEndEvent):
        """處理歌曲結束，自動播放隊列中的下一首。"""
        if not payload.player: 
            return
            
        player: wavelink.Player = payload.player
        
        # 自動播放邏輯
        if not player.queue.is_empty:
            next_track = player.queue.get()
            try:
                await player.play(next_track)
                log("INFO", "WAVELINK", f"自動播放下一首: {next_track.title}")
            except Exception as e:
                log_exception("ERROR", "WAVELINK", f"自動播放失敗: {next_track.title}", exc=e)

    # --- 輔助函數 ---
    
    async def get_player_or_connect(self, interaction: Interaction) -> wavelink.Player | None:
        await interaction.response.defer(ephemeral=True) 
        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("你需要先加入一個語音頻道！", ephemeral=True) 
                return None
            
            voice_channel = interaction.user.voice.channel
            try:
                # Wavelink 3.x 連接方式
                player = await voice_channel.connect(cls=wavelink.Player)
                await interaction.followup.send(f"✅ 已連接到 **`{voice_channel.name}`**。", ephemeral=False) 
            except Exception as e:
                await interaction.followup.send(f"❌ 無法連接到語音頻道: {e}", ephemeral=True)
                return None
        
        if interaction.user.voice and player.channel.id != interaction.user.voice.channel.id:
            await interaction.followup.send("請在我在的語音頻道中使用指令。", ephemeral=True)
            return None
        
        return player
        
    # --- 斜線指令 ---

    @app_commands.command(name="play", description="播放歌曲。")
    @app_commands.describe(search="歌曲名稱或 YouTube 連結")
    async def play_slash(self, interaction: Interaction, search: str):
        player = await self.get_player_or_connect(interaction)
        if not player: return 

        # Wavelink 3.x 搜尋語法
        tracks = await wavelink.Pool.fetch_tracks(search)
        if not tracks:
            return await interaction.followup.send(f"找不到關於 `{search}` 的歌曲。", ephemeral=True) 
            
        track = tracks[0]

        if player.playing:
            player.queue.put(track)
            await interaction.followup.send(f"🎵 已將 **`{track.title}`** 加入隊列！") 
        else:
            await player.play(track)
            await interaction.followup.send(f"🎶 正在播放: **`{track.title}`**") 

    @app_commands.command(name="skip", description="跳過當前歌曲。")
    async def skip_slash(self, interaction: Interaction):
        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player or not player.playing:
            return await interaction.response.send_message("目前沒有音樂在播放。", ephemeral=True)
        
        await player.stop() 
        await interaction.response.send_message("⏭️ 已跳過當前歌曲。") 

    @app_commands.command(name="stop", description="停止並斷開連接。")
    async def stop_slash(self, interaction: Interaction):
        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player:
            return await interaction.response.send_message("我不在語音頻道中。", ephemeral=True)

        player.queue.clear()
        await player.disconnect()
        await interaction.response.send_message("✅ 已停止並斷開連接。")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))