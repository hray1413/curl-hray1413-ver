import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
import hashlib
from datetime import datetime

class Updater(commands.Cog):
    """自動更新檢查系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.github_repo = "wei530601/curl"
        self.branch = "main"
        self.version_url = f"https://raw.githubusercontent.com/{self.github_repo}/refs/heads/{self.branch}/version.txt"
        self.update_checked = False
        
    def get_local_version(self):
        """讀取本地版本號"""
        try:
            with open('./version.txt', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if '=' in content:
                    return content.split('=')[1].strip()
                return content
        except Exception as e:
            print(f"   ❌ 無法讀取本地版本: {e}")
            return None
    
    async def get_remote_version(self):
        """獲取遠程版本號"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.version_url) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        content = content.strip()
                        if '=' in content:
                            return content.split('=')[1].strip()
                        return content
                    else:
                        print(f"   ❌ 無法獲取遠程版本 (HTTP {resp.status})")
                        return None
        except Exception as e:
            print(f"   ❌ 獲取遠程版本時出錯: {e}")
            return None
    
    async def get_changed_files(self, local_version, remote_version):
        """通過 GitHub API 獲取兩個版本之間更改的文件"""
        try:
            # 獲取最近的提交來查找更改的文件
            commits_url = f"https://api.github.com/repos/{self.github_repo}/commits"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(commits_url, params={"per_page": 50}) as resp:
                    if resp.status == 200:
                        commits = await resp.json()
                        changed_files = set()
                        
                        # 查找包含版本更新的提交，並收集所有更改的文件
                        for commit in commits:
                            # 獲取每個提交的詳細信息
                            commit_url = commit['url']
                            async with session.get(commit_url) as commit_resp:
                                if commit_resp.status == 200:
                                    commit_data = await commit_resp.json()
                                    files = commit_data.get('files', [])
                                    
                                    for file in files:
                                        filename = file['filename']
                                        # 排除某些文件
                                        if not self.should_exclude_file(filename):
                                            changed_files.add(filename)
                            
                            # 限制只檢查最近幾個提交
                            if len(changed_files) > 0:
                                break
                        
                        return list(changed_files)
                    else:
                        print(f"   ⚠️  無法獲取提交歷史 (HTTP {resp.status})，將下載所有核心文件")
                        # 如果無法獲取提交，返回核心文件列表
                        return self.get_core_files()
        except Exception as e:
            print(f"   ❌ 獲取更改文件列表時出錯: {e}")
            return self.get_core_files()
    
    def should_exclude_file(self, filename):
        """判斷文件是否應該被排除"""
        exclude_patterns = [
            'website/',       # 網站文件
            '.git/',          # Git 文件
            'data/',          # 數據文件
            '.env',           # 環境變量
            '__pycache__/',   # Python 緩存
            '.pyc',           # Python 編譯文件
            'README.md',      # 說明文件（可選）
            '.gitignore',     # Git 忽略文件
        ]
        
        for pattern in exclude_patterns:
            if pattern in filename:
                return True
        return False
    
    def get_core_files(self):
        """獲取核心文件列表（作為後備方案）"""
        core_files = ['bot.py']
        
        # 添加所有 cog 文件
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    core_files.append(f'cogs/{filename}')
        
        # 添加 web 文件
        if os.path.exists('./web'):
            for filename in os.listdir('./web'):
                if filename.endswith('.py'):
                    core_files.append(f'web/{filename}')
        
        return core_files
    
    async def download_file(self, filepath):
        """從 GitHub 下載單個文件"""
        try:
            file_url = f"https://raw.githubusercontent.com/{self.github_repo}/refs/heads/{self.branch}/{filepath}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        
                        # 確保目錄存在
                        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
                        
                        # 寫入文件
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        
                        return True
                    else:
                        print(f"      ❌ 下載失敗: {filepath} (HTTP {resp.status})")
                        return False
        except Exception as e:
            print(f"      ❌ 下載 {filepath} 時出錯: {e}")
            return False
    
    async def check_and_update(self):
        """檢查並執行更新"""
        print("\n🔍 檢查更新...")
        print("─" * 62)
        
        local_version = self.get_local_version()
        if not local_version:
            print("   ⚠️  無法讀取本地版本，跳過更新檢查")
            return
        
        print(f"   📌 本地版本: {local_version}")
        
        remote_version = await self.get_remote_version()
        if not remote_version:
            print("   ⚠️  無法獲取遠程版本，跳過更新檢查")
            return
        
        print(f"   🌐 遠程版本: {remote_version}")
        
        if local_version == remote_version:
            print("   ✅ 當前版本已是最新！")
            print("─" * 62)
            return
        
        print(f"\n   🎉 發現新版本: {local_version} → {remote_version}")
        print("\n   📥 正在獲取更新文件列表...")
        
        changed_files = await self.get_changed_files(local_version, remote_version)
        
        if not changed_files:
            print("   ⚠️  無法獲取更新文件列表")
            print("─" * 62)
            return
        
        print(f"   📋 找到 {len(changed_files)} 個需要更新的文件")
        
        print("\n   📥 開始下載更新...")
        success_count = 0
        fail_count = 0
        
        for filepath in changed_files:
            print(f"      ⬇️  {filepath}")
            if await self.download_file(filepath):
                success_count += 1
            else:
                fail_count += 1
            await asyncio.sleep(0.1)  # 避免請求過快
        
        print(f"\n   ✅ 成功: {success_count} 個文件")
        if fail_count > 0:
            print(f"   ❌ 失敗: {fail_count} 個文件")
        
        # 更新本地版本號
        try:
            with open('./version.txt', 'w', encoding='utf-8') as f:
                f.write(f"versions = {remote_version}")
            print(f"\n   🎊 更新完成！版本已升級至 {remote_version}")
            print("   ⚠️  建議重啟機器人以應用更新")
        except Exception as e:
            print(f"   ❌ 寫入版本文件失敗: {e}")
        
        print("─" * 62)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """機器人準備就緒時自動檢查更新"""
        if not self.update_checked:
            self.update_checked = True
            # 等待一小段時間，讓機器人完全初始化
            await asyncio.sleep(2)
            await self.check_and_update()
    
    @commands.command(name='checkupdate', aliases=['更新檢查', 'update'])
    @commands.has_permissions(administrator=True)
    async def check_update_command(self, ctx):
        """手動檢查更新（僅管理員）"""
        await ctx.send("🔍 正在檢查更新，請查看控制台輸出...")
        await self.check_and_update()

async def setup(bot):
    await bot.add_cog(Updater(bot))
