
import 'dotenv/config';
import { MongoClient } from 'mongodb';
import { createApp } from './app.js';

let client = null;
let collection = null;

const uri = process.env.MONGO_URI;
const dbName = process.env.MONGO_DB || 'monolith_observability';

if (uri) {
  try {
    client = new MongoClient(uri, {
      serverSelectionTimeoutMS: 5000,
      connectTimeoutMS: 5000,
      maxPoolSize: 5,
      retryWrites: true
    });

    await client.connect();
    await client.db('admin').command({ ping: 1 });

    collection = client
      .db(dbName)
      .collection('catalog_queries');

    await collection.createIndex(
      { at: 1 },
      { expireAfterSeconds: 60 * 60 * 24 * 30 }
    );

    console.log('MongoDB Atlas conectado correctamente');
    console.log(`Base de datos: ${dbName}`);
    console.log('Colección: catalog_queries');

  } catch (error) {
    console.warn(
      `MongoDB no disponible: ${error.message}`
    );

    await client?.close().catch(() => {});
    client = null;
    collection = null;
  }
} else {
  console.log(
    'MONGO_URI no configurada. Auditoría desactivada.'
  );
}

async function audit(event) {
  if (!collection) return;

  try {
    await collection.insertOne({
      ...event,
      at: new Date()
    });
  } catch (error) {
    console.warn(
      `No se pudo registrar auditoría: ${error.message}`
    );
  }
}

const port = Number(process.env.PORT || 4000);

const server = createApp({ audit }).listen(
  port,
  '0.0.0.0',
  () => {
    console.log(`Monolith Node.js activo en puerto ${port}`);
  }
);

async function shutdown() {
  console.log('Cerrando servicio Monolith...');

  server.close(async () => {
    try {
      await client?.close();
    } finally {
      process.exit(0);
    }
  });
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
