function getEdgeKey() {
  const b64 = process.env.EDGE_PRIVATE_KEY;
  if (!b64) {
    if (typeof window !== 'undefined') return null;
    throw new Error('EDGE_PRIVATE_KEY missing in Railway vault');
  }
  return Buffer.from(b64, 'base64').toString('utf8');
}
export const edgePrivateKey = getEdgeKey();
