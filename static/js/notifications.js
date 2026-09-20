/* Notification popup */
(function () {
    function buildOverlay() {
        if (document.getElementById('notif-overlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'notif-overlay';
        overlay.className = 'notif-overlay';

        overlay.innerHTML = `
            <div class="notif-popup" role="dialog" aria-label="Notifications">
                <div class="notif-popup-header">
                    <h3>🔔 Notifications</h3>
                    <button class="notif-close-btn" id="notif-close-btn"
                            type="button" aria-label="Close">✕</button>
                </div>

                <div class="notif-popup-body" id="notif-popup-body"></div>
            </div>
        `;

        document.body.appendChild(overlay);

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeNotifPopup();
        });

        document
            .getElementById('notif-close-btn')
            .addEventListener('click', closeNotifPopup);
    }

    function closeNotifPopup() {
        const overlay = document.getElementById('notif-overlay');

        if (overlay) {
            overlay.classList.remove('open');
        }
    }

    function openNotifPopup() {
        buildOverlay();

        const overlay = document.getElementById('notif-overlay');
        overlay.classList.add('open');

        loadNotifications();
    }

    function loadNotifications() {
        const body = document.getElementById('notif-popup-body');

        body.innerHTML = `
            <a class="notif-item" href="/farm-planner">
                <div class="notif-item-top">
                    <span class="notif-badge">Farm Guide</span>
                </div>
                <div class="notif-item-title">Today’s Farm Guide</div>
                <p class="notif-item-desc">
                    Check today’s simple crop-care actions for your farm.
                </p>
            </a>

            <a class="notif-item" href="/crop-advisory">
                <div class="notif-item-top">
                    <span class="notif-badge">Crop Advisory</span>
                </div>
                <div class="notif-item-title">Crop Advisory Ready</div>
                <p class="notif-item-desc">
                    Get personalised crop recommendations for your land.
                </p>
            </a>

            <a class="notif-item" href="/farm-planner">
                <div class="notif-item-top">
                    <span class="notif-badge">Reminder</span>
                </div>
                <div class="notif-item-title">Check your farm tasks</div>
                <p class="notif-item-desc">
                    Review any farm actions you marked for tomorrow.
                </p>
            </a>

            <div class="notif-section-label">Latest Schemes</div>

            <div id="scheme-notifications">
                <div class="notif-loading">Loading latest schemes...</div>
            </div>
        `;

        fetch('/api/notifications/schemes')
            .then(function (res) {
                return res.json();
            })
            .then(function (schemes) {
                const schemeBox =
                    document.getElementById('scheme-notifications');

                if (!schemes || schemes.length === 0) {
                    schemeBox.innerHTML =
                        '<div class="notif-empty">No new schemes right now.</div>';
                    return;
                }

                schemeBox.innerHTML = schemes.map(function (s) {
                    return `
                        <a class="notif-item" href="/scheme/${s.id}">
                            <div class="notif-item-top">
                                <span class="notif-badge">${s.category}</span>
                            </div>
                            <div class="notif-item-title">${s.name}</div>
                            <p class="notif-item-desc">${s.overview}</p>
                        </a>
                    `;
                }).join('');
            })
            .catch(function () {
                document.getElementById('scheme-notifications').innerHTML =
                    '<div class="notif-empty">Could not load schemes. Try again.</div>';
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.js-notif-bell').forEach(function (btn) {
            btn.addEventListener('click', openNotifPopup);
        });
    });
})();