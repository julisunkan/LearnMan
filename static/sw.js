// Service Worker with NO CACHING - always fetch fresh content
// Caching removed to ensure fresh content loading as requested

self.addEventListener('install', function(event) {
  // Skip waiting to activate immediately
  self.skipWaiting();
});

self.addEventListener('fetch', function(event) {
  // Always fetch from network, no cache checking
  event.respondWith(
    fetch(event.request).catch(function(error) {
      console.log('Fetch failed, but no cache fallback:', error);
      throw error;
    })
  );
});

self.addEventListener('activate', function(event) {
  // Clear any existing caches
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          console.log('Deleting cache:', cacheName);
          return caches.delete(cacheName);
        })
      );
    }).then(function() {
      // Force refresh all clients
      return self.clients.matchAll().then(function(clients) {
        clients.forEach(function(client) {
          client.postMessage({ action: 'clearCache' });
        });
      });
    })
  );
  self.clients.claim();
});

// Add cache clearing message handler
self.addEventListener('message', function(event) {
  if (event.data && event.data.action === 'clearAllCaches') {
    event.waitUntil(
      caches.keys().then(function(cacheNames) {
        return Promise.all(
          cacheNames.map(function(cacheName) {
            console.log('Force deleting cache:', cacheName);
            return caches.delete(cacheName);
          })
        );
      }).then(function() {
        // Notify client that cache is cleared
        event.ports[0].postMessage({ success: true });
      })
    );
  }
});