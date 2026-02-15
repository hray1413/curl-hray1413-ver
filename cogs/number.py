import discord
from discord.ext import commands
from discord import app_commands, Webhook
import aiohttp
import json
import os
import asyncio
import typing

# --- 設定：儲存遊戲狀態的檔案路徑 ---
STATE_FILE = 'number_relay_state.json'
# 使用您提供的 CONFIG_FILE 來儲存 Webhook 資訊
WEBHOOK_CONFIG_FILE = 'relay_webhooks.json' 

# 模擬您的日誌函式
def print_log(level, tag, message):
    timestamp = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] [{tag}] {message}")

# --- 輔助函式：載入與儲存遊戲狀態 ---

def load_game_state():
    """從檔案載入當前遊戲狀態，如果檔案不存在則返回預設狀態。"""
    default_state = {
        'current_number': 1,
        'last_user_id': None,
        # 'relay_channel_ids' 不再需要，因為 Webhook Config 已經包含了頻道資訊
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                return {**default_state, **state}
        except json.JSONDecodeError:
            print_log("ERROR", "RELAY_STATE", f"❌ 遊戲狀態檔案損壞，使用預設狀態。")
        except Exception as e:
            print_log("ERROR", "RELAY_STATE", f"❌ 載入遊戲狀態錯誤: {e}")
    return default_state

def save_game_state(state):
    """儲存當前遊戲狀態到檔案。"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        print_log("ERROR", "RELAY_STATE", f"❌ 儲存遊戲狀態失敗: {e}")

# --- Cogs 插件本體 ---

class NumberRelay(commands.Cog, name="NumberRelay"):
    """跨群數字接龍遊戲插件 (基於 Webhook 廣播)"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 遊戲狀態鎖 (保證文件讀寫的原子性)
        self.game_state_lock = asyncio.Lock()
        
        # 遊戲狀態會在每次鎖定後讀取，此處僅作為初始化檢查
        self.game_state = load_game_state() 
        
        # Webhook 橋樑配置
        self.relay_webhooks: typing.Dict[str, str] = {} # {channel_id: webhook_url}
        
        # 設置 aiohttp session
        if not hasattr(bot, 'session'):
            self.session = aiohttp.ClientSession()
        else:
            self.session = bot.session
            
        self._load_webhook_config()

    def _load_webhook_config(self):
        """從 JSON 檔案載入 Webhook URL 配置。"""
        if os.path.exists(WEBHOOK_CONFIG_FILE):
            with open(WEBHOOK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                try:
                    self.relay_webhooks = json.load(f)
                    print_log("INFO", "RELAY_HOOK", f"✅ 已載入 {len(self.relay_webhooks)} 個接龍 Webhook。")
                except json.JSONDecodeError:
                    print_log("ERROR", "RELAY_HOOK", "❌ Webhook 配置檔案損壞，已重置為空。")
                    self.relay_webhooks = {}
                except Exception as e:
                     print_log("ERROR", "RELAY_HOOK", f"❌ 載入 Webhook 配置時發生未知錯誤: {e}")
        else:
            print_log("INFO", "RELAY_HOOK", "ℹ️ 未找到 Webhook 配置檔案，將創建新檔案。")
            self._save_webhook_config()

    def _save_webhook_config(self):
        """將當前 Webhook 配置儲存到 JSON 檔案。"""
        try:
            with open(WEBHOOK_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.relay_webhooks, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print_log("ERROR", "RELAY_HOOK", f"❌ 儲存 Webhook 配置檔案失敗: {e}")

    # --- Webhook 廣播機制 ---

    async def broadcast_relay_status(self, message: discord.Message, status_type: str, next_number: int, error_message: str = None):
        """
        使用 Webhook 將遊戲狀態廣播給所有橋樑頻道。
        
        Args:
            message: 觸發事件的原始訊息對象。
            status_type: 'SUCCESS', 'ERROR_RESET', 'MANUAL_RESET'。
            next_number: 下一個目標數字。
            error_message: 錯誤時的額外訊息。
        """
        source_channel_id = str(message.channel.id)
        source_guild_name = message.guild.name
        
        embed = discord.Embed(timestamp=discord.utils.utcnow())

        if status_type == 'SUCCESS':
            embed.title = f"🎉 成功接龍！"
            embed.description = f"**{message.author.display_name}** 在 **[{source_guild_name}]** 接龍到 **{next_number - 1}**！\n下一位請接 **{next_number}**。"
            embed.color = discord.Color.green()
        
        elif status_type == 'ERROR_RESET':
            embed.title = "🚨 接龍失敗！遊戲重設！"
            embed.description = f"**{message.author.display_name}** 在 **[{source_guild_name}]** 犯規。\n{error_message}\n新的數字從 **{next_number}** 開始！"
            embed.color = discord.Color.red()
            
        elif status_type == 'MANUAL_RESET':
            embed.title = "💥 遊戲被手動重設！"
            embed.description = f"管理員在 **[{source_guild_name}]** 手動重設了遊戲。\n新的數字從 **{next_number}** 開始！"
            embed.color = discord.Color.orange()
            
        embed.set_footer(text=f"來源：{source_guild_name} | {message.author.name}", icon_url=message.author.display_avatar.url)

        # 遍歷所有 Webhook 進行廣播
        for target_id, webhook_url in self.relay_webhooks.items():
            if target_id == source_channel_id and status_type != 'MANUAL_RESET':
                continue # 避免在原頻道發送重複的成功訊息 (錯誤訊息需要單獨發送)

            try:
                webhook = Webhook.from_url(webhook_url, session=self.session)
                await webhook.send(embed=embed, username="數字接龍廣播", avatar_url=self.bot.user.display_avatar.url)
                print_log("DEBUG", "BROADCAST", f"✅ 成功廣播狀態到目標頻道 ID: {target_id}")
            except Exception as e:
                # 錯誤處理可以更詳細，但這裡保持簡潔
                print_log("ERROR", "BROADCAST", f"❌ 廣播失敗到 {target_id}: {type(e).__name__}")


    # --- 內部函式：重設遊戲 ---
    async def reset_game(self, initiator_message: discord.Message, manual: bool = False):
        """
        將遊戲重設到起始狀態 (數字 1)，並通知所有接龍頻道。
        """
        async with self.game_state_lock:
            # 確保在鎖定區間內修改狀態
            self.game_state['current_number'] = 1
            self.game_state['last_user_id'] = None
            save_game_state(self.game_state)

        # 通知原頻道 (如果是錯誤觸發)
        if not manual:
             await initiator_message.channel.send(
                f"🚨 **接龍失敗！** 遊戲重設！新的數字從 **1** 開始！",
                delete_after=15
             )

        # 廣播狀態
        await self.broadcast_relay_status(
            message=initiator_message,
            status_type='MANUAL_RESET' if manual else 'ERROR_RESET',
            next_number=1,
            error_message=f"正確數字應為 {self.game_state['current_number']}。"
        )

    # --- 權限檢查：所有管理指令都需要管理員權限 ---
    async def cog_check(self, interaction: discord.Interaction):
        if interaction.command:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ **錯誤：** 您必須是伺服器管理員才能使用此指令。", ephemeral=True)
                return False
        return True

    # --- Slash Command 1: 重設遊戲 ---
    @app_commands.command(name='relay_reset', description='[管理員] 重設數字接龍遊戲到 1。')
    async def relay_reset_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # 創建一個 Message 對象來模擬，用於 broadcast
        mock_message = interaction.message or await interaction.original_response() 
        await self.reset_game(mock_message, manual=True)
        await interaction.followup.send(f"✅ 數字接龍已重設。當前目標數字：**1**。", ephemeral=True)


    # --- Slash Command 2: 設定接龍頻道 (創建 Webhook) ---
    @app_commands.command(name="setrelaychannel", description="[管理員] 設定本頻道為數字接龍橋樑。")
    @app_commands.default_permissions(manage_channels=True)
    async def set_relay_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        channel_id_str = str(channel.id)

        if channel_id_str in self.relay_webhooks:
            return await interaction.followup.send("⚠️ 此頻道已設定為接龍橋樑。", ephemeral=True)

        try:
            webhook_name = f"RelayHook-{channel.guild.name[:20]}"
            webhook = await channel.create_webhook(name=webhook_name, reason="設立數字接龍廣播橋樑")
            webhook_url = webhook.url
        except discord.Forbidden:
            return await interaction.followup.send("❌ 權限不足：Bot 需要有 '管理 Webhook' 的權限。", ephemeral=True)
        except Exception as e:
            print_log("ERROR", "RELAY_HOOK", f"創建 Webhook 失敗: {e}")
            return await interaction.followup.send(f"❌ 創建 Webhook 失敗: {e}", ephemeral=True)
        
        self.relay_webhooks[channel_id_str] = webhook_url
        self._save_webhook_config()

        await interaction.followup.send(f"✅ 頻道 **{channel.name}** 已成功設定為數字接龍廣播橋樑。", ephemeral=True)
        print_log("INFO", "RELAY_HOOK", f"✅ 頻道 '{channel.name}' (ID: {channel_id_str}) 已設定橋樑。")

    # --- Slash Command 3: 移除接龍頻道 ---
    @app_commands.command(name='removerelaychannel', description='[管理員] 移除本頻道的數字接龍橋樑設定。')
    @app_commands.default_permissions(manage_channels=True)
    async def remove_relay_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        channel_id_str = str(channel.id)

        if channel_id_str not in self.relay_webhooks:
            return await interaction.followup.send("⚠️ 此頻道未設定為接龍橋樑。", ephemeral=True)
        
        webhook_url = self.relay_webhooks.pop(channel_id_str)
        try:
            webhook = Webhook.from_url(webhook_url, session=self.session)
            await webhook.delete(reason="移除數字接龍橋樑")
        except (discord.NotFound, discord.Forbidden):
            print_log("WARN", "RELAY_HOOK", f"無法刪除 Webhook (ID: {channel_id_str})，可能已被手動刪除。")
        except Exception as e:
            print_log("ERROR", "RELAY_HOOK", f"刪除 Webhook 時發生未知錯誤: {e}")

        self._save_webhook_config()

        await interaction.followup.send(f"✅ 頻道 **{channel.name}** 已移除接龍橋樑設定。", ephemeral=True)
        print_log("INFO", "RELAY_HOOK", f"✅ 頻道 '{channel.name}' (ID: {channel_id_str}) 已移除橋樑。")


    # --- 事件監聽: 處理所有訊息 (核心邏輯) ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 1. 過濾基礎訊息
        if message.author.bot or message.interaction or message.type != discord.MessageType.default:
            return

        source_channel_id = str(message.channel.id)
        
        # 2. 檢查是否為接龍頻道
        if source_channel_id not in self.relay_webhooks:
            return

        # 3. 嘗試解析訊息內容
        try:
            sent_number = int(message.content.strip())
        except ValueError:
            return # 非純數字訊息，忽略

        # --- 核心邏輯判斷 (使用鎖定保證同步) ---
        async with self.game_state_lock:
            # 在鎖定區間內，讀取最新的狀態 (防止檔案讀寫延遲)
            self.game_state = load_game_state() 
            expected_number = self.game_state['current_number']
            
            # A. 防連發檢查
            if message.author.id == self.game_state['last_user_id']:
                try: await message.delete() 
                except: pass
                await message.channel.send(
                    f"❌ **{message.author.display_name}**，你不能連續發送兩次！當前目標數字仍是 **{expected_number}**。",
                    delete_after=10
                )
                # 保持鎖定，不進行任何狀態修改，直接結束
                return

            # B. 數字檢查: 成功接龍
            if sent_number == expected_number:
                
                # 更新狀態 (在記憶體中)
                self.game_state['current_number'] += 1
                self.game_state['last_user_id'] = message.author.id
                
                # 立即儲存狀態 (寫入檔案)
                save_game_state(self.game_state) 

                # 釋放鎖定，然後進行廣播
                
            else:
                # C. 錯誤時直接重來 (重設遊戲)
                
                # 1. 刪除錯誤訊息
                try: await message.delete() 
                except: pass
                     
                # 2. 宣佈錯誤並重設遊戲 (在鎖定區間內重設)
                self.game_state['current_number'] = 1
                self.game_state['last_user_id'] = None
                save_game_state(self.game_state)
                
                # 釋放鎖定，然後進行廣播
                
            
        # --- 鎖定區間結束，進行廣播 ---
        
        if sent_number == expected_number:
            # 成功廣播
            await self.broadcast_relay_status(
                message=message,
                status_type='SUCCESS',
                next_number=self.game_state['current_number']
            )
            print_log("INFO", "RELAY_GAME", f"SUCCESS: {message.author.name} 接龍到 {expected_number}. 下一數字: {self.game_state['current_number']}")
            
        else:
            # 失敗廣播
            await message.channel.send(
                f"🚨 **接龍失敗！** **{message.author.display_name}** 傳送了 `{sent_number}`，但正確的數字是 **{expected_number}**。\n💥 **遊戲重設！** 新的數字從 **1** 開始！",
                delete_after=15
            )
            await self.broadcast_relay_status(
                message=message,
                status_type='ERROR_RESET',
                next_number=1,
                error_message=f"預期數字是 **{expected_number}**，實際收到 **{sent_number}**。"
            )
            print_log("INFO", "RELAY_GAME", f"FAIL: {message.author.name} (Expected {expected_number}, Got {sent_number}). Game Reset.")
            

async def setup(bot):
    """Discord.py 載入 Cogs 的標準函式。"""
    await bot.add_cog(NumberRelay(bot))