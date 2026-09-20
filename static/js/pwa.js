/**
 * ANNADATA PWA — pwa.js
 * Handles: display-mode detection, install prompt,
 *          toast notifications, SW registration & updates
 */
(function () {
  'use strict';

  /* ── 1. Display-Mode Detection ─────────────────────────────── */
  function detectMode() {
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true ||
      document.referrer.startsWith('android-app://');

    if (isStandalone) {
      document.body.classList.add('pwa-app-mode');
      document.documentElement.setAttribute('data-pwa-mode', 'app');
    } else {
      document.body.classList.add('pwa-browser-mode');
      document.documentElement.setAttribute('data-pwa-mode', 'browser');
      // Show header install button if it exists
      const headerBtn = document.getElementById('header-install-btn');
      if (headerBtn) headerBtn.style.display = 'flex';
    }
  }

  /* ── 2. Install Prompt ─────────────────────────────────────── */
  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showInstallBanner();
  });

  window.addEventListener('appinstalled', function () {
    hideInstallBanner();
    showToast('✅ Annadata installed! Launch from your home screen.', 'success');
    deferredPrompt = null;
  });

  function showInstallBanner() {
    var banner = document.getElementById('pwa-install-banner');
    if (banner) {
      // Small delay so page is fully rendered first
      setTimeout(function () { banner.classList.add('visible'); }, 1500);
    }
  }

  function hideInstallBanner() {
    var banner = document.getElementById('pwa-install-banner');
    if (banner) banner.classList.remove('visible');
  }

  /* Public: called by install buttons */
  window.triggerInstall = function () {
    if (!deferredPrompt) {
      showToast('ℹ️ Open this site in Chrome on Android to install.', 'info');
      return;
    }
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(function (result) {
      if (result.outcome === 'accepted') {
        showToast('✅ Installing Annadata…', 'success');
      }
      deferredPrompt = null;
      hideInstallBanner();
    });
  };

  /* ── 3. Toast System ───────────────────────────────────────── */
  window.showToast = function (message, type, duration) {
    type = type || 'info';
    duration = duration || 3200;

    var container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    if (type === 'success') toast.style.borderLeftColor = '#5ca53d';
    if (type === 'error')   toast.style.borderLeftColor = '#e05555';
    if (type === 'warning') toast.style.borderLeftColor = '#f4b731';
    container.appendChild(toast);

    requestAnimationFrame(function () {
      requestAnimationFrame(function () { toast.classList.add('visible'); });
    });

    setTimeout(function () {
      toast.classList.remove('visible');
      setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 350);
    }, duration);
  };

  /* ── 4. Service Worker Registration ────────────────────────── */
  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;

    var swUrl = '/sw.js';

    navigator.serviceWorker.register(swUrl, { scope: '/' })
      .then(function (reg) {
        console.log('[Annadata SW] Registered, scope:', reg.scope);

        // Detect update available
        reg.addEventListener('updatefound', function () {
          var newWorker = reg.installing;
          if (!newWorker) return;
          newWorker.addEventListener('statechange', function () {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              showUpdateBanner();
            }
          });
        });
      })
      .catch(function (err) {
        console.warn('[Annadata SW] Registration failed:', err);
      });

    // Listen for controller change (after update)
    var refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', function () {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });
  }

  function showUpdateBanner() {
    var banner = document.getElementById('update-banner');
    if (banner) banner.classList.add('visible');
  }

  /* Public: called by update banner button */
  window.applyUpdate = function () {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistration().then(function (reg) {
        if (reg && reg.waiting) {
          reg.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
      });
    }
    window.location.reload();
  };

  /* ── 5. Page Transition ─────────────────────────────────────── */
  function initTransitions() {
    document.addEventListener('click', function (e) {
      var link = e.target.closest('a[href]');
      if (!link) return;
      var href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:') ||
          href.startsWith('mailto:') || link.target === '_blank') return;
      document.body.classList.add('page-transitioning');
    });

    window.addEventListener('pageshow', function (e) {
      if (e.persisted) {
        document.body.classList.remove('page-transitioning');
      }
    });
  }

  /* ── 6. Wire up DOM buttons ────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    // Install banner buttons
    var installBtn  = document.getElementById('pwa-install-btn');
    var dismissBtn  = document.getElementById('pwa-dismiss-btn');
    var headerBtn   = document.getElementById('header-install-btn');
    var fabBtn      = document.getElementById('pwa-fab-install');

    if (installBtn)  installBtn.addEventListener('click',  window.triggerInstall);
    if (dismissBtn)  dismissBtn.addEventListener('click',  hideInstallBanner);
    if (headerBtn)   headerBtn.addEventListener('click',   window.triggerInstall);
    if (fabBtn)      fabBtn.addEventListener('click',      window.triggerInstall);

    initTransitions();
  });

  /* ── Init ───────────────────────────────────────────────────── */
  detectMode();
  registerServiceWorker();

})();
