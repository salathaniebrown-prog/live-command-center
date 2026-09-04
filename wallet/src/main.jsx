import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WagmiProvider } from "wagmi";
import { createAppKit, useAppKit } from "@reown/appkit/react";
import { WagmiAdapter } from "@reown/appkit-adapter-wagmi";
import { base, mainnet } from "@reown/appkit/networks";
import { useAppKitWallet } from "@reown/appkit-wallet-button/react";
import "./styles.css";

const projectId = import.meta.env.VITE_REOWN_PROJECT_ID?.trim();
const networks = [base, mainnet];
const queryClient = new QueryClient();
let wagmiAdapter = null;

if (projectId) {
  wagmiAdapter = new WagmiAdapter({
    networks,
    projectId
  });

  createAppKit({
    adapters: [wagmiAdapter],
    networks,
    projectId,
    metadata: {
      name: "Eagle Eyes",
      description: "Eagle Eyes World Data Command Center wallet access",
      url: `${window.location.origin}/wallet/`,
      icons: []
    },
    features: {
      analytics: true
    }
  });
}

function formatConnectedAddress(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (typeof value.address === "string") return value.address;
  if (typeof value.caipAddress === "string") return value.caipAddress;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function shorten(value) {
  if (!value) return "";
  const address = value.includes(":") ? value.split(":").at(-1) : value;
  if (address.length < 14) return address;
  return `${address.slice(0, 7)}…${address.slice(-5)}`;
}

function SetupRequired() {
  return (
    <main className="shell">
      <section className="panel">
        <div className="brandRow">
          <span className="brand">EAGLE EYES</span>
          <span className="status statusWarning">SETUP</span>
        </div>
        <p className="eyebrow">SECURE WALLET RAIL</p>
        <h1>Wallet page is installed.</h1>
        <p className="lead">
          Add the Railway environment variable <code>VITE_REOWN_PROJECT_ID</code> and rebuild this branch to activate Reown AppKit.
        </p>
        <div className="notice">
          Never place a seed phrase, recovery phrase, or wallet private key in this project.
        </div>
        <a className="secondaryButton" href="/">RETURN TO COMMAND CENTER</a>
      </section>
    </main>
  );
}

function WalletApp() {
  const { open } = useAppKit();
  const [connectedAddress, setConnectedAddress] = useState("");
  const [selectedAmount, setSelectedAmount] = useState(10);
  const [errorMessage, setErrorMessage] = useState("");

  const { isReady, isPending, connect } = useAppKitWallet({
    namespace: "eip155",
    onSuccess(parsedCaipAddress) {
      setErrorMessage("");
      setConnectedAddress(formatConnectedAddress(parsedCaipAddress));
    },
    onError(error) {
      setErrorMessage(error?.message || "Wallet connection failed.");
    }
  });

  const amountLabel = useMemo(() => `$${selectedAmount}`, [selectedAmount]);

  async function connectMetaMask() {
    setErrorMessage("");
    try {
      await connect("metamask");
    } catch (error) {
      setErrorMessage(error?.message || "MetaMask connection failed.");
    }
  }

  return (
    <main className="shell">
      <section className="panel">
        <div className="brandRow">
          <span className="brand">EAGLE EYES</span>
          <span className="status">WALLET RAIL</span>
        </div>

        <p className="eyebrow">SUPPORT DEVELOPMENT</p>
        <h1>Connect securely. Approve only what you recognize.</h1>
        <p className="lead">
          This isolated page connects an EVM wallet through Reown AppKit. It does not request or store private keys.
        </p>

        {!connectedAddress ? (
          <div className="actions">
            <button
              className="primaryButton"
              type="button"
              disabled={!isReady || isPending}
              onClick={connectMetaMask}
            >
              {isPending ? "CONNECTING…" : "CONNECT METAMASK"}
            </button>
            <button className="secondaryButton" type="button" onClick={() => open()}>
              OTHER WALLETS
            </button>
          </div>
        ) : (
          <div className="connectedCard">
            <div>
              <span className="connectedLabel">CONNECTED</span>
              <strong>{shorten(connectedAddress)}</strong>
            </div>
            <span className="check">✓</span>
          </div>
        )}

        {errorMessage ? <div className="errorBox">{errorMessage}</div> : null}

        <div className="divider" />

        <div className="sectionHeading">
          <div>
            <p className="eyebrow">SUPPORT AMOUNT</p>
            <h2>{amountLabel}</h2>
          </div>
          <span className="safeTag">NO PAYMENT SENT YET</span>
        </div>

        <div className="amountGrid">
          {[5, 10, 25, 50].map((amount) => (
            <button
              key={amount}
              className={selectedAmount === amount ? "amount active" : "amount"}
              type="button"
              onClick={() => setSelectedAmount(amount)}
            >
              ${amount}
            </button>
          ))}
        </div>

        <button className="disabledPayment" type="button" disabled>
          PAYMENT ACTIVATES AFTER VERIFICATION STEP
        </button>

        <p className="finePrint">
          Wallet connection is live once configured. Sending funds remains disabled until the destination address, network, transaction verification, and receipt flow are added and tested.
        </p>

        <a className="backLink" href="/">← Return to Eagle Eyes Command Center</a>
      </section>
    </main>
  );
}

function Root() {
  if (!projectId || !wagmiAdapter) return <SetupRequired />;

  return (
    <WagmiProvider config={wagmiAdapter.wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <WalletApp />
      </QueryClientProvider>
    </WagmiProvider>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
