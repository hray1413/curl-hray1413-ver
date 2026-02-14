# curl 源代碼

这是一個使用Python编写的Discord機器人，支援Slash Commands和Cogs模組化結構。

## 功能特點

- ✅ 使用 Discord.py 2.0+ 
- ✅ 支援 Slash Commands（斜線指令）
- ✅ 模組化 Cogs 結構
- ✅ 自動載入所有 cogs
- ✅ 環境變數配置
- ✅ 網頁後台控制台（OAuth2 登入）
- ✅ 警告系統（自動處罰）
- ✅ 成就系統（40+ 成就，4 種稀有度）
- ✅ 等級經驗系統
- ✅ 簽到系統
- ✅ 生日系統
- ✅ 遊戲系統（21點、猜拳、猜數字）
- ✅ 統計分析系統
- ✅ 個人資料卡片系統
- ✅ 反應角色系統
- ✅ 歡迎/離開系統
- ✅ 臨時語音頻道系統
- ✅ 自定義命令系統
- ✅ 自動日誌記錄系統
- ✅ 實用工具集合
- ✅ 終端命令控制

## 指令列表

### 📋 一般指令 (`/一般`)
- `/一般 延遲檢查` - 檢查機器人延遲
- `/一般 打招呼` - 打個招呼
- `/一般 查看用戶資訊` - 查看用戶詳細資訊
- `/一般 機器人信息` - 查看機器人資訊

### 🛡️ 管理指令 (`/管理`)
**基礎管理：**
- `/管理 踢出用戶` - 踢出成員
- `/管理 封鎖用戶` - 封禁成員
- `/管理 清除訊息` - 批量刪除訊息

**⚠️ 警告系統：**
- `/管理 警告` - 警告用戶
- `/管理 取消警告` - 取消最近一次警告
- `/管理 警告記錄` - 查看警告歷史
- `/管理 清除警告` - 清除所有警告（需管理員）

**自動處罰規則：**
- 3次警告 → 自動踢出伺服器
- 5次警告 → 自動封禁

### 🎮 遊戲指令 (`/遊戲`)
- `/遊戲 21點` - 21點撲克遊戲
- `/遊戲 猜拳` - 猜拳遊戲（剪刀石頭布）
- `/遊戲 猜數字` - 猜數字遊戲（1-100）
- `/遊戲 排行榜` - 查看遊戲排行榜
- `/遊戲 統計` - 查看你的遊戲統計

### 🎭 娛樂指令 (`/娛樂`)
- `/娛樂 投擲骰子` - 投擲骰子
- `/娛樂 擲硬幣` - 擲硬幣
- `/娛樂 魔法8球` - 魔法8球問答
- `/娛樂 幫你選擇` - 幫你做選擇

### 🏆 成就系統 (`/成就`)
- `/成就 列表` - 查看所有可用成就
- `/成就 我的成就` - 查看已解鎖的成就
- `/成就 進度` - 查看成就解鎖進度
- **成就類型**: 訊息、等級、遊戲、簽到、特殊
- **稀有度**: 普通、稀有、史詩、傳奇
- **自動解鎖**: 達成條件後自動解鎖

### 📊 伺服器資訊 (`/伺服器`)
- `/伺服器 資訊` - 查看伺服器詳細資訊
- `/伺服器 圖標` - 查看伺服器圖標
- `/伺服器 成員統計` - 成員統計和在線狀態
- `/伺服器 角色列表` - 查看所有角色

### ⭐ 等級系統 (`/等級`)
- `/等級 查看` - 查看等級和經驗
- `/等級 排行榜` - 查看等級排行榜
- `/等級 重置` - 重置用戶等級（需管理員）
- **自動功能**: 發送訊息獲得經驗，升級自動通知

### 📅 簽到系統 (`/簽到`)
- `/簽到 查看` - 查看簽到資訊
- `/簽到 打卡` - 每日簽到取得積分
- `/簽到 排行榜` - 簽到排行榜
- `/簽到 重置` - 重置用戶簽到（需管理員）

### 🎂 生日系統 (`/生日`)
- `/生日 設定` - 設定你的生日
- `/生日 查看` - 查看生日資訊
- `/生日 列表` - 查看本月生日名單
- `/生日 刪除` - 刪除你的生日
- `/生日 開關` - 開啟/關閉生日提醒（需管理員）
- `/生日 設定頻道` - 設定生日通知頻道（需管理員）

