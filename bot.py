import discord
from discord.ext import commands
import os
import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv
from web.server import WebServer

# 載入環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
WEB_PORT = int(os.getenv('WEB_PORT', 8080))  # 網頁端口，預設8080

# 讀取版本號
def get_version():
    """從 version.txt 讀取版本號"""
    try:
        with open('./version.txt', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # 解析 versions = x.x.x 格式
            if '=' in content:
                return content.split('=')[1].strip()
            return content
    except:
        return "Unknown"

def print_banner():
    """顯示啟動橫幅"""
    version = get_version()
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        ██████╗██╗   ██╗██████╗ ██╗                           ║
║       ██╔════╝██║   ██║██╔══██╗██║                           ║
║       ██║     ██║   ██║██████╔╝██║                           ║
║       ██║     ██║   ██║██╔══██╗██║                           ║
║       ╚██████╗╚██████╔╝██║  ██║███████╗                      ║
║        ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝                      ║
║                                                              ║
║                    多功能 Discord 機器人                     ║
║                      Version {version:<31} ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"⏰ 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True  # 需要此權限才能獲取成員在線狀態
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # 初始化網頁伺服器
        self.web_server = WebServer(self, port=WEB_PORT)
    
    async def setup_hook(self):
        print("\n📦 正在初始化系統...")
        print("─" * 62)
        
        # 啟動網頁控制台
        print("🌐 啟動網頁控制台...")
        await self.web_server.start()
        print(f"   ✓ 網頁控制台已啟動 (端口: {WEB_PORT})")
        
        # 載入所有cogs
        print("\n📁 載入功能模組...")
        cog_count = 0
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                cog_name = filename[:-3].replace('_', ' ').title()
                print(f"   ✓ {cog_name}")
                cog_count += 1
        print(f"\n   總計載入 {cog_count} 個模組")
        
        # 同步slash commands
        print("\n⚡ 同步斜線命令...")
        await self.tree.sync()
        print("   ✓ 命令已同步至 Discord")
        print("─" * 62)
        
        # 啟動終端輸入監聽
        self.loop.create_task(self.handle_terminal_input())
    
    async def on_ready(self):
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                    🤖 機器人已成功啟動                       ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        
        print("\n📊 機器人資訊:")
        print(f"   • 名稱:     {self.user.name}")
        print(f"   • ID:       {self.user.id}")
        print(f"   • 伺服器:   {len(self.guilds)} 個")
        print(f"   • 用戶數:   {sum(g.member_count for g in self.guilds):,} 位")
        print(f"   • 延遲:     {round(self.latency * 1000)}ms")
        print(f"   • 網頁:     http://localhost:{WEB_PORT}")
        
        print("\n" + "═" * 62)
        print("💬 終端命令:")
        print("   restart  - 重啟機器人     │   status  - 顯示狀態")
        print("   stop     - 關閉機器人     │   ver     - 查看版本")
        print("   help     - 顯示幫助")
        print("═" * 62)
        
        print("\n✨ 準備就緒！等待指令中...")
        print("\n💡 提示:")
        print("   • 使用 /help 查看所有指令")
        print(f"   • 訪問網頁控制台：http://localhost:{WEB_PORT}")
        print("   • 在終端輸入 help 查看管理命令\n")
    
    async def handle_terminal_input(self):
        """處理終端輸入命令"""
        def get_input():
            return sys.stdin.readline().strip()
        
        while True:
            try:
                # 在另一個執行緒中讀取輸入，避免阻塞事件循環
                command = await asyncio.get_event_loop().run_in_executor(None, get_input)
                
                if not command:
                    continue
                
                # 處理命令
                if command.lower() in ['restart', '重啟', 'restat']:
                    print('\n' + '═' * 62)
                    print('🔄 正在重啟機器人...')
                    print('═' * 62 + '\n')
                    await self.close()
                    # 重新啟動 (支援 Linux/Windows)
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                
                elif command.lower() in ['stop', '關閉', 'quit', 'exit']:
                    print('\n' + '═' * 62)
                    print('🛑 正在關閉機器人...')
                    await self.web_server.stop()
                    await self.close()
                    print('✓ 已安全關閉')
                    print('═' * 62 + '\n')
                    sys.exit(0)
                
                elif command.lower() in ['status', '狀態']:
                    print('\n' + '╔' + '═' * 60 + '╗')
                    print('║' + ' ' * 22 + '📊 機器人狀態' + ' ' * 22 + '║')
                    print('╠' + '═' * 60 + '╣')
                    print(f'║  名稱:     {self.user.name:<45}║')
                    print(f'║  ID:       {str(self.user.id):<45}║')
                    print(f'║  伺服器:   {str(len(self.guilds)) + " 個":<45}║')
                    print(f'║  延遲:     {str(round(self.latency * 1000)) + "ms":<45}║')
                    print(f'║  網頁:     {"http://localhost:" + str(WEB_PORT):<45}║')
                    print(f'║  運行時間: {str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")):<45}║')
                    print('╚' + '═' * 60 + '╝\n')
                
                elif command.lower() in ['ver', 'version', '版本']:
                    version = get_version()
                    print('\n' + '╔' + '═' * 60 + '╗')
                    print('║' + ' ' * 22 + '📌 版本資訊' + ' ' * 24 + '║')
                    print('╠' + '═' * 60 + '╣')
                    print(f'║  當前版本: {version:<46}║')
                    print('╚' + '═' * 60 + '╝\n')
                
                elif command.lower() in ['help', '幫助', 'h']:
                    print('\n' + '╔' + '═' * 60 + '╗')
                    print('║' + ' ' * 21 + '📋 可用終端命令' + ' ' * 21 + '║')
                    print('╠' + '═' * 60 + '╣')
                    print('║  restart / 重啟     重新啟動機器人' + ' ' * 21 + '║')
                    print('║  stop / 關閉        關閉機器人' + ' ' * 25 + '║')
                    print('║  status / 狀態      顯示機器人狀態' + ' ' * 21 + '║')
                    print('║  ver / 版本         顯示當前版本' + ' ' * 23 + '║')
                    print('║  help / 幫助        顯示此幫助訊息' + ' ' * 21 + '║')
                    print('╚' + '═' * 60 + '╝\n')
                
                else:
                    print(f'❌ 未知命令: {command}')
                    print('💡 輸入 help 查看可用命令\n')
            
            except Exception as e:
                print(f'❌ 處理命令時發生錯誤: {e}')
                await asyncio.sleep(0.1)

def main():
    print_banner()
    bot = MyBot()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print('\n\n' + '═' * 62)
        print('⚠️  收到中斷信號，正在關閉...')
        print('═' * 62 + '\n')
    except Exception as e:
        print('\n\n' + '═' * 62)
        print(f'❌ 發生錯誤: {e}')
        print('═' * 62 + '\n')

if __name__ == '__main__':
    main()

# time 0