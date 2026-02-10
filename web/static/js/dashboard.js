// dashboard.js - 儀表板頁面

const GUILD_ID = '{GUILD_ID}';

// 載入統計數據
async function loadStats() {
    try {
        const response = await fetch('/api/stats/' + GUILD_ID);
        if (response.ok) {
            const stats = await response.json();
            document.getElementById('member-count').textContent = stats.member_count.toLocaleString();
            document.getElementById('channel-count').textContent = stats.channel_count;
            document.getElementById('role-count').textContent = stats.role_count;
            document.getElementById('text-channels').textContent = stats.text_channels;
        }
    } catch (error) {
        console.error('載入統計數據失敗:', error);
    }
}

// 載入等級數據
async function loadLevels() {
    try {
        const response = await fetch('/api/data/' + GUILD_ID + '/levels');
        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('levels-data');
            
            if (!data.exists || Object.keys(data.data).length === 0) {
                container.innerHTML = '<p style="color: #888;">暫無等級數據</p>';
                return;
            }
            
            // 計算統計
            const users = Object.keys(data.data).length;
            const totalXP = Object.values(data.data).reduce((sum, user) => sum + (user.xp || 0), 0);
            const totalMessages = Object.values(data.data).reduce((sum, user) => sum + (user.messages || 0), 0);
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">註冊用戶</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${users}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">總經驗值</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${totalXP.toLocaleString()}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">總訊息數</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${totalMessages.toLocaleString()}</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('levels-data').innerHTML = '<p style="color: #dc2626;">載入失敗</p>';
    }
}

// 載入簽到數據
async function loadDaily() {
    try {
        const response = await fetch('/api/data/' + GUILD_ID + '/daily');
        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('daily-data');
            
            if (!data.exists || Object.keys(data.data).length === 0) {
                container.innerHTML = '<p style="color: #888;">暫無簽到數據</p>';
                return;
            }
            
            const users = Object.keys(data.data).length;
            const totalCheckins = Object.values(data.data).reduce((sum, user) => sum + (user.total_checkins || 0), 0);
            const totalPoints = Object.values(data.data).reduce((sum, user) => sum + (user.total_points || 0), 0);
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">簽到用戶</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${users}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">總簽到次數</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${totalCheckins.toLocaleString()}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">總積分</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${totalPoints.toLocaleString()}</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('daily-data').innerHTML = '<p style="color: #dc2626;">載入失敗</p>';
    }
}

// 載入歡迎系統設定
async function loadWelcome() {
    try {
        const response = await fetch('/api/data/' + GUILD_ID + '/welcome');
        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('welcome-data');
            
            if (!data.exists) {
                container.innerHTML = '<p style="color: #888;">尚未設定歡迎系統</p>';
                return;
            }
            
            const settings = data.data;
            const welcomeChecked = settings.welcome_enabled ? 'checked' : '';
            const leaveChecked = settings.leave_enabled ? 'checked' : '';
            const welcomeStatusColor = settings.welcome_enabled ? '#2563eb' : '#6b7280';
            const leaveStatusColor = settings.leave_enabled ? '#2563eb' : '#6b7280';
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    <div style="background: #1a1a1a; padding: 1.25rem; border-left: 3px solid ${welcomeStatusColor};">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                            <div style="color: #ccc; font-size: 0.95rem; font-weight: 500;">歡迎系統</div>
                            <label style="position: relative; display: inline-block; width: 44px; height: 22px; cursor: pointer;">
                                <input type="checkbox" id="welcome-toggle" ${welcomeChecked} 
                                       onchange="toggleWelcome('welcome', this.checked)"
                                       style="opacity: 0; width: 0; height: 0;">
                                <span style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; 
                                             background: ${settings.welcome_enabled ? '#333' : '#2b2b2b'}; 
                                             transition: 0.2s; border: 1px solid ${settings.welcome_enabled ? '#2563eb' : '#444'};">
                                    <span style="position: absolute; height: 14px; width: 14px; left: ${settings.welcome_enabled ? '26px' : '4px'}; 
                                                 top: 3px; background: ${settings.welcome_enabled ? '#2563eb' : '#666'}; transition: 0.2s;"></span>
                                </span>
                            </label>
                        </div>
                        <div style="margin-bottom: 0.5rem;">
                            <span style="color: ${welcomeStatusColor}; font-weight: 500; font-size: 0.9rem;">${settings.welcome_enabled ? '已開啟' : '已關閉'}</span>
                        </div>
                        <div style="color: #666; font-size: 0.85rem;">
                            頻道：${settings.welcome_channel ? `<span style="color: #888;">#${settings.welcome_channel}</span>` : '<span style="color: #555;">未設定</span>'}
                        </div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1.25rem; border-left: 3px solid ${leaveStatusColor};">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                            <div style="color: #ccc; font-size: 0.95rem; font-weight: 500;">離開系統</div>
                            <label style="position: relative; display: inline-block; width: 44px; height: 22px; cursor: pointer;">
                                <input type="checkbox" id="leave-toggle" ${leaveChecked} 
                                       onchange="toggleWelcome('leave', this.checked)"
                                       style="opacity: 0; width: 0; height: 0;">
                                <span style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; 
                                             background: ${settings.leave_enabled ? '#333' : '#2b2b2b'}; 
                                             transition: 0.2s; border: 1px solid ${settings.leave_enabled ? '#2563eb' : '#444'};">
                                    <span style="position: absolute; height: 14px; width: 14px; left: ${settings.leave_enabled ? '26px' : '4px'}; 
                                                 top: 3px; background: ${settings.leave_enabled ? '#2563eb' : '#666'}; transition: 0.2s;"></span>
                                </span>
                            </label>
                        </div>
                        <div style="margin-bottom: 0.5rem;">
                            <span style="color: ${leaveStatusColor}; font-weight: 500; font-size: 0.9rem;">${settings.leave_enabled ? '已開啟' : '已關閉'}</span>
                        </div>
                        <div style="color: #666; font-size: 0.85rem;">
                            頻道：${settings.leave_channel ? `<span style="color: #888;">#${settings.leave_channel}</span>` : '<span style="color: #555;">未設定</span>'}
                        </div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('welcome-data').innerHTML = '<p style="color: #dc2626;">載入失敗</p>';
    }
}

