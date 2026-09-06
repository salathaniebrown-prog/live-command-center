'use strict';
const express = require('express');
const os = require('os');
const mqtt = require('mqtt');
const { Pool } = require('pg');
const app = express();
const PORT = Number(process.env.PORT) || 3000;
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const client = mqtt.connect(process.env.MQTT_URL || 'mqtt://mqtt:1883');
app.disable('x-powered-by');
app.use(express.json({limit:'256kb'}));
client.on('connect', () => client.subscribe('eagle-eyes/telemetry/+'));
client.on('message', async (topic, buf) => {
  try {
    const p = JSON.parse(buf.toString());
    const nodeId = topic.split('/').pop();
    await pool.query('INSERT INTO telemetry(time,node_id,latitude,longitude,altitude_m,payload) VALUES(COALESCE($1,NOW()),$2,$3,$4,$5,$6)', [p.time || null,nodeId,p.latitude ?? null,p.longitude ?? null,p.altitude_m ?? null,p]);
  } catch (e) { console.error('telemetry ingest failed:', e.message); }
});
app.get('/api/health', async (_req,res) => {
  try { await pool.query('SELECT 1'); res.json({ok:true,database:true,mqtt:client.connected,uptimeSeconds:Math.floor(process.uptime()),time:new Date().toISOString()}); }
  catch { res.status(503).json({ok:false,database:false,mqtt:client.connected}); }
});
app.get('/api/metrics', (_req,res) => {
  const total=os.totalmem(), used=total-os.freemem();
  res.json({cpuCores:os.cpus().length,memoryPercent:Number((used/total*100).toFixed(1)),loadAverage:os.loadavg(),hostname:os.hostname(),source:'power-blueprint-node',timestamp:new Date().toISOString()});
});
app.get('/api/telemetry/latest', async (_req,res) => {
  try { const r=await pool.query('SELECT time,node_id,latitude,longitude,altitude_m,payload FROM telemetry ORDER BY time DESC LIMIT 100'); res.json(r.rows); }
  catch { res.status(500).json({ok:false,error:'telemetry query failed'}); }
});
app.post('/api/telemetry/:nodeId', (req,res) => {
  const nodeId=String(req.params.nodeId).replace(/[^a-zA-Z0-9_.-]/g,'');
  if(!nodeId) return res.status(400).json({ok:false,error:'invalid node id'});
  client.publish(`eagle-eyes/telemetry/${nodeId}`, JSON.stringify({...req.body,time:req.body.time||new Date().toISOString()}), {qos:1}, err => err ? res.status(503).json({ok:false}) : res.status(202).json({ok:true,nodeId}));
});
app.listen(PORT,'0.0.0.0',()=>console.log(`Power Blueprint listening on ${PORT}`));
