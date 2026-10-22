import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
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

function landslideProxy() {
  const origin = process.env.NWP_API_ORIGIN || 'http://127.0.0.1:8003';
  return async (req, res, next) => {
    if (!['/api/landslide/forecast/', '/api/flood/forecast/'].some((prefix) => req.url?.startsWith(prefix))) return next();
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      sendJson(res, { detail: 'Method not allowed' }, 405);
      return;
    }
    try {
      const response = await fetch(new URL(req.url, origin), { signal: AbortSignal.timeout(15000) });
      res.statusCode = response.status;
      res.setHeader('Content-Type', response.headers.get('content-type') || 'application/json');
      res.setHeader('Cache-Control', response.headers.get('cache-control') || 'no-store');
      res.end(req.method === 'HEAD' ? undefined : Buffer.from(await response.arrayBuffer()));
    } catch {
      sendJson(res, { detail: 'API indikator bencana belum tersedia. Jalankan backend FastAPI.' }, 503);
    }
  };
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
      const numeric = url.startsWith('/ecmwf/numeric/');
      sendFile(res, target, { missingWebp: url.endsWith('.webp') && !numeric });
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
      sendFile(res, target);
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
      sendFile(res, target);
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
        server.middlewares.use(landslideProxy());
        server.middlewares.use(nwpStatic());
      },
      configurePreviewServer(server) {
        server.middlewares.use(landslideProxy());
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
        // TMS raster: start is the fixed model run; end is the selected forecast date.
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
            if (upstream.ok) {
              res.setHeader('Cache-Control', 'public, max-age=3600');
            } else {
              res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
            }
            res.setHeader('Access-Control-Allow-Origin', '*');
            const arrayBuffer = await upstream.arrayBuffer();
            res.end(Buffer.from(arrayBuffer));
          } catch (e) {
            res.statusCode = 502;
            res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
            res.end(String(e));
          }
        });

        // BNPB InaRISK sebagai tile XYZ. Browser tidak boleh hit gis.bnpb.go.id
        // langsung (CORS), jadi proxy di sini.
        // Banjir: WMS 1.1.1 + SRS=EPSG:3857 (diverifikasi 2026-10-22, server terima
        // Web Mercator meski tidak diumumkan di GetCapabilities).
        // Longsor: service Float32 0-1 TANPA colormap, jadi WMS merendernya
        // grayscale nyaris hitam. Ambil TIFF mentah via exportImage lalu warnai
        // di sini: 0 = NoData (transparan), selainnya ramp kelas longsor app.
        const INARISK_WMS = {
          flood: 'inarisk/layer_kerentanan_banjir/ImageServer/WMSServer?LAYERS=layer_kerentanan_banjir',
        };
        const INARISK_EXPORT =
          'https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_KERENTANAN_TANAH_LONGSOR/ImageServer/exportImage';
        const BNPB_HEADERS = { 'User-Agent': 'metamorph-nwp/1.0', Accept: '*/*' };

        // Kelas sama dengan LANDSLIDE_LEVELS di LayerControl: Waspada / Siaga / Bahaya.
        function landslideColor(v) {
          if (v <= 0.333) return [0xea, 0xb3, 0x08, 200];
          if (v <= 0.666) return [0xf9, 0x73, 0x16, 210];
          return [0xdc, 0x26, 0x26, 220];
        }

        // PNG RGBA, filter None per baris, deflate. Cukup untuk tile ini.
        function encodePng(rgba, width = 256, height = 256) {
          const stride = width * 4;
          const raw = Buffer.alloc(height * (1 + stride));
          for (let row = 0; row < height; row++) {
            rgba.copy(raw, row * (1 + stride) + 1, row * stride, (row + 1) * stride);
          }
          const ihdr = Buffer.alloc(13);
          ihdr.writeUInt32BE(width, 0);
          ihdr.writeUInt32BE(height, 4);
          ihdr[8] = 8;
          ihdr[9] = 6;
          const chunk = (type, data) => {
            const len = Buffer.alloc(4);
            len.writeUInt32BE(data.length);
            const body = Buffer.concat([Buffer.from(type), data]);
            const crc = Buffer.alloc(4);
            crc.writeUInt32BE(zlib.crc32(body));
            return Buffer.concat([len, body, crc]);
          };
          return Buffer.concat([
            Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
            chunk('IHDR', ihdr),
            chunk('IDAT', zlib.deflateSync(raw)),
            chunk('IEND', Buffer.alloc(0)),
          ]);
        }

        // Tile yang memotong ekuator diambil sebagai dua TIFF 256x128
        // (utara lalu selatan) lalu digabung jadi satu PNG 256x256.
        function colorizeSplitTile(north, south) {
          const top = colorizeLandslideTiff(north, 256, 128);
          const bottom = colorizeLandslideTiff(south, 256, 128);
          const rgba = Buffer.alloc(256 * 256 * 4);
          top.copy(rgba, 0);
          bottom.copy(rgba, 256 * 128 * 4);
          return encodePng(rgba);
        }

        // TIFF dari exportImage: little-endian, Float32, 1 sampel, tanpa
        // kompresi, strip 128x128. Nilai tepat 0 = NoData.
        function colorizeLandslideTiff(buf, width = 256, height = 256) {
          if (buf.length < 8 || buf.readUInt16LE(0) !== 0x4949) {
            throw new Error('Bukan TIFF little-endian');
          }
          const ifd = buf.readUInt32LE(4);
          const count = buf.readUInt16LE(ifd);
          const tag = {};
          for (let i = 0; i < count; i++) {
            const e = ifd + 2 + 12 * i;
            tag[buf.readUInt16LE(e)] = {
              type: buf.readUInt16LE(e + 2),
              cnt: buf.readUInt32LE(e + 4),
              val: buf.readUInt32LE(e + 8),
            };
          }
          const need = [256, 257, 258, 259, 277, 339];
          if (
            need.some((t) => !tag[t]) ||
            tag[256].val !== width ||
            tag[257].val !== height ||
            tag[258].val !== 32 ||
            tag[259].val !== 1 ||
            tag[277].val !== 1 ||
            tag[339].val !== 3 ||
            !tag[324] ||
            !tag[325]
          ) {
            throw new Error('Layout TIFF longsor tak terduga');
          }
          const readLongs = (t) => {
            const out = [];
            const base = t.cnt === 1 ? null : t.val;
            for (let i = 0; i < t.cnt; i++) {
              out.push(base === null ? t.val : buf.readUInt32LE(base + 4 * i));
            }
            return out;
          };
          const offsets = readLongs(tag[324]);
          const lengths = readLongs(tag[325]);
          const rgba = Buffer.alloc(width * height * 4);
          // Tile 128x128 diisi baris-per-baris: tile 0 kiri-atas, 1 kanan-atas,
          // 2 kiri-bawah, 3 kanan-bawah. Tile kosong (byte count 0) = semua NoData.
          const tilesPerRow = width / 128;
          offsets.forEach((off, i) => {
            const len = lengths[i] || 0;
            if (!len) return;
            const col0 = (i % tilesPerRow) * 128;
            const row0 = Math.floor(i / tilesPerRow) * 128;
            for (let row = 0; row < 128; row++) {
              for (let col = 0; col < 128; col++) {
                const v = buf.readFloatLE(off + (row * 128 + col) * 4);
                if (!(v > 0)) continue;
                const [r, g, b, a] = landslideColor(v);
                const p = ((row0 + row) * width + col0 + col) * 4;
                rgba[p] = r;
                rgba[p + 1] = g;
                rgba[p + 2] = b;
                rgba[p + 3] = a;
              }
            }
          });
          return rgba;
        }
        server.middlewares.use('/api/proxy-inarisk-tile', async (req, res) => {
          try {
            const reqUrl = new URL(req.url, 'http://localhost');
            const m = reqUrl.pathname.match(/(\d+)\/(\d+)\/(\d+)\.png$/);
            if (!m) {
              res.statusCode = 400;
              res.end('Invalid InaRISK tile request');
              return;
            }
            const z = Number(m[1]);
            const x = Number(m[2]);
            const y = Number(m[3]);
            if (z > 12 || x >= 2 ** z || y >= 2 ** z) {
              res.statusCode = 400;
              res.end('Tile coordinate out of range');
              return;
            }
            const n = 2 ** z;
            const span = (20037508.342789244 * 2) / n;
            // ArcGIS Web Adaptor menolak BBOX dengan >1 desimal (HTTP 500),
            // jadi bulatkan ke bilangan bulat. Geser 0.5 m tidak terlihat di tile.
            const minx = Math.round(-20037508.342789244 + x * span);
            const maxx = Math.round(minx + span);
            const maxy = Math.round(20037508.342789244 - y * span);
            const miny = Math.round(maxy - span);
            const layerKey = reqUrl.searchParams.get('layer') === 'flood' ? 'flood' : 'landslide';
            // Header browser (Accept: image/*, Sec-Fetch-*) bikin ArcGIS Web Adaptor
            // balas 500; header minimal ala curl lolos. Diverifikasi 2026-10-22.
            // Server BNPB sesekali balas 500 di bawah beban paralel lalu pulih
            // sendiri, jadi ulang sekali sebelum menyerah.
            const fetchBnpb = async (url, init = {}) => {
              const opts = {
                ...init,
                headers: { ...BNPB_HEADERS, ...init.headers },
                signal: AbortSignal.timeout(45000),
              };
              let upstream = await fetch(url, opts);
              if (upstream.status >= 500) {
                await new Promise((resolve) => setTimeout(resolve, 1000));
                upstream = await fetch(url, opts);
              }
              return upstream;
            };
            res.setHeader('Access-Control-Allow-Origin', '*');
            if (layerKey === 'landslide') {
              // exportImage balas 500 bila bbox melewati ekuator (diverifikasi
              // 2026-10-22), jadi tile yang memotong y=0 dipecah dua.
              const spans = miny < 0 && maxy > 0
                ? [[minx, 0, maxx, maxy], [minx, miny, maxx, 0]]
                : [[minx, miny, maxx, maxy]];
              const parts = [];
              for (const [bx0, by0, bx1, by1] of spans) {
                const body = new URLSearchParams({
                  bbox: `${bx0},${by0},${bx1},${by1}`,
                  bboxSR: '102100',
                  imageSR: '102100',
                  size: spans.length === 1 ? '256,256' : '256,128',
                  format: 'tiff',
                  pixelType: 'F32',
                  f: 'image',
                });
                const upstream = await fetchBnpb(INARISK_EXPORT, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                  body,
                });
                if (!upstream.ok) {
                  res.statusCode = upstream.status;
                  res.setHeader('Cache-Control', 'no-store');
                  res.end(Buffer.from(await upstream.arrayBuffer()));
                  return;
                }
                parts.push(Buffer.from(await upstream.arrayBuffer()));
              }
              const png = spans.length === 1
                ? encodePng(colorizeLandslideTiff(parts[0]))
                : colorizeSplitTile(parts[0], parts[1]);
              res.statusCode = 200;
              res.setHeader('Content-Type', 'image/png');
              res.setHeader('Cache-Control', 'public, max-age=86400');
              res.end(png);
              return;
            }
            const targetUrl =
              `https://gis.bnpb.go.id/server/services/${INARISK_WMS.flood}` +
              `&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap` +
              `&STYLES=default&FORMAT=image/png&TRANSPARENT=TRUE&SRS=EPSG:3857` +
              `&WIDTH=256&HEIGHT=256&BBOX=${minx},${miny},${maxx},${maxy}`;
            const upstream = await fetchBnpb(targetUrl, {});
            res.statusCode = upstream.status;
            res.setHeader('Content-Type', upstream.headers.get('content-type') || 'image/png');
            res.setHeader('Cache-Control', upstream.ok ? 'public, max-age=86400' : 'no-store');
            res.end(Buffer.from(await upstream.arrayBuffer()));
          } catch (e) {
            res.statusCode = 502;
            res.setHeader('Cache-Control', 'no-store');
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
    watch: {
      ignored: ['**/data/**', '**/engine/output/**', '**/engine/.venv/**', '**/.claude/**'],
    },
  },
});
