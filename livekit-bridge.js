const { Room, RoomEvent, Track } = require('@livekit/rtc-node');
const { insertVectorTelemetry } = require('./vector-teleport');

async function startLiveKitStreamBridge() {
  const room = new Room();

  room.on(RoomEvent.Connected, () => {
    console.log('[+] Connected to LiveKit voice session.');
  });

  room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === Track.Kind.AUDIO) {
      console.log('[+] Audio track subscribed from participant:', participant.identity);
      
      // Pipe incoming PCM audio frames into telemetry buffer or speech-to-text pipeline
      track.on('audioFrame', (buffer) => {
        // Process real-time audio telemetry frame
        // insertVectorTelemetry(Date.now(), Array.from(buffer).slice(0, 384));
      });
    }
  });

  room.on(RoomEvent.Disconnected, () => {
    console.log('[-] Disconnected from LiveKit session. Reconnecting...');
    setTimeout(startLiveKitStreamBridge, 5000);
  });

  try {
    // Connect using environment credentials
    const wsUrl = process.env.LIVEKIT_URL || 'ws://localhost:7880';
    const token = process.env.LIVEKIT_TOKEN || 'mock_token';
    await room.connect(wsUrl, token);
  } catch (err) {
    console.error('[!] LiveKit connection error:', err.message);
  }
}

if (require.main === module) {
  startLiveKitStreamBridge();
}

module.exports = { startLiveKitStreamBridge };
