import discord
from discord.ext import commands
from utils.logger import log, log_exception
import re

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 預設攔截清單 (可根據你遇到的 yaerak 等亂碼持續增加)
        self.blacklist_patterns = [
            r"^true$", r"^false$", r"^t$", r"^f$", 
            r"yaerak", r"yalayam", r"yaerak\d+"
        ]

    def is_bot_submission(self, content: str) -> bool:
        """檢查申請內容是否符合機器人特徵"""
        clean_content = content.strip().lower()
        
        # 1. 檢查精確關鍵字或正則表達式
        for pattern in self.blacklist_patterns:
            if re.search(pattern, clean_content):
                return True
        
        # 2. 檢查過短的無意義回答
        if len(clean_content) < 2:
            return True
            
        return False

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """偵測成員通過 Discord 內建規則篩選的瞬間"""
        # pending 為 True 表示還沒按下「同意規範」，當它轉為 False 時觸發
        if before.pending and not after.pending:
            log("INFO", "防護", f"偵測到新成員通過驗證: {after.name} ({after.id})")

            # 💡 註：在 Discord 內建篩選中，Bot 雖無法直接抓到「表單文字」
            # 但可以結合「帳號年齡」或「特定名字特徵」來執行自動化操作
            
            # 這裡我們先示範針對「疑似機器人特徵」的處置 (例如無頭像 + 剛註冊)
            if after.avatar is None and (discord.utils.utcnow() - after.created_at).days < 7:
                reason = "系統判定：帳號特徵符合自動化機器人 (無頭像且新註冊)"
                
                try:
                    # 1. 發送私訊通知
                    try:
                        await after.send(f"⚠️ 您已被伺服器拒絕加入：\n> {reason}")
                        log("INFO", "防護", f"已發送拒絕通知給 {after.name}")
                    except discord.Forbidden:
                        log("WARN", "防護", f"無法私訊 {after.name}，對方可能關閉私訊")

                    # 2. 執行封鎖 (Ban)
                    await after.ban(reason=reason, delete_message_seconds=86400)
                    log("INFO", "防護", f"🔨 已封鎖疑似機器人: {after.name}")

                except Exception as e:
                    log_exception("ERROR", "防護", f"處置 {after.name} 時出錯", exc=e)

async def setup(bot):
    await bot.add_cog(Security(bot))