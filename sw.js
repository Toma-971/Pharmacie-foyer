/* Mode hors connexion : l'appli est gardée en cache sur le téléphone.
   Changer VERSION à chaque mise à jour pour que les téléphones la récupèrent. */
const VERSION='pharmacie-v7-1';
const SHELL=['./','index.html','manifest.webmanifest','icons/icon-192.png','icons/icon-512.png','icons/icon-maskable-512.png','icons/apple-touch-icon.png'];

self.addEventListener('install',e=>{
  e.waitUntil(caches.open(VERSION).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',e=>{
  const req=e.request;
  if(req.method!=='GET')return;
  const url=new URL(req.url);
  // Pages : réseau d'abord (pour recevoir les mises à jour), cache si hors connexion.
  if(req.mode==='navigate'){
    e.respondWith(fetch(req).then(r=>{
      const copy=r.clone();caches.open(VERSION).then(c=>c.put('index.html',copy));return r;
    }).catch(()=>caches.match('index.html')));
    return;
  }
  // Base des médicaments : la copie en cache tout de suite, mise à jour en arrière-plan.
  if(url.origin===location.origin&&url.pathname.indexOf('/data/')>=0){
    e.respondWith(caches.open(VERSION).then(c=>c.match(req).then(hit=>{
      const net=fetch(req).then(r=>{if(r.ok)c.put(req,r.clone());return r;}).catch(()=>hit||Response.error());
      if(hit){e.waitUntil(net);return hit;}
      return net;
    })));
    return;
  }
  // Polices Google et fichiers de l'appli : cache d'abord.
  if(url.origin===location.origin||url.host==='fonts.googleapis.com'||url.host==='fonts.gstatic.com'){
    e.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(r=>{
      if(r.ok||r.type==='opaque'){const copy=r.clone();caches.open(VERSION).then(c=>c.put(req,copy));}
      return r;
    })));
  }
});
