// ================================================================
// 🔔 SERVICE WORKER AURA — v6
// ✅ badge.png supprimé (causait un 404 qui bloquait le son)
// ✅ Tag unique → son à chaque notification
// ✅ silent:false → son activé
// ✅ Logs de débogage dans la console DevTools
// ================================================================

// ⚠️ Numéro augmenté → Chrome installe automatiquement cette version
const CACHE_NOM = 'aura-sw-v6';

self.addEventListener('install', () => {
    console.log('[SW] 🔧 Version installée : ' + CACHE_NOM);
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    console.log('[SW] ✅ Service Worker activé : ' + CACHE_NOM);
    e.waitUntil(self.clients.claim());
});

// ── Styles par type de notification ──────────────────────────────
const STYLES = {
    commande:        { vibrate: [300,100,300,100,600], requireInteraction: true  },
    confirmation:    { vibrate: [200,100,200],          requireInteraction: false },
    promo:           { vibrate: [100,50,100,50,300],    requireInteraction: false },
    nouveau_produit: { vibrate: [150,50,150],           requireInteraction: false },
    message:         { vibrate: [200,100,200],          requireInteraction: false },
    defaut:          { vibrate: [200,100,200],          requireInteraction: false },
};

// ── Actions par type ──────────────────────────────────────────────
const ACTIONS = {
    commande:        [{ action:'voir', title:'👀 Voir la commande' }, { action:'ignorer', title:'✕ Fermer' }],
    confirmation:    [{ action:'voir', title:'📦 Ma commande' }],
    promo:           [{ action:'voir', title:'🛒 Voir les promos' }, { action:'ignorer', title:'✕ Plus tard' }],
    nouveau_produit: [{ action:'voir', title:'🆕 Voir le produit' }],
    message:         [{ action:'voir', title:'💬 Lire' }],
    defaut:          [{ action:'voir', title:'👀 Voir' }],
};

// ── Réception push ────────────────────────────────────────────────
self.addEventListener('push', event => {
    console.log('[SW] 📩 Push reçu');

    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
            console.log('[SW] ✅ Données :', data);
        } catch(e) {
            data = { titre:'Aura', corps: event.data.text(), type:'defaut' };
            console.log('[SW] ⚠️ Texte brut :', data.corps);
        }
    } else {
        console.warn('[SW] ⚠️ Push sans données');
    }

    const titre = data.titre || '🛍️ Aura Markeplay';
    const corps  = data.corps  || 'Vous avez une nouvelle notification';
    const url    = data.url    || '/compte';
    const type   = data.type   || 'defaut';
    const style  = STYLES[type] || STYLES.defaut;

    // Tag UNIQUE à chaque push = son joué à chaque fois
    const tag = 'aura-' + type + '-' + Date.now() + '-' + Math.random().toString(36).slice(2,7);

    // Badge compteur
    const nb = data.badge_count || 0;
    if (nb > 0 && 'setAppBadge' in self.registration) {
        self.registration.setAppBadge(nb).catch(() => {});
    }

    const options = {
        body:               corps,
        icon:               '/static/img/logo.png',
        // ✅ badge supprimé — badge.png était introuvable (404)
        //    et ce 404 bloquait le son sur Android Chrome
        tag:                tag,
        renotify:           true,
        vibrate:            style.vibrate,
        requireInteraction: style.requireInteraction,
        silent:             false,   // SON ACTIVÉ — ne jamais mettre true
        actions:            ACTIONS[type] || ACTIONS.defaut,
        timestamp:          Date.now(),
        data:               { url, type, tag }
    };

    console.log('[SW] 🔔 Notification | type=' + type + ' | silent=false | tag=' + tag);

    event.waitUntil(
        self.registration.showNotification(titre, options)
            .then(() => {
                console.log('[SW] ✅ Notification affichée — son doit jouer !');
            })
            .catch(err => {
                console.error('[SW] ❌ ERREUR showNotification :', err.message);
            })
    );
});

// ── Clic notification ─────────────────────────────────────────────
self.addEventListener('notificationclick', event => {
    console.log('[SW] 👆 Clic — action :', event.action);
    event.notification.close();
    if (event.action === 'ignorer') return;

    const urlCible = (event.notification.data && event.notification.data.url)
        ? event.notification.data.url : '/compte';

    if ('clearAppBadge' in self.registration) {
        self.registration.clearAppBadge().catch(() => {});
    }

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(list => {
                for (const c of list) {
                    if ('focus' in c) {
                        c.focus();
                        if ('navigate' in c) c.navigate(urlCible);
                        return;
                    }
                }
                if (clients.openWindow) return clients.openWindow(urlCible);
            })
    );
});

// ── Message depuis la page (mise à jour badge) ────────────────────
self.addEventListener('message', event => {
    if (!event.data) return;
    if (event.data.type === 'MISE_A_JOUR_BADGE') {
        const nb = event.data.count || 0;
        if (nb > 0 && 'setAppBadge' in self.registration) {
            self.registration.setAppBadge(nb).catch(() => {});
        } else if ('clearAppBadge' in self.registration) {
            self.registration.clearAppBadge().catch(() => {});
        }
    }
    if (event.data.type === 'MESSAGES_LUS') {
        if ('clearAppBadge' in self.registration) {
            self.registration.clearAppBadge().catch(() => {});
        }
    }
});