### 📈 統計系統 (`/統計`)
- `/統計 活躍度` - 查看同服活躍度統計
- `/統計 活躍排行` - 查看活躍用戶排行
- `/統計 熱門頻道` - 查看熱門頻道
- `/統計 時段分析` - 查看24小時活躍分析
- `/統計 我的統計` - 查看你的個人統計

### 👤 個人資料 (`/個人資料`)
- `/個人資料 查看` - 查看個人資料卡片
- `/個人資料 設定簡介` - 設定個人簡介（最多100字）
- `/個人資料 設定標題` - 設定個人標題（最多30字）
- `/個人資料 設定顏色` - 自定義卡片顏色（十六進位）
- `/個人資料 清除` - 清除所有自定義設定

### 👆 反應角色 (`/反應角色`)
- `/反應角色 創建` - 創建反應角色訊息
- `/反應角色 列表` - 查看所有反應角色
- `/反應角色 添加` - 為訊息添加反應角色
- `/反應角色 移除` - 移除反應角色

### 👋 歡迎系統 (`/歡迎系統`)
- `/歡迎系統 查看設定` - 查看歡迎系統設定
- `/歡迎系統 開關` - 啟用/停用歡迎或離開系統
- `/歡迎系統 設定歡迎頻道` - 設定歡迎訊息頻道
- `/歡迎系統 設定歡迎訊息` - 自訂歡迎訊息
- `/歡迎系統 設定離開頻道` - 設定離開訊息頻道
- `/歡迎系統 設定離開訊息` - 自訂離開訊息
- **網頁管理**: 可在網頁控制台完全自定義

### 🎤 臨時語音 (`/臨時語音`)
- `/臨時語音 設定` - 設定觸發頻道和分類
- `/臨時語音 停用` - 停用系統
- `/臨時語音 狀態` - 查看系統狀態
- `/臨時語音 限制人數` - 設定頻道人數上限
- `/臨時語音 重命名` - 重命名你的臨時頻道
- **自動功能**: 用戶加入觸發頻道自動創建，離開後自動刪除
- **網頁管理**: 可在網頁控制台配置

### 📝 自定義命令 (`/自定義`)
- `/自定義 添加` - 添加自定義命令
- `/自定義 刪除` - 刪除自定義命令
- `/自定義 編輯` - 編輯命令內容
- `/自定義 列表` - 查看所有自定義命令
- **使用方式**: 用 `!命令名稱` 觸發
- **網頁管理**: 可在網頁控制台管理

### 🔧 工具指令 (`/工具`)
- `/工具 頭像` - 查看用戶頭像
- `/工具 計算器` - 計算數學表達式
- `/工具 倒數計時` - 創建倒數計時
- `/工具 投票` - 創建投票（最多5個選項）
- `/工具 提醒我` - 設定定時提醒
- `/工具 縮短文字` - 縮短長文本
- `/工具 隨機數` - 生成隨機數

### 🔍 日誌系統
- 自動記錄所有指令使用
- 彩色 Embed 格式，按類型顯示不同顏色
- 需在 `.env` 配置日誌頻道 ID

## 安裝步骤

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 配置環境變數
複製 `.env.example` 為 `.env`，然後編輯填入以下資訊：

```env
# Discord Bot Token（必需）
DISCORD_TOKEN=你的機器人token

# 日誌頻道 ID（可選）
LOG_CHANNEL_ID=日誌頻道的ID

# 網頁控制台設定（可選）
WEB_PORT=8080

# Discord OAuth2 設定（網頁登入必需）
DISCORD_CLIENT_ID=你的應用ID
DISCORD_CLIENT_SECRET=你的應用密鑰
DISCORD_REDIRECT_URI=http://localhost:8080/callback

# Session 密鑰（可選，會自動生成）
SESSION_SECRET=隨機44字符的密鑰
```

### 3. 獲取 Discord Bot Token 和 OAuth2 設定

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 創建新應用或選擇現有應用
3. 在左側選單選擇 "Bot"
4. 點擊 "Add Bot"（如果還沒有）
5. 複製 Token 並填入 `.env` 的 `DISCORD_TOKEN`
6. 在 "Privileged Gateway Intents" 中啟用：
   - **MESSAGE CONTENT INTENT** - 讀取訊息內容
   - **SERVER MEMBERS INTENT** - 獲取成員列表
   - **PRESENCE INTENT** - 獲取成員在線狀態

