const CACHE_NAME = 'ficore-cache-v1';
const urlsToCache = [
    '/static/css/styles.css',
    '/static/js/scripts.js',
    '/static/js/interactivity.js',
    '/manifest.json',
    '/static/img/favicon.ico',
    '/static/img/apple-touch-icon.png',
    '/static/img/favicon-32x32.png',
    '/static/img/favicon-16x16.png'
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
                .catch(() => new Response('Offline: Resource not cached', { status: 503 }))
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
