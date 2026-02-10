// select_server.js - 伺服器選擇頁面

async function loadGuilds() {
    try {
        const response = await fetch('/api/guilds');
        if (!response.ok) {
            throw new Error('載入失敗');
        }
        
        const data = await response.json();
        const guilds = data.guilds;
        
        document.getElementById('loading').style.display = 'none';
        
        if (guilds.length === 0) {
            document.getElementById('no-guilds').style.display = 'block';
            return;
        }
        
        const guildsContainer = document.getElementById('guilds');
        guildsContainer.style.display = 'grid';
        
        guilds.forEach(guild => {
            const card = document.createElement('a');
            card.className = 'guild-card';
            card.href = `/dashboard/${guild.id}`;
            
            const icon = guild.icon 
                ? `<img src="${guild.icon}" alt="${guild.name}">`
                : guild.name.charAt(0).toUpperCase();
            
            card.innerHTML = `
                <div class="guild-header">
                    <div class="guild-icon">${icon}</div>
                    <div class="guild-info">
                        <div class="guild-name">${guild.name}</div>
                        <div class="guild-members">${guild.member_count.toLocaleString()} 位成員</div>
                    </div>
                </div>
                <span class="guild-badge">有管理權限</span>
            `;
            
            guildsContainer.appendChild(card);
        });
        
    } catch (error) {
        document.getElementById('loading').style.display = 'none';
        const errorDiv = document.getElementById('error');
        errorDiv.className = 'error';
        errorDiv.textContent = '載入伺服器列表時發生錯誤：' + error.message;
        errorDiv.style.display = 'block';
    }
}

// 頁面載入時執行
loadGuilds();
