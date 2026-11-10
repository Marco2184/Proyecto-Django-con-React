import { createCoalescedFetch } from './singleFlight.js';
import { djangoProxyHeaders } from './djangoProxyHeaders.js';
import {localeResponses, language} from './locale.js';

import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import cookieParser from 'cookie-parser';
import { authRouter } from './auth.js';
import { assistantRouter } from './assistant/router.js';

const paths = new Set([
  '/api/productos/',
  '/api/productos/buscar/',
  '/api/plataformas/',
  '/api/categorias/'
]);

const safeInt = (value, fallback) => {
  if (value === undefined || value === null || value === '') {
    return fallback;
  }

  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
};

export function createApp({
  backendUrl = process.env.DJANGO_API_URL || 'http://127.0.0.1:8000/api',
  allowedOrigins = process.env.ALLOWED_ORIGINS || 'http://localhost:3000,http://127.0.0.1:3000',
  fetchImpl = fetch,
  cacheTtlMs = safeInt(process.env.CACHE_TTL_MS, 45000),
  audit = async () => {},
} = {}) {
  const app = express();

  const origins = allowedOrigins
    .split(',')
    .map(origin => origin.trim())
    .filter(Boolean);

  const cache = new Map();
  const sharedFetch = createCoalescedFetch();

  app.disable('x-powered-by');
  app.use(helmet());
  app.use(localeResponses);
  app.use(express.json({ limit: '16kb' }));
  app.use(cookieParser());

  app.use(cors({
    credentials: true,
    origin(origin, callback) {
      callback(null, !origin || origins.includes(origin));
    }
  }));

  if (
    process.env.JWT_SHARED_SECRET &&
    process.env.JWT_REFRESH_SECRET
  ) {
    app.use('/auth', authRouter({ fetchImpl }));
  }

  app.get('/health', (_req, res) => {
    res.json({
      status: 'ok',
      service: 'monolith-catalog',
      upstream: 'django'
    });
  });

  app.use('/assistant',assistantRouter({backendUrl,fetchImpl,allowedOrigins}));

  async function forward(req, res) {
    const pathname = req.path.endsWith('/')
      ? req.path
      : `${req.path}/`;

    const isProductDetail = /^\/api\/productos\/\d+\/$/.test(pathname);

    if (/^\/api\/productos\/[^/]+\/$/.test(pathname) && !isProductDetail && pathname !== '/api/productos/buscar/') {
      return res.status(400).json({ error: 'ID de producto inválido' });
    }

    if (!paths.has(pathname) && !isProductDetail) {
      return res.status(404).json({
        error: 'Ruta no encontrada'
      });
    }

    // Cache breve de listados públicos anónimos.
    // Las compras y operaciones de stock siguen en Django.
    const publicProductList = (
      pathname === '/api/productos/' &&
      !req.headers.authorization &&
      !req.headers.cookie &&
      !req.headers['x-api-key']
    );

    const canCache = (
      pathname === '/api/plataformas/' ||
      pathname === '/api/categorias/' ||
      publicProductList
    );

    const backend = backendUrl.replace(/\/+$/, '');

    const backendPath = pathname.replace(/^\/api/, '');

    const url = new URL(backend + backendPath);

    const incomingUrl = new URL(
      req.originalUrl,
      'http://localhost'
    );

    url.search = incomingUrl.search;

    const key = language(req) + ':' + url.toString();

    if (canCache && cacheTtlMs > 0) {
      const cached = cache.get(key);

      if (cached && cached.until > Date.now()) {
        res.set('X-Catalog-Cache', 'HIT');
        res.set(
          'Cache-Control',
          canCache &&
          !req.headers.authorization &&
          !req.headers.cookie &&
          !req.headers['x-api-key']
            ? 'public, max-age=2'
            : 'no-store'
        );

        return res
          .status(cached.status)
          .json(cached.body);
      }

      if (cached) {
        cache.delete(key);
      }
    }

    const controller = new AbortController();

    const timer = setTimeout(() => {
      controller.abort();
    }, 8000);

    const upstreamStartedAt = performance.now();
    try {
      const getUpstream = () => fetchImpl(url.toString(), {
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          'Accept-Language': language(req),
          ...djangoProxyHeaders(backendUrl)
        },
        cache: 'no-store'
      });

      const upstream = await (
        canCache && cacheTtlMs > 0
          ? sharedFetch(key, getUpstream)
          : getUpstream()
      );

      const upstreamMs = performance.now() - upstreamStartedAt;

      if (process.env.MONOLITH_PERF_LOG === '1' &&
          upstreamMs >= 750 && Math.random() < 0.1) {
        console.log(JSON.stringify({
          event: 'catalog_upstream_slow',
          route: pathname,
          status: upstream.status,
          duration_ms: Math.round(upstreamMs)
        }));
      }

      const type = upstream.headers.get('content-type') || '';

      if (!type.includes('application/json')) {
        return res.status(502).json({
          error: 'El backend devolvió un formato inesperado'
        });
      }

      const body = await upstream.json();

      if (
        upstream.ok &&
        canCache &&
        cacheTtlMs > 0
      ) {
        if (cache.size > 500) {
          cache.clear();
        }

        cache.set(key, {
          body,
          status: upstream.status,
          until: Date.now() + cacheTtlMs
        });
      }

      res.set('X-Catalog-Cache', 'BYPASS');
      res.set(
          'Cache-Control',
          canCache &&
          !req.headers.authorization &&
          !req.headers.cookie &&
          !req.headers['x-api-key']
            ? 'public, max-age=2'
            : 'no-store'
        );

      res.status(upstream.status).json(body);

      Promise.resolve()
        .then(() => audit({
          path: pathname,
          query: req.query,
          status: upstream.status,
          at: new Date()
        }))
        .catch(() => {});

    } catch (err) {
      if (process.env.MONOLITH_PERF_LOG === '1') {
        console.warn(JSON.stringify({
          event: 'catalog_upstream_error',
          route: pathname,
          duration_ms: Math.round(performance.now() - upstreamStartedAt),
          error: err?.name || 'Error',
          cause_code: err?.cause?.code || null,
          cause_name: err?.cause?.name || null
        }));
      }

      if (!res.headersSent) {
        res.status(502).json({
          error: 'No se pudo consultar el catálogo de Django'
        });
      }

    } finally {
      clearTimeout(timer);
    }
  }

  app.get('/api/productos', forward);
  app.get('/api/productos/', forward);

  app.get('/api/productos/buscar', forward);
  app.get('/api/productos/buscar/', forward);

  app.get('/api/productos/:id', forward);
  app.get('/api/productos/:id/', forward);

  app.get('/api/plataformas', forward);
  app.get('/api/plataformas/', forward);

  app.get('/api/categorias', forward);
  app.get('/api/categorias/', forward);

  app.use((_req, res) => {
    res.status(404).json({
      error: 'Ruta no encontrada'
    });
  });

  app.use((error, _req, res, _next) => {
    const status = error?.status === 413 ? 413 : error?.type === 'entity.parse.failed' ? 400 : 500;
    res.status(status).json({detail: status === 400 ? 'JSON inválido.' : status === 413 ? 'Solicitud demasiado grande.' : 'Error interno del servicio.'});
  });
  return app;
}