**OAuth2 設定（網頁控制台必需）：**
1. 在左側選單選擇 "OAuth2" > "General"
2. 複製 "CLIENT ID" 並填入 `.env` 的 `DISCORD_CLIENT_ID`
3. 複製 "CLIENT SECRET" 並填入 `.env` 的 `DISCORD_CLIENT_SECRET`
4. 在 "Redirects" 中添加：`http://localhost:8080/callback`
5. 如果部署到伺服器，也添加：`http://你的IP:8080/callback`

**獲取頻道 ID（可選）：**
1. 在 Discord 中啟用開發者模式（設定 > 進階 > 開發者模式）
2. 右鍵點擊要用作日誌的頻道
3. 點擊 "複製頻道 ID"
4. 填入 `.env` 的 `LOG_CHANNEL_ID`

### 4. 邀請機器人到伺服器

1. 在Developer Portal中選擇 "OAuth2" > "URL Generator"
2. 選擇scope:
   - `bot`
   - `applications.commands`
3. 選擇Bot Permissions (根據需要):
   - Send Messages
   - Manage Messages
   - Kick Members
   - Ban Members
   - Embed Links
   等等
4. 複製生成的URL并在浏览器中打开，選擇伺服器邀請機器人

### 5. 運行機器人
```bash
python bot.py
```

機器人啟動後會自動：
- 顯示精美的啟動橫幅
- 載入所有 Cogs 模組
- 同步 Slash 指令
- 啟動網頁後台控制台（預設端口：8080）
- 啟動終端命令監聽

**訪問網頁控制台**：
- 本地訪問：http://localhost:8080
- 網路訪問：http://你的IP:8080
- 使用 Discord 帳號登入（OAuth2）

**網頁管理功能**：
- 📊 實時統計數據：成員數、頻道數、角色數等
- ⭐ 等級系統：查看排行榜和用戶等級
- 📅 簽到系統：簽到統計和排行
- 👋 歡迎系統：完全自定義歡迎/離開訊息和頻道
- 🎂 生日系統：查看生日列表
- 🎮 遊戲系統：遊戲統計和排行
- 📈 活躍度分析：伺服器活躍度數據
- 📝 自定義命令：創建和管理自定義命令
- 🎤 臨時語音：配置臨時語音頻道設定
- ⚠️ 警告系統：查看和管理用戶警告記錄
- 🏆 成就系統：查看用戶成就解鎖情況、授予/撤銷成就

**終端命令控制**：
機器人運行時，可直接在終端輸入以下命令進行控制：
- `restart` 或 `重啟` - 重新啟動機器人
- `stop` 或 `關閉` - 安全關閉機器人
- `status` 或 `狀態` - 顯示機器人當前狀態
- `help` 或 `幫助` - 顯示終端命令幫助

## 添加新的 Cog

在 `cogs/` 資料夾中創建新的 Python 檔案，例如 `cogs/mycog.py`：

```python
import discord
from discord import app_commands
from discord.ext import commands

class MyCog(commands.Cog):
    """我的自訂 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="mycommand", description="我的指令描述")
    async def mycommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'📦 {self.__class__.__name__} cog已載入')

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

機器人會自動載入所有在 `cogs/` 資料夾中的 Python 檔案。

## 專案結構

```
.
├── bot.py                  # 主程式檔案
├── version.txt             # 版本號
├── .env                    # 環境變數（需要創建）
├── .env.example            # 環境變數示例
├── requirements.txt        # Python 依賴
├── README.md               # 說明文檔
├── OAUTH_SETUP.md          # OAuth2 設定教學
├── LICENSE                 # 授權文件
├── .gitignore              # Git 忽略檔案
├── data/                   # 數據目錄（自動生成）
│   └── [guild_id]/         # 各伺服器數據
│       ├── levels.json           # 等級數據
│       ├── daily.json            # 簽到數據
│       ├── birthdays.json        # 生日數據
│       ├── welcome.json          # 歡迎系統設定
│       ├── custom_commands.json  # 自定義命令
│       ├── temp_voice.json       # 臨時語音設定
│       ├── warnings.json         # 警告記錄
│       ├── achievements.json     # 成就數據
│       ├── reaction_roles.json   # 反應角色
│       ├── profiles.json         # 個人資料
│       ├── statistics.json       # 統計數據
│       ├── tickets.json          # 客服單數據
│       └── ticket/               # 客服單聊天記錄（HTML）
├── web/                    # 網頁控制台
│   ├── server.py           # Web 伺服器（OAuth2 + API）
│   ├── index.html          # 登入頁面
│   ├── select_server.html  # 伺服器選擇
│   ├── dashboard.html      # 控制台主頁
│   ├── my-tickets.html     # 我的客服單頁面
│   └── static/             # 靜態資源（CSS、JS、圖片）
├── website/                # 官網（排除於 Git 之外）
└── cogs/                   # Cogs 資料夾（功能模組）
    ├── general.py          # 一般指令（ping、userinfo、help）
    ├── moderation.py       # 管理指令（kick、ban、warn、清除訊息）
    ├── fun.py              # 娛樂指令（骰子、硬幣、魔法8球）
    ├── games.py            # 遊戲系統（21點、猜拳、猜數字）
    ├── serverinfo.py       # 伺服器資訊統計
    ├── utilities.py        # 實用工具集合（頭像、計算器、提醒）
    ├── leveling.py         # 等級系統
    ├── daily.py            # 簽到系統
    ├── birthday.py         # 生日系統
    ├── welcome.py          # 歡迎/離開系統
    ├── temp_voice.py       # 臨時語音頻道
    ├── custom_commands.py  # 自定義命令
    ├── profile.py          # 個人資料卡片
    ├── achievements.py     # 成就系統（150+ 成就）
    ├── reaction_roles.py   # 反應角色
    ├── statistics.py       # 統計分析（活躍度、熱門頻道）
    ├── tickets.py          # 客服單系統（HTML 聊天記錄）
    ├── polls.py            # 投票/問卷系統（按鈕式 UI）
    ├── updater.py          # 自動更新系統
    ├── developer.py        # 開發者專用指令
    └── logging_system.py   # 日誌系統