// 切換歡迎系統開關
async function toggleWelcome(type, enabled) {
    try {
        const response = await fetch('/api/welcome/' + GUILD_ID + '/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: type,
                enabled: enabled
            })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                // 重新載入歡迎系統設定以更新UI
                loadWelcome();
                
                // 顯示成功提示
                const statusText = enabled ? '已開啟' : '已關閉';
                const typeText = type === 'welcome' ? '歡迎系統' : '離開系統';
                showNotification(`${typeText}${statusText}`, 'success');
            }
        } else {
            showNotification('設定更新失敗', 'error');
            // 恢復開關狀態
            loadWelcome();
        }
    } catch (error) {
        console.error('切換失敗:', error);
        showNotification('發生錯誤', 'error');
        // 恢復開關狀態
        loadWelcome();
    }
}

// 顯示通知
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 0.875rem 1.25rem;
        background: ${type === 'success' ? '#2563eb' : '#dc2626'};
        color: white;
        font-size: 0.9rem;
        font-weight: 500;
        border-left: 3px solid ${type === 'success' ? '#1d4ed8' : '#b91c1c'};
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    // 3秒後移除
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// 載入生日數據
async function loadBirthdays() {
    try {
        const response = await fetch('/api/data/' + GUILD_ID + '/birthdays');
        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('birthday-data');
            
            if (!data.exists || Object.keys(data.data).length === 0) {
                container.innerHTML = '<p style="color: #888;">暫無生日記錄</p>';
                return;
            }
            
            const birthdays = Object.keys(data.data).length;
            const currentMonth = new Date().getMonth() + 1;
            const thisMonth = Object.values(data.data).filter(bd => bd.month === currentMonth).length;
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">已登記生日</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${birthdays}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">本月壽星</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${thisMonth}</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('birthday-data').innerHTML = '<p style="color: #dc2626;">載入失敗</p>';
    }
}

