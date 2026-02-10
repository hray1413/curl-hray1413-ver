import discord
from discord import app_commands
from discord.ext import commands
import psutil
import platform

class General(commands.Cog):
    """通用指令"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # 創建指令組
    general_group = app_commands.Group(name="一般", description="一般功能指令")
    
    @general_group.command(name="延遲檢查", description="檢查機器人延遲")
    async def ping(self, interaction: discord.Interaction):
        """Ping指令 - 顯示機器人延遲"""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f'🏓 Pong! 延遲: {latency}ms')
    
    @general_group.command(name="打招呼", description="打個招呼")
    async def hello(self, interaction: discord.Interaction):
        """Say hello"""
        await interaction.response.send_message(f'👋 你好, {interaction.user.mention}!')
    
    @general_group.command(name="查看用戶資訊", description="查看用戶資訊")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        """顯示用戶資訊"""
        member = member or interaction.user
        
        embed = discord.Embed(
            title=f"{member.name} 的資訊",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="📛 用戶名", value=str(member), inline=True)
        embed.add_field(name="🆔 ID", value=member.id, inline=True)
        embed.add_field(name="📅 加入時間", value=discord.utils.format_dt(member.joined_at, style='R'), inline=False)
        embed.add_field(name="📅 帳號創建時間", value=discord.utils.format_dt(member.created_at, style='R'), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @general_group.command(name="機器人信息", description="查看機器人系統資訊")
    async def botinfo(self, interaction: discord.Interaction):
        """顯示機器人系統資訊"""
        # 獲取系統資訊
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        embed = discord.Embed(
            title="🤖 機器人系統資訊",
            color=discord.Color.blue(),
            description=f"**系統：** {platform.system()} {platform.release()}"
        )
        
        # CPU 使用率
        embed.add_field(
            name="💻 CPU 使用率",
            value=f"```{cpu_percent}%```",
            inline=True
        )
        
        # 記憶體使用率
        embed.add_field(
            name="🧠 記憶體使用率",
            value=f"```{memory.percent}%\n{memory.used / (1024**3):.2f}GB / {memory.total / (1024**3):.2f}GB```",
            inline=True
        )
        
        # 磁碟使用率
        embed.add_field(
            name="💾 儲存空間使用率",
            value=f"```{disk.percent}%\n{disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB```",
            inline=True
        )
        
        # Python 版本
        embed.add_field(
            name="🐍 Python 版本",
            value=f"```{platform.python_version()}```",
            inline=True
        )
        
        # Discord.py 版本
        embed.add_field(
            name="📚 Discord.py 版本",
            value=f"```{discord.__version__}```",
            inline=True
        )
        
        # 伺服器數量
        embed.add_field(
            name="🌐 服務伺服器數",
            value=f"```{len(self.bot.guilds)}```",
            inline=True
        )
        
        # GitHub 開源資訊
        embed.add_field(
            name="\u200b",
            value="本機器人在 Github 上開源，[Github](https://github.com/wei530601/curl) 可點擊",
            inline=False
        )
        
        embed.set_footer(text=f"請求者：{interaction.user.name}")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    @general_group.command(name="幫助", description="顯示所有可用指令")
    async def help(self, interaction: discord.Interaction):
        """顯示幫助資訊"""
        embed = discord.Embed(
            title="📚 指令幫助",
            description="以下是所有可用的指令列表",
            color=discord.Color.from_rgb(37, 99, 235)
        )
        
        # 一般指令
        embed.add_field(
            name="📌 /一般",
            value=(
                "`延遲檢查` - 檢查機器人延遲\n"
                "`打招呼` - 打個招呼\n"
                "`查看用戶資訊` - 查看用戶詳細資訊\n"
                "`機器人信息` - 查看機器人系統資訊\n"
                "`幫助` - 顯示此幫助訊息"
            ),
            inline=False
        )
        
        # 管理指令
        embed.add_field(
            name="🛡️ /管理",
            value=(
                "`踢出用戶` - 踢出指定用戶\n"
                "`封禁用戶` - 封禁指定用戶\n"
                "`清除消息` - 清除指定數量的消息"
            ),
            inline=False
        )
        
        # 娛樂指令
        embed.add_field(
            name="🎮 /娛樂",
            value=(
                "`擲骰子` - 擲一個骰子 (1-6)\n"
                "`拋硬幣` - 拋硬幣 (正面/反面)\n"
                "`8ball` - 問一個問題，獲得隨機答案\n"
                "`選擇` - 從多個選項中隨機選擇"
            ),
            inline=False
        )
        
        # 伺服器指令
        embed.add_field(
            name="🏰 /伺服器",
            value=(
                "`資訊` - 查看伺服器詳細資訊\n"
                "`圖標` - 顯示伺服器圖標\n"
                "`統計` - 查看伺服器統計數據\n"
                "`身分組列表` - 查看所有身分組"
            ),
            inline=False
        )
        
        # 工具指令
        embed.add_field(
            name="🔧 /工具",
            value=(
                "`頭像` - 查看用戶頭像\n"
                "`計算機` - 進行數學計算\n"
                "`投票` - 創建投票\n"
                "`提醒` - 設定提醒\n"
                "`翻譯` - 翻譯文字\n"
                "`縮短網址` - 縮短長網址\n"
                "`二維碼` - 生成QR碼\n"
                "`天氣` - 查看天氣資訊"
            ),
            inline=False
        )
        
        # 等級指令
        embed.add_field(
            name="⭐ /等級",
            value=(
                "`查看` - 查看自己或其他用戶的等級\n"
                "`排行榜` - 查看等級排行榜\n"
                "`重置` - 重置用戶等級 (需要管理權限)"
            ),
            inline=False
        )
        
        embed.set_footer(text="使用 / 來查看所有指令")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(General(bot))
