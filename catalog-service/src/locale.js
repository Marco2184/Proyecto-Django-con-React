const english = {"No se pudo consultar el cat\u00e1logo de Django":"The catalog server could not be reached","JSON inválido.": "Invalid JSON.", "Solicitud demasiado grande.": "Request is too large.", "Error interno del servicio.": "Internal service error.", "No se pudo contactar al backend Django": "The catalog server could not be reached", "Tiempo de espera agotado al consultar Django": "The catalog request timed out",
  "Origen no permitido.": "Origin not allowed.",
  "Correo y contraseña inválidos.": "Invalid email address or password.",
  "Correo y contraseña obligatorios.": "Email and password are required.",
  "Demasiados intentos. Espera un minuto.": "Too many attempts. Please wait a minute.",
  "Credenciales inválidas o cuenta inactiva.": "Invalid credentials or inactive account.",
  "No se pudo contactar el backend Django.": "The authentication server could not be reached.",
  "Revisa nombre, correo y contraseñas (mínimo 8 caracteres).": "Check your name, email and passwords (at least 8 characters).",
  "No se pudo registrar el usuario en Django.": "Your account could not be created.",
  "Sesión expirada.": "Your session has expired.",
  "Sesión expirada o revocada.": "Your session has expired or been revoked.",
  "Autenticación temporalmente no disponible.": "Authentication is temporarily unavailable.",
  "No se pudo revocar la sesión.": "Your session could not be revoked.",
  "Sesión cerrada.": "Signed out.",
  "Sesiones cerradas.": "Signed out of all sessions.",
  "ID de producto inválido": "Invalid product ID",
  "Ruta no encontrada": "Route not found",
  "El backend devolvió un formato inesperado": "The server returned an unexpected format"
};
english['Identificador de registro inv\u00e1lido.']='Invalid registration identifier.';
export function language(req) { return /^en(?:[-,;]|$)/i.test(req.get('accept-language') || '') ? 'en' : 'es'; }
export function localize(req, text) {return language(req) === 'en' ? english[text] || text : text;}
export function localeResponses(req,res,next) {
  const send=res.json.bind(res);
  res.json=body=>{
    if(body && typeof body==='object' && !Array.isArray(body)) {
      body={...body};
      for(const key of ['detail','error','message']) if(typeof body[key]==='string') body[key]=localize(req,body[key]);
    }
    res.set('Content-Language',language(req));res.vary('Accept-Language');
    return send(body);
  };next();
}
