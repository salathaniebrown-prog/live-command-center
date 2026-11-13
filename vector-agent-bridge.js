const { queryNearestTelemetry, insertVectorTelemetry } = require('./vector-teleport');

async function enrichAgentPrompt(promptText, queryEmbedding) {
  // Query top 3 nearest telemetry vectors using sqlite-vec
  const matches = queryNearestTelemetry(queryEmbedding, 3);
  const contextBlock = matches.map(m => `[Telemetry Match] ID: ${m.rowid} (Distance: ${m.distance.toFixed(4)})`).join('\n');
  
  return {
    systemPrompt: `You are Astra Core AI Agent operating within a sovereign Android telemetry environment.\nRelevant Context:\n${contextBlock}`,
    prompt: promptText
  };
}

module.exports = { enrichAgentPrompt };
