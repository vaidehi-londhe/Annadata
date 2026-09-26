/* ===========================
   Side menu drawer: Home, Crop,
   Schemes, Learn, Sathi, Profile, Logout
   =========================== */
(function () {
    const LINKS = [
        { label: 'Home',    icon: 'fa-house',       href: '/dashboard' },
        { label: 'Crop',    icon: 'fa-seedling',    href: '/crop-advisory' },
        { label: 'Schemes', icon: 'fa-file-lines',  href: '/schemes' },
        { label: 'Learn',   icon: 'fa-book',        href: '/learn' },
        { label: 'Sathi',   icon: 'fa-robot',       href: '/sathi' },
        { label: 'Profile', icon: 'fa-user',        href: '/profile' }
    ];

    function buildOverlay() {
        if (document.getElementById('side-menu-overlay')) return;

        const currentPath = window.location.pathname;

        const linksHtml = LINKS.map(function (l) {
            const active = currentPath.startsWith(l.href) ? ' active' : '';
            return `<a class="${active.trim()}" href="${l.href}">
                        <i class="fa-solid ${l.icon}"></i>
                        <span>${l.label}</span>
                    </a>`;
        }).join('');

        const overlay = document.createElement('div');
        overlay.id = 'side-menu-overlay';
        overlay.className = 'side-menu-overlay';
        overlay.innerHTML = `
            <div class="side-menu-panel" role="dialog" aria-label="Menu">
                <div class="side-menu-header">
                    <div class="brand">🌿 Annadata</div>
                    <button class="side-menu-close-btn" id="side-menu-close-btn" type="button" aria-label="Close">✕</button>
                </div>
                <nav class="side-menu-links">${linksHtml}</nav>
                <div class="side-menu-footer">
                    <a href="/logout">
                        <i class="fa-solid fa-right-from-bracket"></i>
                        <span>Logout</span>
                    </a>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeSideMenu();
        });
        document.getElementById('side-menu-close-btn').addEventListener('click', closeSideMenu);
    }

    function closeSideMenu() {
        const overlay = document.getElementById('side-menu-overlay');
        if (overlay) overlay.classList.remove('open');
    }

    function openSideMenu() {
        buildOverlay();
        document.getElementById('side-menu-overlay').classList.add('open');
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.js-menu-btn').forEach(function (btn) {
            btn.addEventListener('click', openSideMenu);
        });
    });
})();