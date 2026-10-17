import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const ECMWF_OUT = path.resolve(ROOT, 'engine/output');
const GFS_DATA = path.resolve(ROOT, 'data/gfs');
const GFS_TILES = path.resolve(GFS_DATA, 'tiles/gfs');
const GFS_NUM_TILES = path.resolve(GFS_DATA, 'tiles_numeric/gfs');
const ICON_TILES = path.resolve(ROOT, 'data/tiles/icon');
const ICON_NUM_TILES = path.resolve(ROOT, 'data/tiles_numeric/icon');

const TYPES = {
  '.webp': 'image/webp',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
};

const TRANSPARENT_WEBP = Buffer.from(
  '524946461a000000574542505650384c0e0000002f670000000488880800',
  'hex'
);

function sendJson(res, obj, status = 200) {
  const body = JSON.stringify(obj);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.end(body);
}

function sendFile(res, target, { missingWebp = false, cache } = {}) {
  fs.stat(target, (err, st) => {
    if (err || !st.isFile()) {
      if (missingWebp) {
        res.statusCode = 200;
        res.setHeader('Content-Type', 'image/webp');
        res.setHeader('Cache-Control', 'no-store');
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.end(TRANSPARENT_WEBP);
        return;
      }
      res.statusCode = 404;
      res.end('Not found');
      return;
    }
    const ext = path.extname(target).toLowerCase();
    const cacheHeader =
      cache || (ext === '.json' ? 'no-cache' : 'public, max-age=86400');
    res.statusCode = 200;
    res.setHeader('Content-Type', TYPES[ext] || 'application/octet-stream');
    res.setHeader('Cache-Control', cacheHeader);
    res.setHeader('Access-Control-Allow-Origin', '*');
    fs.createReadStream(target).pipe(res);
  });
}

function guarded(root, rel) {
  const target = path.resolve(root, rel);
  const relToOut = path.relative(root, target);
  if (relToOut.startsWith('..') || path.isAbsolute(relToOut)) return null;
  return target;
}

function nwpStatic() {
  return (req, res, next) => {
    if (!req.url) return next();
    const url = decodeURIComponent(req.url.split('?')[0]);

    if (url.startsWith('/ecmwf/')) {
      const target = guarded(ECMWF_OUT, url.slice('/ecmwf/'.length));
      if (!target) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      sendFile(res, target, { missingWebp: url.endsWith('.webp') });
      return;
    }

    if (url === '/api/gfs/latest') {
      sendFile(res, path.join(GFS_DATA, 'latest.json'));
      return;
    }
    if (url === '/api/gfs/runs') {
      fs.readdir(GFS_TILES, { withFileTypes: true }, (err, entries) => {
        const runs = (err ? [] : entries)
          .filter((e) => e.isDirectory())
          .map((e) => e.name)
          .sort()
          .reverse();
        sendJson(res, { runs });
      });
      return;
    }
    if (url.startsWith('/api/gfs/runs/') && url.endsWith('/manifest.json')) {
      const run = url.slice('/api/gfs/runs/'.length, -'/manifest.json'.length);
      const target = guarded(GFS_TILES, path.join(run, 'manifest.json'));
      if (!target) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      sendFile(res, target);
      return;
    }
    if (url.startsWith('/tiles/gfs/') && url.endsWith('.webp')) {
      const target = guarded(GFS_TILES, url.slice('/tiles/gfs/'.length));
      if (!target) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      sendFile(res, target, { missingWebp: true });
      return;
    }
    if (url.startsWith('/tiles/gfs-numeric/') && url.endsWith('.webp')) {
      const target = guarded(GFS_NUM_TILES, url.slice('/tiles/gfs-numeric/'.length));
      if (!target) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      sendFile(res, target, { missingWebp: true });
      return;
    }

    if (url === '/api/icon/manifest') {
      const latest = path.join(ICON_TILES, 'latest_manifest.json');
      fs.stat(latest, (err) => {
        if (!err) {
          sendFile(res, latest);
          return;
        }
        fs.readdir(ICON_TILES, { withFileTypes: true }, (dirErr, entries) => {
          const runs = (dirErr ? [] : entries)
            .filter((e) => e.isDirectory() && /^\d{10}$/.test(e.name))
            .map((e) => e.name)
            .sort()
            .reverse();
          if (!runs.length) {
            sendJson(res, { error: 'No ICON runs processed yet.' }, 404);
            return;
          }
          sendFile(res, path.join(ICON_TILES, runs[0], 'manifest.json'));
        });
      });
      return;
    }
    if (url.startsWith('/api/icon/tiles/') && url.endsWith('.webp')) {
      const target = guarded(ICON_TILES, url.slice('/api/icon/tiles/'.length));
      if (!target) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      sendFile(res, target, { missingWebp: true });
      return;
    }
    if (url.startsWith('/api/icon/tiles-numeric/') && url.endsWith('.webp')) {
      const target = guarded(ICON_NUM_TILES, url.slice('/api/icon/tiles-numeric/'.length));
      if (!target) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      sendFile(res, target, { missingWebp: true });
      return;
    }

    return next();
  };
}

