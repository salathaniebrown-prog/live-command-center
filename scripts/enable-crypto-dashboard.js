"use strict";

const fs = require("node:fs");
const path = require("node:path");

const pagePath = path.join(__dirname, "..", "public", "index.html");
let next = fs.readFileSync(pagePath, "utf8");

const MARKER = 'id="crypto"';

if (next.includes(MARKER)) {
  console.log("Eagle Eyes crypto dashboard already enabled.");
  process.exit(0);
}

function insertBefore(anchor, addition, label) {
  const index = next.indexOf(anchor);
  if (index === -1) throw new Error(`Could not find ${label} anchor`);
  next = next.slice(0, index) + addition + next.slice(index);
}

function replaceOnce(anchor, replacement, label) {
  const index = next.indexOf(anchor);
  if (index === -1) throw new Error(`Could not find ${label} anchor`);
  next = next.slice(0, index) + replacement + next.slice(index + anchor.length);
}

const cryptoCss = `
.cryptoGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.cryptoCard{border:1px solid var(--line);border-radius:11px;background:#06100b;padding:11px}.cryptoCard span{display:block;color:var(--muted);font:700 8px ui-monospace,monospace;letter-spacing:.1em}.cryptoCard b{display:block;margin-top:5px;color:var(--cyan);font:800 14px ui-monospace,monospace;word-break:break-word}.cryptoActions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.cryptoForm{border:1px solid var(--line);border-radius:11px;background:#06100b;padding:11px;display:grid;gap:8px}.cryptoForm h3{margin:0;color:var(--gold);font:800 11px ui-monospace,monospace;letter-spacing:.08em}.cryptoForm input{width:100%;border:1px solid var(--line2);background:#030906;color:var(--text);border-radius:9px;padding:9px;outline:none}.cryptoOutput{margin-top:10px;min-height:90px;border:1px solid var(--line);border-radius:10px;background:#030906;padding:11px;white-space:pre-wrap;word-break:break-word;font:600 10px/1.5 ui-monospace,monospace;color:#d9efe3}@media(max-width:820px){.cryptoGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.cryptoActions{grid-template-columns:1fr}}@media(max-width:520px){.cryptoGrid{grid-template-columns:1fr}}
`;
insertBefore("</style>", cryptoCss, "style closing tag");

replaceOnce(
  '<a href="#links">LINKS</a><a href="#max">MAX</a>',
  '<a href="#links">LINKS</a><a href="#crypto">CRYPTO</a><a href="#max">MAX</a>',
  "navigation"
);

const cryptoPanel = ` <article id="crypto" class="panel span12"><div class="head"><div class="title">CRYPTO FUNDING RAIL // BASE USDC</div><div id="cryptoState" class="sub">CHECKING SANDBOX</div></div><div class="body"><div class="cryptoGrid"><div class="cryptoCard"><span>NETWORK</span><b id="cryptoNetwork">CHECKING</b></div><div class="cryptoCard"><span>MODE</span><b id="cryptoMode">SANDBOX</b></div><div class="cryptoCard"><span>ASSET</span><b id="cryptoAsset">USDC</b></div><div class="cryptoCard"><span>MAINNET</span><b id="cryptoMainnet">LOCKED</b></div></div><div class="cryptoActions"><section class="cryptoForm"><h3>RECEIVE USDC REQUEST</h3><input id="cryptoReceiveAmount" inputmode="decimal" placeholder="Amount USDC"><input id="cryptoReceiveMemo" maxlength="140" placeholder="Memo (optional)"><button class="btn" type="button" onclick="createCryptoReceive()">CREATE REQUEST</button></section><section class="cryptoForm"><h3>PREPARE UNSIGNED SEND</h3><input id="cryptoSendTo" autocomplete="off" placeholder="0x recipient address"><input id="cryptoSendAmount" inputmode="decimal" placeholder="Amount USDC"><input id="cryptoSendMemo" maxlength="140" placeholder="Memo (optional)"><button class="btn" type="button" onclick="prepareCryptoSend()">PREPARE FOR WALLET</button></section></div><div id="cryptoOutput" class="cryptoOutput">Base Sepolia sandbox status loading. No private key, seed phrase, server signing, or autonomous broadcast is used. Every send requires external wallet approval.</div></div></article>\n`;
insertBefore(
  ' <article class="panel span5"><div class="head"><div class="title">PX4 OBSERVATION</div>',
  cryptoPanel,
  "PX4 panel"
);

const cryptoJs = `
function cryptoToken(){return sessionStorage.getItem('eagleEyesToken')||($('token')?.value||'').trim()}
async function loadCryptoStatus(){try{const {r,j}=await getj('/api/eagle-eyes/crypto/status');if(!r.ok)throw new Error(j?.error||('HTTP '+r.status));$('cryptoState').textContent=j?.configured?'SANDBOX READY':'SANDBOX • ADDRESS NOT CONFIGURED';$('cryptoNetwork').textContent=j?.network?.name||'Base Sepolia';$('cryptoMode').textContent=(j?.mode||'sandbox').toUpperCase();$('cryptoAsset').textContent=(j?.asset?.symbol||'USDC')+' • CHAIN '+(j?.network?.chainId??'84532');$('cryptoMainnet').textContent=j?.mainnetLocked===false&&j?.network?.mainnet?'ENABLED':'LOCKED';if(!j?.configured)$('cryptoOutput').textContent='Crypto rail is present and safe, but CRYPTO_RECEIVE_ADDRESS is not configured in this deployment. Base Sepolia remains the default and mainnet remains locked.'}catch(e){$('cryptoState').textContent='UNAVAILABLE';$('cryptoOutput').textContent='Crypto status unavailable: '+e.message}}
async function cryptoPost(route,body){const token=cryptoToken();if(!token){$('cryptoOutput').textContent='Command Rail access token required for crypto request preparation. No wallet credentials belong here.';return null}const {r,j}=await getj(route,{method:'POST',headers:{'content-type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});if(!r.ok){$('cryptoOutput').textContent='Crypto request rejected: '+(j?.error||('HTTP '+r.status));return null}$('cryptoOutput').textContent=JSON.stringify(j,null,2);return j}
async function createCryptoReceive(){const amount=($('cryptoReceiveAmount').value||'').trim(),memo=($('cryptoReceiveMemo').value||'').trim();if(!amount){$('cryptoOutput').textContent='Enter a USDC amount for the receive request.';return}await cryptoPost('/api/eagle-eyes/crypto/payment-request',{amountUsdc:amount,memo})}
async function prepareCryptoSend(){const toAddress=($('cryptoSendTo').value||'').trim(),amount=($('cryptoSendAmount').value||'').trim(),memo=($('cryptoSendMemo').value||'').trim();if(!toAddress||!amount){$('cryptoOutput').textContent='Enter a recipient address and USDC amount. The server will prepare only an unsigned request.';return}await cryptoPost('/api/eagle-eyes/crypto/transfer-request',{toAddress,amountUsdc:amount,memo})}
`;
insertBefore("function saveToken(){", cryptoJs, "saveToken function");
insertBefore(
  "syncAll().then(renderExecutiveCouncil);setInterval(()=>syncAll().then(renderExecutiveCouncil),60000);",
  "loadCryptoStatus();setInterval(loadCryptoStatus,60000);\n",
  "startup synchronization"
);

fs.writeFileSync(pagePath, next);
console.log("Eagle Eyes Chronicle V13 crypto dashboard enabled.");
