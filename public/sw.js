// Service worker: l'app funziona anche offline (il firmware si scarica solo quando serve)
const VERSION = 'esp32lab-v20';
const SHELL = [
  './',
  'board/main.py',
  'board/projects/p01_blink.py',
  'board/projects/p02_rgb.py',
  'board/projects/p03_dimmer.py',
  'board/projects/p04_button.py',
  'board/projects/p05_buzzer.py',
  'board/projects/p06_pot.py',
  'board/projects/p07_light.py',
  'board/projects/p08_dht.py',
  'board/projects/p09_distance.py',
  'board/projects/p10_joystick.py',
  'board/projects/p11_ir.py',
  'board/projects/p12_servo.py',
  'board/projects/p13_radar.py',
  'board/projects/p14_dcmotor.py',
  'board/projects/p15_stepper.py',
  'board/projects/p16_matrix.py',
  'board/projects/p17_webled.py',
  'board/projects/p18_meteo.py',
  'board/projects/p19_clock.py',
  'board/projects/p20_photo.py',
  'board/projects/p21_stream.py',
  'board/projects/p22_pancam.py',
  'board/projects/p23_car.py',
  'board/projects/p24_autocar.py',
  'board/projects/p25_fpvcar.py',
  'board/projects/x_line.py',
  'board/projects/x_mpu6050.py',
  'board/projects/x_oled.py',
  'board/projects/x_pir_cam.py',
  'board/projects/x_irrigazione.py',
  'board/projects/x_ring.py',
  'css/app.css',
  'icons/icon-192.png',
  'icons/icon.svg',
  'index.html',
  'js/app.js',
  'js/conn.js',
  'js/diagram.js',
  'js/flash.js',
  'js/native.js',
  'js/projects.js',
  'js/widgets.js',
  'manifest.webmanifest',
  'vendor/esptool.js',
  'vendor/serial-polyfill.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// rete prima (cosi' gli aggiornamenti da GitHub arrivano subito), cache se offline
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  if (new URL(req.url).pathname.startsWith('/api/')) return;   // ponte Internet: mai in cache
  e.respondWith(
    fetch(req).then((res) => {
      if (res.ok && !req.url.endsWith('.bin')) {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy));
      }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then((r) => r || caches.match('./'))),
  );
});