export default defineConfig({
  plugins: [
    svelte(),
    {
      name: 'nwp-tiles',
      configureServer(server) {
        server.middlewares.use(nwpStatic());
      },
      configurePreviewServer(server) {
        server.middlewares.use(nwpStatic());
      },
    },
    {
      name: 'bmkg-proxy',
      configureServer(server) {
        // Direct REST endpoint: /api/proxy-satellite-tile/{z}/{x}/{y}.png?tiletype=...&modelname=...&param=...&baserun=...
        server.middlewares.use('/api/proxy-satellite-tile', async (req, res) => {
          try {
            const reqUrl = new URL(req.url, 'http://localhost');
            const targetUrl = `https://satellite.bmkg.go.id/api22/tile${reqUrl.pathname}${reqUrl.search}`;
            const upstream = await fetch(targetUrl, {
              headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://cuaca.bmkg.go.id/',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
              },
            });
            res.statusCode = upstream.status;
            res.setHeader('Content-Type', upstream.headers.get('content-type') || 'image/png');
            res.setHeader('Cache-Control', 'public, max-age=300');
            res.setHeader('Access-Control-Allow-Origin', '*');
            const arrayBuffer = await upstream.arrayBuffer();
            res.end(Buffer.from(arrayBuffer));
          } catch (e) {
            res.statusCode = 502;
            res.end(String(e));
          }
        });

        // Query param endpoint for verification
        server.middlewares.use('/api/proxy-satellite', async (req, res) => {
          try {
            const url = new URL(req.url, 'http://localhost');
            const targetUrl = url.searchParams.get('url');
            if (!targetUrl || !targetUrl.startsWith('https://satellite.bmkg.go.id/')) {
              res.statusCode = 400;
              res.end('Invalid url');
              return;
            }
            const upstream = await fetch(targetUrl, {
              headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://cuaca.bmkg.go.id/',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
              },
            });
            res.statusCode = upstream.status;
            res.setHeader('Content-Type', upstream.headers.get('content-type') || 'image/png');
            res.setHeader('Cache-Control', 'public, max-age=300');
            res.setHeader('Access-Control-Allow-Origin', '*');
            const arrayBuffer = await upstream.arrayBuffer();
            res.end(Buffer.from(arrayBuffer));
          } catch (e) {
            res.statusCode = 502;
            res.end(String(e));
          }
        });

        server.middlewares.use('/api/geocode', async (req, res) => {
          try {
            const url = new URL(req.url, 'http://localhost');
            const lat = Number(url.searchParams.get('lat'));
            const lon = Number(url.searchParams.get('lon'));
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
              res.statusCode = 400;
              res.end('Invalid lat/lon');
              return;
            }
            const targetUrl = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}&zoom=14&addressdetails=1`;
            const upstream = await fetch(targetUrl, {
              headers: {
                'User-Agent': 'metamorph-nwp/1.0 (nwp-geocoder)',
                Accept: 'application/json',
              },
            });
            res.statusCode = upstream.status;
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.setHeader('Cache-Control', 'public, max-age=86400');
            res.setHeader('Access-Control-Allow-Origin', '*');
            const arrayBuffer = await upstream.arrayBuffer();
            res.end(Buffer.from(arrayBuffer));
          } catch (e) {
            res.statusCode = 502;
            res.end(String(e));
          }
        });

        // SPARTAN fire-weather tiles (BMKG): /api/proxy-spartan-tile/{z}/{x}/{y}.png?product=fwi&start=YYYYMMDD0000&end=YYYYMMDD0000
        // Upstream pattern verified 2026-10-18: https://spartan.bmkg.go.id/map/rgb_req/spartan/{product}/0/{start}/{end}/{z}/{x}/{y}.png
        // Tiles are TMS (y origin at south), pre-coloured 4-class raster, aggregated over [start, end], max range 7 days.
        const SPARTAN_PRODUCTS = new Set(['ffmc', 'dmc', 'dc', 'isi', 'bui', 'fwi']);
        server.middlewares.use('/api/proxy-spartan-tile', async (req, res) => {
          try {
            const reqUrl = new URL(req.url, 'http://localhost');
            const m = reqUrl.pathname.match(/(\d+)\/(\d+)\/(\d+)\.png$/);
            const product = reqUrl.searchParams.get('product');
            const start = reqUrl.searchParams.get('start');
            const end = reqUrl.searchParams.get('end');
            if (
              !m ||
              !SPARTAN_PRODUCTS.has(product) ||
              !/^\d{12}$/.test(start || '') ||
              !/^\d{12}$/.test(end || '')
            ) {
              res.statusCode = 400;
              res.end('Invalid SPARTAN tile request');
              return;
            }
            const [, z, x, y] = m;
            const targetUrl = `https://spartan.bmkg.go.id/map/rgb_req/spartan/${product}/0/${start}/${end}/${z}/${x}/${y}.png`;
            const upstream = await fetch(targetUrl, {
              headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://spartan.bmkg.go.id/',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
              },
            });
            res.statusCode = upstream.status;
            res.setHeader('Content-Type', upstream.headers.get('content-type') || 'image/png');
            res.setHeader('Cache-Control', 'public, max-age=3600');
            res.setHeader('Access-Control-Allow-Origin', '*');
            const arrayBuffer = await upstream.arrayBuffer();
            res.end(Buffer.from(arrayBuffer));
          } catch (e) {
            res.statusCode = 502;
            res.end(String(e));
          }
        });

        server.middlewares.use('/api/proxy-cuaca', async (req, res) => {
          try {
            const url = new URL(req.url, 'http://localhost');
            const targetUrl = url.searchParams.get('url');
            if (!targetUrl || !targetUrl.startsWith('https://cuaca.bmkg.go.id/')) {
              res.statusCode = 400;
              res.end('Invalid url');
              return;
            }
            const upstream = await fetch(targetUrl, {
              headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://cuaca.bmkg.go.id/data/public/nwp-viewer/',
              },
            });
            res.statusCode = upstream.status;
            res.setHeader('Content-Type', upstream.headers.get('content-type') || 'application/json');
            res.setHeader('Cache-Control', 'public, max-age=60');
            res.setHeader('Access-Control-Allow-Origin', '*');
            const arrayBuffer = await upstream.arrayBuffer();
            res.end(Buffer.from(arrayBuffer));
          } catch (e) {
            res.statusCode = 502;
            res.end(String(e));
          }
        });
      },
    },
  ],
  server: {
    port: 5173,
    host: true,
  },
});