```

## 等級系統說明

等級系統會自動追蹤用戶的活躍度：
- 每發送一則訊息獲得 15-25 隨機經驗值
- 60秒冷卻時間防止刷經驗
- 升級時自動發送通知
- 數據存儲在 `./data/[guild_id]/levels.json` 檔案中
- 每個伺服器的數據獨立

**經驗公式**: 
- 等級 1→2: 100 XP
- 等級 2→3: 150 XP
- 等級 N→N+1: 100 + (N-1) × 50 XP

## 數據存儲

所有數據按伺服器 ID 分別存儲在 `./data/[guild_id]/` 目錄下：
- **levels.json** - 等級和經驗數據
- **daily.json** - 簽到記錄和積分
- **birthdays.json** - 生日資訊
- **welcome.json** - 歡迎系統設定
- **custom_commands.json** - 自定義命令
- **temp_voice.json** - 臨時語音設定
- **warnings.json** - 警告記錄
- **achievements.json** - 成就解鎖狀態
- **reaction_roles.json** - 反應角色配置
- **profiles.json** - 個人資料自定義
- **statistics.json** - 活躍度統計

建議定期備份 `./data/` 資料夾。

## 注意事項

- 確保機器人有足夠的權限執行指令
- Slash commands 需要一些時間同步（最多1小時）
- 首次運行時會自動同步所有 slash commands
- 不要將 `.env` 檔案提交到 Git 倉庫
- `./data/` 資料夾會自動創建，建議定期備份
- 網頁控制台需要正確配置 Discord OAuth2 設定
- 警告系統會自動處罰：3次踢出、5次封禁
- 成就系統會自動追蹤用戶行為並解鎖成就

## 故障排除

### Slash commands 沒有顯示
- 確保 bot 有 `applications.commands` scope
- 等待最多1小時讓 Discord 同步指令
- 檢查機器人是否在伺服器中
- 嘗試在終端輸入 `restart` 重啟機器人

### 權限錯誤
- 確保在 Developer Portal 中啟用了必要的 Intents
- 檢查機器人在伺服器中的角色權限
- 確認機器人角色位置高於要管理的角色

### 網頁控制台無法登入
- 檢查 `.env` 中的 OAuth2 設定是否正確
- 確認 Redirect URI 在 Developer Portal 中已添加
- 檢查 `SESSION_SECRET` 是否設定（可自動生成）
- 確保網頁端口未被其他程序佔用

### 數據未保存
- 檢查 `./data/[guild_id]/` 目錄是否有寫入權限
- 確認相關 JSON 檔案格式正確
- 查看終端錯誤訊息

### 警告系統不工作
- 確保機器人有 "踢出成員" 和 "封禁成員" 權限
- 檢查 `./data/[guild_id]/warnings.json` 是否存在
- 確認執行者權限高於被警告者

## 許可證

MIT License
