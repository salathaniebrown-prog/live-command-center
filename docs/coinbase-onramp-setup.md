# Coinbase Onramp setup boundary

This project may use Coinbase Onramp as the future card/bank-to-crypto funding provider for the Eagle Eyes / Command Center Crypto Lab.

## Current project state

- The Billing Hub can open Coinbase and the official Coinbase payment-method help page.
- The user may mark a payment method as **USER CONFIRMED LINKED** after Coinbase itself reports success.
- That local confirmation is not treated as an API-verified Command Center integration.
- The current Crypto Lab remains wallet-approved and does not sign or submit transactions on the server.
- Mainnet stays locked unless deliberately configured elsewhere.

## User-owned Coinbase step

Payment-method enrollment is completed inside Coinbase, not inside this repository.

On mobile, Coinbase documents this flow:

1. Open the Coinbase app.
2. Open the menu.
3. Go to **Profile & Settings**.
4. Choose **Add a payment method**.
5. Choose an eligible payment method.
6. Complete Coinbase verification.

Availability depends on the user's region, account status, card/bank eligibility, and issuer policy. Do not represent a card as supported until Coinbase confirms it.

Official references:

- https://help.coinbase.com/en/coinbase/getting-started/add-a-payment-method/manage-method
- https://help.coinbase.com/en/coinbase/getting-started/add-a-payment-method/add-and-verify-pm-namerica-latam
- https://help.coinbase.com/en/coinbase/getting-started/add-a-payment-method/add-a-payment-method-troubleshooting
- https://www.coinbase.com/developer-platform/products/onramp

## Future embedded Onramp integration

Coinbase Developer Platform Onramp can provide fiat-to-crypto funding inside an application. That integration requires a Coinbase Developer Platform account and provider credentials.

Security requirements:

- Never commit Coinbase API credentials to Git.
- Never paste card numbers, CVV, bank credentials, passwords, 2FA codes, wallet seed phrases, or private keys into the Command Center.
- Store provider credentials only in the deployment secret store.
- Keep automatic crypto purchase disabled.
- Require explicit owner confirmation for every purchase.
- Display asset, network, destination wallet, amount, provider fees, and final total before confirmation.
- Log provider order/transaction references and timestamps after completion.
- Do not mark a payment method or purchase VERIFIED unless the provider confirms it.

## Funding method note

Coinbase's current U.S. payment-method documentation lists methods such as ACH, debit card, PayPal, Apple Pay, Google Pay, and Samsung Pay, subject to account/region eligibility. Card issuers or processors may block crypto transactions. The project must therefore support a provider-reported UNAVAILABLE/DECLINED state instead of assuming any specific card will work.
