import discord
from discord.ext import commands
from discord import app_commands, Webhook
import aiohttp
import json
import os
import asyncio
import typing

# --- 配置設定 ---
CONFIG_FILE = 'bridge_webhooks.json' 

# 模擬您的日誌函式
def print_log(level, tag, message):
    timestamp = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    # 注意：這裡使用 print() 模擬日誌輸出到終端機
    print(f"[{timestamp}] [{level}] [{tag}] {message}")

class CrossChatBridge(commands.Cog, name="CrossChatBridge"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bridge_webhooks: typing.Dict[str, str] = {} # {channel_id: webhook_url}
        if not hasattr(bot, 'session'):
            self.session = aiohttp.ClientSession()
        else:
            self.session = bot.session
            
        self._load_config()

    def cog_unload(self):
        """Cog 卸載時關閉 session (如果它是 Cog 內部創建的)"""
        if not hasattr(self.bot, 'session'):
             print_log("INFO", "Bridge", "Cog 正在卸載，關閉內建 aiohttp session。")
             asyncio.create_task(self.session.close())
    
    # --- 配置載入與儲存 ---

    def _load_config(self):
        """從 JSON 檔案載入 Webhook URL 配置。"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                try:
                    self.bridge_webhooks = json.load(f)
                    print_log("INFO", "Bridge", f"✅ 已載入 {len(self.bridge_webhooks)} 個橋接 Webhook。")
                except json.JSONDecodeError:
                    print_log("ERROR", "Bridge", "❌ Webhook 配置檔案損壞，已重置為空。")
                    self.bridge_webhooks = {}
        else:
            print_log("INFO", "Bridge", "ℹ️ 未找到 Webhook 配置檔案，將創建新檔案。")
            self._save_config()

    def _save_config(self):
        """將當前配置儲存到 JSON 檔案。"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bridge_webhooks, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print_log("ERROR", "Bridge", f"❌ 儲存配置檔案失敗: {e}")

    # --- 斜線指令 ---

    @app_commands.command(name="setbridge", description="將本頻道設定為跨群聊天的橋樑。")
    @app_commands.default_permissions(manage_channels=True)
    async def set_bridge(self, interaction: discord.Interaction):
        channel = interaction.channel
        
        channel_id_str = str(channel.id)
        if channel_id_str in self.bridge_webhooks:
            return await interaction.response.send_message("⚠️ 此頻道已設定為橋樑。", ephemeral=True)

        try:
            webhook_name = f"CrossChat-{channel.guild.name[:20]}"
            webhook = await channel.create_webhook(name=webhook_name, reason="設立跨群聊天橋樑")
            webhook_url = webhook.url
        except discord.Forbidden:
            return await interaction.response.send_message("❌ 權限不足：Bot 需要有 '管理 Webhook' 的權限。", ephemeral=True)
        except Exception as e:
            print_log("ERROR", "Bridge", f"創建 Webhook 失敗: {e}")
            return await interaction.response.send_message(f"❌ 創建 Webhook 失敗: {e}", ephemeral=True)
        
        self.bridge_webhooks[channel_id_str] = webhook_url
        self._save_config()

        await interaction.response.send_message(f"✅ 頻道 **{channel.name}** 已成功設定為跨群聊天橋樑。", ephemeral=True)
        print_log("INFO", "Bridge", f"✅ 頻道 '{channel.name}' (ID: {channel_id_str}) 已設定橋樑。")

    @app_commands.command(name="removebridge", description="移除本頻道的跨群聊天橋樑設定。")
    @app_commands.default_permissions(manage_channels=True)
    async def remove_bridge(self, interaction: discord.Interaction):
        channel = interaction.channel
        channel_id_str = str(channel.id)

        if channel_id_str not in self.bridge_webhooks:
            return await interaction.response.send_message("⚠️ 此頻道未設定為橋樑。", ephemeral=True)
        
        webhook_url = self.bridge_webhooks.pop(channel_id_str)
        try:
            webhook = Webhook.from_url(webhook_url, session=self.session)
            await webhook.delete(reason="移除跨群聊天橋樑")
        except (discord.NotFound, discord.Forbidden):
            print_log("WARN", "Bridge", f"無法刪除 Webhook (ID: {channel_id_str})，可能已被手動刪除或權限不足。")
        except Exception as e:
            print_log("ERROR", "Bridge", f"刪除 Webhook 時發生未知錯誤: {e}")

        self._save_config()

        await interaction.response.send_message(f"✅ 頻道 **{channel.name}** 已移除跨群聊天橋樑設定。", ephemeral=True)
        print_log("INFO", "Bridge", f"✅ 頻道 '{channel.name}' (ID: {channel_id_str}) 已移除橋樑。")

    # --- 訊息監聽器 (核心功能) ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽所有訊息，將來自橋接頻道的訊息轉發給其他所有橋接頻道。"""
        
        # [第 1 級過濾] 忽略 Bot 自己的訊息、指令、系統訊息
        if message.author.bot or message.interaction or message.type != discord.MessageType.default:
            return

        source_channel_id = str(message.channel.id)
        
        # [第 2 級過濾] 檢查是否來自橋接頻道
        if source_channel_id not in self.bridge_webhooks:
            return
            
        print_log("DEBUG", "BRIDGE", f"--- 🌉 收到來自橋接頻道 '{message.channel.name}' 的訊息，準備轉發 ---")

        # [第 3 級準備] 構造 Webhook 內容和 Embed
        
        content = message.content
        embed = None # 用於回覆訊息的 Embed

        # --- 新增回覆訊息處理邏輯 ---
        if message.reference and message.reference.message_id:
            try:
                # 嘗試獲取被回覆的訊息
                replied_message = await message.channel.fetch_message(message.reference.message_id)
                replied_author = replied_message.author
                
                # 處理被回覆訊息的內容 (如果內容是空字串，可能是附件或 Embed)
                replied_content = replied_message.content 
                if not replied_content:
                    if replied_message.attachments:
                        replied_content = f"*[附件 x{len(replied_message.attachments)}]*"
                    elif replied_message.embeds:
                        replied_content = f"*[Embed x{len(replied_message.embeds)}]*"
                    else:
                        replied_content = "*[無文字內容]*"

                # 創建 Embed 來模擬回覆
                # 使用 Discord Blockquote 格式來顯示被回覆的內容，限制長度
                embed = discord.Embed(
                    description=f"> {replied_content[:100]}{'...' if len(replied_content) > 100 else ''}",
                    color=discord.Color.blue()
                )
                # 設定 Embed 欄位顯示被回覆者
                embed.set_author(
                    name=f"回覆 {replied_author.display_name}",
                    icon_url=replied_author.display_avatar.url if replied_author.display_avatar else None
                )
            except discord.NotFound:
                # 訊息可能已被刪除
                embed = discord.Embed(
                    description="> *[原訊息已刪除]*",
                    color=discord.Color.dark_grey()
                )
                embed.set_author(name="回覆一條已刪除的訊息")
            except Exception as e:
                print_log("ERROR", "BRIDGE", f"--- ❌ 獲取回覆訊息時出錯: {e} ---")
                
        # 處理附件：將附件 URL 附加到內容中
        if message.attachments:
            attachment_urls = [att.url for att in message.attachments]
            attachment_text = "\n" + "\n".join(attachment_urls)
            content = (content or "") + attachment_text
            
        # 最終檢查內容是否為空 (純回覆/純附件/純Embed 應能通過)
        if not content and not embed:
             print_log("WARN", "BRIDGE", f"--- ⚠️ 訊息內容和附件均為空，忽略轉發 ---")
             return
            
        avatar_url = message.author.display_avatar.url if message.author.display_avatar else None
        guild_name = message.guild.name
        webhook_username = f"[{guild_name}] {message.author.display_name}"
        
        # [第 4 級轉發] 遍歷所有目標 Webhook URL
        
        target_webhooks = list(self.bridge_webhooks.items())
        
        if len(target_webhooks) <= 1:
            print_log("WARN", "BRIDGE", "--- ⚠️ 橋樑設定不足，無法轉發 (只有一個或零個目標) ---")
            return
            
        for target_id, webhook_url in target_webhooks:
            if target_id == source_channel_id:
                continue

            try:
                webhook = Webhook.from_url(webhook_url, session=self.session)
                
                await webhook.send(
                    content=content,
                    username=webhook_username,
                    avatar_url=avatar_url,
                    embed=embed if embed else discord.utils.MISSING,
                    allowed_mentions=discord.AllowedMentions.all() 
                )
                print_log("DEBUG", "BRIDGE", f"--- ✅ 成功轉發到目標頻道 ID: {target_id} ---")

            except discord.Forbidden:
                print_log("ERROR", "BRIDGE", f"--- ❌ 轉發失敗: Discord 拒絕 (Forbidden)。目標 Webhook 權限不足。目標 ID: {target_id} ---")
            except discord.NotFound:
                print_log("ERROR", "BRIDGE", f"--- ❌ 轉發失敗: Webhook 找不到 (NotFound)。目標 Webhook 已被刪除。目標 ID: {target_id} ---")
            except Exception as e:
                print_log("ERROR", "BRIDGE", f"--- ❌ 轉發發生未知錯誤: {type(e).__name__}: {e}。目標 ID: {target_id} ---")


async def setup(bot):
    await bot.add_cog(CrossChatBridge(bot))