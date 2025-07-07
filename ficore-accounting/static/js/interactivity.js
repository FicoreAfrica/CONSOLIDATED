document.addEventListener('DOMContentLoaded', function() {
    // Accordion Button Scroll Handler
    const accordionButtons = document.querySelectorAll('.accordion-button');
    accordionButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetSelector = this.getAttribute('data-bs-target');
            const target = document.querySelector(targetSelector);
            if (!target) {
                console.warn(`Accordion target not found: ${targetSelector}`);
                return;
            }
            if (target.classList.contains('show')) return;
            const offset = parseInt(this.getAttribute('data-scroll-offset')) || -60;
            const transitionDuration = parseFloat(getComputedStyle(target).transitionDuration) * 1000 || 300;
            setTimeout(() => {
                const y = target.getBoundingClientRect().top + window.scrollY + offset;
                window.scrollTo({ top: y, behavior: 'smooth' });
            }, transitionDuration);
        });
    });

    // Dark Mode Toggle (aligned with base.html)
    const modeToggle = document.getElementById('darkModeToggle');
    if (modeToggle) {
        const body = document.body;
        const icon = modeToggle.querySelector('i');
        const savedMode = localStorage.getItem('dark_mode');

        if (savedMode === 'true') {
            body.classList.add('dark-mode');
            icon.className = 'bi bi-sun fs-3';
            modeToggle.setAttribute('data-bs-title', '{{ t("general_mode_toggle_tooltip_switch_to_light", default="Switch to light mode") | e }}');
            modeToggle.setAttribute('aria-label', '{{ t("general_mode_toggle_light", default="Toggle light mode") | e }}');
        } else {
            body.classList.remove('dark-mode');
            icon.className = 'bi bi-moon-stars fs-3';
            modeToggle.setAttribute('data-bs-title', '{{ t("general_mode_toggle_tooltip_switch_to_dark", default="Switch to dark mode") | e }}');
            modeToggle.setAttribute('aria-label', '{{ t("general_mode_toggle_dark", default="Toggle dark mode") | e }}');
        }

        modeToggle.addEventListener('click', function() {
            body.classList.toggle('dark-mode');
            const isDarkMode = body.classList.contains('dark-mode');
            icon.className = isDarkMode ? 'bi bi-sun fs-3' : 'bi bi-moon-stars fs-3';
            modeToggle.setAttribute('data-bs-title', isDarkMode ? '{{ t("general_mode_toggle_tooltip_switch_to_light", default="Switch to light mode") | e }}' : '{{ t("general_mode_toggle_tooltip_switch_to_dark", default="Switch to dark mode") | e }}');
            modeToggle.setAttribute('aria-label', isDarkMode ? '{{ t("general_mode_toggle_light", default="Toggle light mode") | e }}' : '{{ t("general_mode_toggle_dark", default="Toggle dark mode") | e }}');
            localStorage.setItem('dark_mode', isDarkMode);
            const tooltip = bootstrap.Tooltip.getInstance(modeToggle);
            if (tooltip) tooltip.dispose();
            new bootstrap.Tooltip(modeToggle);
        });
    } else {
        console.warn('Dark mode toggle not found');
    }

    // Tools Link Navigation (handles dynamic tools-section)
    const toolsLink = document.getElementById('toolsLink');
    if (toolsLink) {
        toolsLink.addEventListener('click', function(event) {
            event.preventDefault();
            const toolsSection = document.getElementById('tools-section');
            if (toolsSection) {
                toolsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                toolsSection.setAttribute('tabindex', '-1');
                toolsSection.focus({ preventScroll: true });
                toolsSection.removeAttribute('tabindex');
            } else {
                console.warn('Tools section not found, checking for fallback navigation');
                // Fallback to first tool URL from context processor if available
                const firstToolLink = document.querySelector('a[href="https://financial-health-score-8jvu.onrender.com/inventory/"]');
                if (firstToolLink) {
                    window.location.href = firstToolLink.getAttribute('href');
                }
            }
        });
    }

    // Flash Message Confetti
    const flashMessages = document.querySelectorAll('.alert.alert-success');
    flashMessages.forEach(message => {
        const duration = 3 * 1000; // 3s duration
        const end = Date.now() + duration;
        const colors = ['#ff0a54', '#ff477e', '#ff7096', '#ff85a1', '#fbb1bd', '#f9bec7'];

        (function frame() {
            confetti({
                particleCount: 5,
                angle: 60,
                spread: 70,
                origin: { x: 0 },
                colors: colors
            });
            confetti({
                particleCount: 5,
                angle: 120,
                spread: 70,
                origin: { x: 1 },
                colors: colors
            });

            if (Date.now() < end) {
                requestAnimationFrame(frame);
            }
        })();
    });
});
```

<xaiArtifact artifact_id="de237c59-eb86-49e3-be47-3ba0e53aa47b" artifact_version_id="3ce5635c-8a14-4999-97b7-f62dc34fb3ce" title="service-worker.js" contentType="application/javascript">
```javascript
const CACHE_NAME = 'ficore-cache-v1';
const urlsToCache = [
    '/static/css/styles.css',
    '/static/js/scripts.js',
    '/static/js/interactivity.js',
    '/manifest.json',
    '/static/img/favicon.ico',
    '/static/img/apple-touch-icon.png',
    '/static/img/favicon-32x32.png',
    '/static/img/favicon-16x16.png',
    '/general/home' // Added for offline homepage access
];

const networkFirstRoutes = [
    '/users/login',
    '/users/logout',
    '/users/signup',
    '/users/forgot_password',
    '/users/reset_password',
    '/users/verify_2fa'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
            .catch(error => console.error('Cache installation failed:', error))
    );
});

self.addEventListener('fetch', event => {
    const requestUrl = new URL(event.request.url);

    if (networkFirstRoutes.some(route => requestUrl.pathname.startsWith(route))) {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(event.request))
                .catch(() => new Response('Offline: Unable to fetch resource', { status: 503 }))
        );
    } else {
        event.respondWith(
            caches.match(event.request)
                .then(response => response || fetch(event.request))
                .catch(() => caches.match('/general/home') || new Response('Offline: Resource not cached', { status: 503 }))
        );
    }
});

self.addEventListener('activate', event => {
    const cacheWhitelist = [CACHE_NAME];
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (!cacheWhitelist.includes(cacheName)) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});
