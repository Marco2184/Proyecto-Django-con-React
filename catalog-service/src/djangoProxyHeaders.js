export function djangoProxyHeaders(backendUrl) {
  const url = new URL(backendUrl);

  // Solo para la conexión privada Django-Node de este despliegue.
  if (url.protocol !== 'http:' ||
      url.hostname !== 'django' ||
      url.port !== '8000') {
    return {};
  }

  const origin = (process.env.ALLOWED_ORIGINS || '')
    .split(',')
    .map(value => value.trim())
    .find(value => value.startsWith('https://'));

  const host = new URL(origin || 'https://monolith-games.duckdns.org').host;

  return {
    Host: host,
    'X-Forwarded-Proto': 'https'
  };
}