// 載入遊戲統計
async function loadGames() {
    try {
        const response = await fetch('/api/data/' + GUILD_ID + '/game_stats');
        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('game-data');
            
            if (!data.exists || Object.keys(data.data).length === 0) {
                container.innerHTML = '<p style="color: #888;">暫無遊戲統計</p>';
                return;
            }
            
            // 計算統計
            const players = Object.keys(data.data).length;
            let totalGames = 0;
            let totalWins = 0;
            const gameTypes = {};
            
            Object.values(data.data).forEach(player => {
                totalGames += player.total_games || 0;
                totalWins += player.total_wins || 0;
                
                if (player.games) {
                    Object.entries(player.games).forEach(([game, stats]) => {
                        if (!gameTypes[game]) {
                            gameTypes[game] = { played: 0, won: 0 };
                        }
                        gameTypes[game].played += stats.played || 0;
                        gameTypes[game].won += stats.won || 0;
                    });
                }
            });
            
            const winRate = totalGames > 0 ? (totalWins / totalGames * 100) : 0;
            
            let gameTypesHtml = '';
            Object.entries(gameTypes).forEach(([name, stats]) => {
                const rate = stats.played > 0 ? (stats.won / stats.played * 100) : 0;
                gameTypesHtml += `
                    <div style="background: #1a1a1a; padding: 0.75rem; border-left: 3px solid #2563eb; margin-bottom: 0.5rem;">
                        <div style="color: #2563eb; font-weight: 600;">${name}</div>
                        <div style="font-size: 0.85rem; color: #888;">
                            ${stats.played} 場遊戲 | 勝率 ${rate.toFixed(1)}%
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1rem;">
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">遊戲玩家</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${players}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">總遊戲場次</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${totalGames.toLocaleString()}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">平均勝率</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${winRate.toFixed(1)}%</div>
                    </div>
                </div>
                <div style="margin-top: 1rem;">
                    <div style="color: #888; font-size: 0.9rem; margin-bottom: 0.5rem;">各遊戲統計</div>
                    ${gameTypesHtml || '<p style="color: #888;">暫無遊戲數據</p>'}
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('game-data').innerHTML = '<p style="color: #dc2626;">載入失敗</p>';
    }
}

// 載入伺服器統計
async function loadStatistics() {
    try {
        const response = await fetch('/api/data/' + GUILD_ID + '/statistics');
        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('statistics-data');
            
            if (!data.exists) {
                container.innerHTML = '<p style="color: #888;">暫無活躍度數據</p>';
                return;
            }
            
            const stats = data.data;
            const totalMessages = stats.total_messages || 0;
            
            // 計算今日訊息
            const today = new Date().toISOString().split('T')[0];
            const todayMessages = stats.daily_messages?.[today] || 0;
            
            // 找出最熱門頻道
            let topChannel = '暫無數據';
            let topChannelCount = 0;
            if (stats.channel_stats) {
                Object.entries(stats.channel_stats).forEach(([id, info]) => {
                    if (info.messages > topChannelCount) {
                        topChannelCount = info.messages;
                        topChannel = '#' + info.name;
                    }
                });
            }
            
            // 找出最活躍時段
            let peakHour = '暫無數據';
            let peakCount = 0;
            if (stats.hourly_activity) {
                Object.entries(stats.hourly_activity).forEach(([hour, count]) => {
                    if (count > peakCount) {
                        peakCount = count;
                        peakHour = hour + ':00';
                    }
                });
            }
            
            // 活躍用戶數
            const activeUsers = Object.keys(stats.user_stats || {}).length;
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1rem;">
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">總訊息數</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${totalMessages.toLocaleString()}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">今日訊息</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${todayMessages.toLocaleString()}</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem; border-left: 3px solid #2563eb;">
                        <div style="color: #888; font-size: 0.9rem;">活躍用戶</div>
                        <div style="font-size: 1.5rem; color: #2563eb; font-weight: 600;">${activeUsers}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    <div style="background: #1a1a1a; padding: 1rem;">
                        <div style="color: #888; font-size: 0.9rem; margin-bottom: 0.5rem;">最熱門頻道</div>
                        <div style="color: #2563eb; font-weight: 600;">${topChannel}</div>
                        <div style="color: #888; font-size: 0.85rem;">${topChannelCount.toLocaleString()} 條訊息</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 1rem;">
                        <div style="color: #888; font-size: 0.9rem; margin-bottom: 0.5rem;">最活躍時段</div>
                        <div style="color: #2563eb; font-weight: 600;">${peakHour}</div>
                        <div style="color: #888; font-size: 0.85rem;">${peakCount.toLocaleString()} 條訊息</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('statistics-data').innerHTML = '<p style="color: #dc2626;">載入失敗</p>';
    }
}

// 頁面載入時執行
loadStats();
loadLevels();
loadDaily();
loadWelcome();
loadBirthdays();
loadGames();
loadStatistics();

// 每30秒更新一次數據
setInterval(() => {
    loadStats();
    loadLevels();
    loadDaily();
    loadWelcome();
    loadBirthdays();
    loadGames();
    loadStatistics();
}, 30000);
