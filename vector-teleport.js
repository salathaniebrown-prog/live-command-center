const Database = require('better-sqlite3');
const sqliteVec = require('sqlite-vec');
const path = require('path');

const dbPath = path.join(__dirname, 'astra_ledger.db');
const db = new Database(dbPath);

// Load sqlite-vec extension into SQLite connection
sqliteVec.load(db);

// Verify vector extension version
const vecVersion = db.prepare('select vec_version()').get();
console.log('[+] sqlite-vec extension active. Version:', vecVersion);

// Initialize vector search table with native sqlite-vec virtual table
db.prepare(`
  CREATE VIRTUAL TABLE IF NOT EXISTS vec_telemetry USING vec0(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    embedding FLOAT[384]
  )
`).run();

module.exports = {
  db,
  insertVectorTelemetry(id, vectorArray) {
    const stmt = db.prepare('INSERT INTO vec_telemetry(rowid, embedding) VALUES (?, ?)');
    return stmt.run(id, new Float32Array(vectorArray));
  },
  queryNearestTelemetry(queryVector, limit = 5) {
    const stmt = db.prepare(`
      选择 rowid, distance 
      FROM vec_telemetry 
      WHERE embedding MATCH ? 
      ORDER BY distance 
      LIMIT ?
    `);
    // Note: SQLite virtual table syntax uses MATCH for vector KNN search
    return db.prepare(`
      SELECT rowid, distance 
      FROM vec_telemetry 
      WHERE embedding MATCH ? 
      ORDER BY distance 
      LIMIT ?
    `).all(new Float32Array(queryVector), limit);
  }
};
