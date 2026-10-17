import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const ECMWF_OUT = path.resolve(ROOT, 'engine/output');

function ecmwfStatic() {
  return (req, res, next) => {
    if (!req.url || !req.url.startsWith('/ecmwf/')) {
      return next();
    }
    const rel = decodeURIComponent(req.url.split('?')[0].slice('/ecmwf/'.length));
    const target = path.resolve(ECMWF_OUT, rel);
    const relToOut = path.relative(ECMWF_OUT, target);
    if (relToOut.startsWith('..') || path.isAbsolute(relToOut)) {
      res.statusCode = 403;
      res.end('Forbidden');
      return;
    }
    fs.stat(target, (err, st) => {
      if (err || !st.isFile()) {
        res.statusCode = 404;
        res.end('Not found');
        return;
      }
      const ext = path.extname(target).toLowerCase();
      const types = {
        '.webp': 'image/webp',
        '.json': 'application/json; charset=utf-8',
        '.png': 'image/png',
      };
      res.statusCode = 200;
      res.setHeader('Content-Type', types[ext] || 'application/octet-stream');
      res.setHeader(
        'Cache-Control',
        ext === '.json' ? 'no-cache' : 'public, max-age=86400'
      );
      res.setHeader('Access-Control-Allow-Origin', '*');
      fs.createReadStream(target).pipe(res);
    });
  };
}

export default defineConfig({
  plugins: [
    svelte(),
    {
      name: 'ecmwf-tiles',
      configureServer(server) {
        server.middlewares.use(ecmwfStatic());
      },
      configurePreviewServer(server) {
        server.middlewares.use(ecmwfStatic());
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
