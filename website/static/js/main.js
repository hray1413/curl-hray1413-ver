// 導航欄漢堡選單
const hamburger = document.getElementById('hamburger');
const navbarMenu = document.getElementById('navbarMenu');

if (hamburger) {
    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('active');
        navbarMenu.classList.toggle('active');
    });

    // 點擊導航連結後關閉選單
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            hamburger.classList.remove('active');
            navbarMenu.classList.remove('active');
        });
    });

    // 點擊外部關閉選單
    document.addEventListener('click', (e) => {
        if (!hamburger.contains(e.target) && !navbarMenu.contains(e.target)) {
            hamburger.classList.remove('active');
            navbarMenu.classList.remove('active');
        }
    });
}

// 平滑滾動
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (href !== '#' && href.startsWith('#')) {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                const offsetTop = target.offsetTop - 70;
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        }
    });
});
