const { db } = require('./vector-teleport');

// Ensure tables support both distance metrics (cosine and L2)
db.prepare(`
  CREATE VIRTUAL TABLE IF NOT EXISTS vec_knn_cosine USING vec0(
    embedding FLOAT[384] distance_metric=cosine
  )
`).run();

db.prepare(`
  CREATE VIRTUAL TABLE IF NOT EXISTS vec_knn_l2 USING vec0(
    embedding FLOAT[384] distance_metric=l2
  )
`).run();

function searchKNN(queryVector, k = 5, metric = 'cosine') {
  const tableName = metric === 'l2' ? 'vec_knn_l2' : 'vec_knn_cosine';
  
  const stmt = db.prepare(`
    SELECT rowid, distance 
    FROM ${tableName} 
    WHERE embedding MATCH ? 
    ORDER BY distance 
    LIMIT ?
  `);

  return stmt.all(new Float32Array(queryVector), k);
}

module.exports = { searchKNN };
