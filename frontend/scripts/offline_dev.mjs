/**
 * Zero-dependency HTTP dev & preview server on port 5173 serving the compiled Continuity AI frontend
 * (from frontend/dist) and proxying /api/* and /health to http://127.0.0.1:8000.
 * Works out-of-the-box with zero node_modules required.
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');
const PORT = Number(process.env.PORT || 5173);

// Only run offline_build.mjs if typescript is installed in node_modules or dist/ is missing
if (fs.existsSync(path.join(ROOT, 'node_modules', 'typescript')) && !fs.existsSync(path.join(DIST, 'assets', 'app.js'))) {
  await import('./offline_build.mjs');
}

const server = http.createServer((req, res) => {
  const url = req.url || '/';
  if (url.startsWith('/api/') || url === '/health') {
    const proxyReq = http.request(
      `http://127.0.0.1:8000${url}`,
      { method: req.method, headers: req.headers },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
        proxyRes.pipe(res);
      }
    );
    proxyReq.on('error', (err) => {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({
          error: {
            code: 'INTERNAL_ERROR',
            message: err.message,
            details: null,
            request_id: 'proxy_err',
          },
        })
      );
    });
    req.pipe(proxyReq);
    return;
  }

  const cleanUrl = url.split('?')[0];
  const filePath =
    cleanUrl === '/' || !cleanUrl.includes('.')
      ? path.join(DIST, 'index.html')
      : path.join(DIST, cleanUrl.replace(/^\/+/, ''));

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath);
    const mime =
      ext === '.js'
        ? 'application/javascript; charset=utf-8'
        : ext === '.css'
        ? 'text/css; charset=utf-8'
        : 'text/html; charset=utf-8';
    res.writeHead(200, { 'Content-Type': mime });
    fs.createReadStream(filePath).pipe(res);
  } else {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    fs.createReadStream(path.join(DIST, 'index.html')).pipe(res);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(
    `Continuity AI Frontend listening on http://127.0.0.1:${PORT} (VITE_API_MODE=real -> http://localhost:8000/api/v1)`
  );
});
