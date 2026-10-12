
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import cookieParser from 'cookie-parser';
import { authRouter } from './auth.js';

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

  app.disable('x-powered-by');
  app.use(helmet());
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

  async function forward(req, res) {
    const pathname = req.path.endsWith('/')
      ? req.path
      : `${req.path}/`;

    const isProductDetail = /^\/api\/productos\/\d+\/$/.test(pathname);

    if (!paths.has(pathname) && !isProductDetail) {
      return res.status(404).json({
        error: 'Ruta no encontrada'
      });
    }

    // Los productos y su stock siempre se consultan en Django.
    // Solo las categorías y plataformas pueden utilizar caché.
    const canCache = (
      pathname === '/api/plataformas/' ||
      pathname === '/api/categorias/'
    );

    const backend = backendUrl.replace(/\/+$/, '');

    const backendPath = pathname.replace(/^\/api/, '');

    const url = new URL(backend + backendPath);

    const incomingUrl = new URL(
      req.originalUrl,
      'http://localhost'
    );

    url.search = incomingUrl.search;

    const key = url.toString();

    if (canCache && cacheTtlMs > 0) {
      const cached = cache.get(key);

      if (cached && cached.until > Date.now()) {
        res.set('X-Catalog-Cache', 'HIT');
        res.set('Cache-Control', 'no-store');

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

    try {
      const upstream = await fetchImpl(url.toString(), {
        signal: controller.signal,
        headers: {
          Accept: 'application/json'
        },
        cache: 'no-store'
      });

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
      res.set('Cache-Control', 'no-store');

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

  return app;
}
