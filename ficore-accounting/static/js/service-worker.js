const CACHE_NAME = 'ficore-cache-v1';
const urlsToCache = [
    '/static/styles/tailwind.min.css',
    '/manifest.json',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png'
];

// Routes that should always fetch from the network
const networkFirstRoutes = [
    '/users/login',
    '/users/logout',
    '/users/signup',
    '/users/forgot_password',
    '/users/reset_password',
    '/users/verify_2fa',
    '/'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    const requestUrl = new URL(event.request.url);

    // Use network-first strategy for authentication routes and index page
    if (networkFirstRoutes.some(route => requestUrl.pathname.startsWith(route))) {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(event.request))
        );
    } else {
        // Cache-first strategy for other resources
        event.respondWith(
            caches.match(event.request)
                .then(response => response || fetch(event.request))
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
