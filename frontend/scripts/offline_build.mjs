/**
 * Cross-platform TypeScript + React bundler.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');

fs.rmSync(DIST, { recursive: true, force: true });
fs.mkdirSync(path.join(DIST, 'assets'), { recursive: true });

function compileFile(relPath) {
  const fullPath = path.join(ROOT, relPath);
  let source = fs.readFileSync(fullPath, 'utf-8');
  source = source.replace(/import\.meta/g, '({ env: window.__CONTINUITY_ENV__ || { VITE_API_MODE: "real", VITE_API_BASE_URL: "http://127.0.0.1:8000/api/v1" } })');
  const result = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React,
      esModuleInterop: true,
    },
    fileName: relPath,
  });
  return result.outputText;
}

const modules = {
  './src/api/generated/schema': '"use strict"; Object.defineProperty(exports, "__esModule", { value: true });',
  './src/api/client': compileFile('src/api/client.ts'),
  './src/api/realApi': compileFile('src/api/realApi.ts'),
  './src/api/mock/scenarios': compileFile('src/api/mock/scenarios.ts'),
  './src/api/mock/mockApi': compileFile('src/api/mock/mockApi.ts'),
  './src/components/StatusBadge': compileFile('src/components/StatusBadge.tsx'),
  './src/components/Legend': compileFile('src/components/Legend.tsx'),
  './src/components/EvidenceQuote': compileFile('src/components/EvidenceQuote.tsx'),
  './src/components/ErrorBanner': compileFile('src/components/ErrorBanner.tsx'),
  './src/components/EmptyState': compileFile('src/components/EmptyState.tsx'),
  './src/components/ConfirmDialog': compileFile('src/components/ConfirmDialog.tsx'),
  './src/components/Badge': compileFile('src/components/Badge.tsx'),
  './src/app/App': compileFile('src/app/App.tsx'),
  './src/main': compileFile('src/main.tsx'),
};

const reactUmd = fs.readFileSync(path.join(ROOT, 'node_modules/react/umd/react.production.min.js'), 'utf-8');
const reactDomUmd = fs.readFileSync(path.join(ROOT, 'node_modules/react-dom/umd/react-dom.production.min.js'), 'utf-8');
const lucideUmd = fs.readFileSync(path.join(ROOT, 'node_modules/lucide-react/dist/umd/lucide-react.min.js'), 'utf-8');

const bundleJs = `
window.__CONTINUITY_ENV__ = {
  VITE_API_MODE: "real",
  VITE_API_BASE_URL: "http://127.0.0.1:8000/api/v1"
};
${reactUmd}
window.react = window.React;
window.React.default = window.React;
window.React.__esModule = true;
${reactDomUmd}
window.ReactDOM.default = window.ReactDOM;
window.ReactDOM.__esModule = true;
${lucideUmd}
window.LucideReact.default = window.LucideReact;
window.LucideReact.__esModule = true;
(function() {
  const moduleRegistry = ${JSON.stringify(modules)};
  const cache = {};
  function resolvePath(fromMod, req) {
    if (req === 'react') return '__ext_react__';
    if (req === 'react-dom/client' || req === 'react-dom') return '__ext_react_dom__';
    if (req === 'lucide-react') return '__ext_lucide__';
    const baseDir = fromMod.split('/').slice(0, -1).join('/');
    const parts = (baseDir + '/' + req).split('/');
    const out = [];
    for (const p of parts) {
      if (p === '.' || p === '') continue;
      if (p === '..') out.pop();
      else out.push(p);
    }
    return './' + out.join('/');
  }
  function customRequire(fromMod, req) {
    const resolved = resolvePath(fromMod, req);
    if (resolved === '__ext_react__') return window.React;
    if (resolved === '__ext_react_dom__') return window.ReactDOM;
    if (resolved === '__ext_lucide__') return window.LucideReact;
    if (cache[resolved]) return cache[resolved].exports;
    const code = moduleRegistry[resolved] || '';
    const mod = { exports: {} };
    cache[resolved] = mod;
    const fn = new Function('exports', 'require', 'module', code);
    fn(mod.exports, (r) => customRequire(resolved, r), mod);
    return mod.exports;
  }
  customRequire('./src/main', './main');
})();
`;

fs.writeFileSync(path.join(DIST, 'assets', 'app.js'), bundleJs, 'utf-8');

const indexHtml = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Continuity AI — Evidence-First Project Knowledge Handover</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%234f46e5'/><text x='50%25' y='54%25' dominant-baseline='middle' text-anchor='middle' fill='white' font-family='sans-serif' font-weight='bold' font-size='18'>C</text></svg>" />
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-slate-100 text-slate-900 antialiased">
    <div id="root"></div>
    <script src="/assets/app.js"></script>
  </body>
</html>
`;
fs.writeFileSync(path.join(DIST, 'index.html'), indexHtml, 'utf-8');
console.log('[Continuity AI Build] Built production bundle in dist/index.html and dist/assets/app.js');
