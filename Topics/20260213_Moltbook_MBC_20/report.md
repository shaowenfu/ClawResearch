# InsightEngine Report: Moltbook MBC-20
**Date**: 2026-02-13
**Status**: Distilled & Synthesized

## 1. Executive Summary
MBC-20 is an inscription-based token protocol on **Moltbook** (the AI agent social network), directly inspired by BRC-20. Unlike standard ERC-20s, tokens are deployed and minted by posting structured JSON messages on Moltbook posts. 

It represents a **"Layer 2.5"** economy where social actions (posts) trigger on-chain asset creation on Base.

## 2. Technical Architecture
### The Mechanism
- **Inscriptions**: Valid actions are JSON blobs inside Moltbook posts.
  - Deploy: `mbc-20 deploy tick=TOKEN max=21M lim=100`
  - Mint: `mbc-20 mint tick=TOKEN`
- **Indexer**: An off-chain indexer (open source) reads Moltbook posts, validates them against protocol rules, and updates balances.
- **Bridge**: Validated balances can be bridged to Base Mainnet as ERC-20 tokens via the `MBC20Factory`.

### Protocol Versions
| Feature | V1 (Current) | V2 (Planned) |
| :--- | :--- | :--- |
| **Deployment** | Admin-only (Gatekept) | **Permissionless** (Burn $CLAW to deploy) |
| **Fees** | 1% Burn, 1% Team | 1% Burn, **1% to Deployer** |
| **Minting** | Signature-based | Open / Fair Launch |

## 3. Tokenomics & The $CLAW Utility
$CLAW is the native utility token of the protocol.
- **Supply**: 21,000,000 (Bitcoin model).
- **Deflationary Mechanism**: 
  - **1% of all V1/V2 pool trades are burned.**
  - **V2 Deployments** require burning $CLAW.
- **Staking/Holding Utility**: Holding/Burning 10,000 $CLAW grants **0% trading fees**.

## 4. Market Ecosystem
- **Infrastructure**: 
  - *MoltScreener*: The "DexScreener" for agent tokens.
  - *MoltRoad*: Underground marketplace for illicit/grey-area agent services.
- **Competitors**: 
  - *Clawnch*: A separate launchpad on Base for "Memecoins" (less technical, more pump.fun style).
  - *MBC-20*: Targeted at "Tech-Native" assets and Agent-to-Agent value transfer.

## 5. Strategic Verdict (Shawn's Take)
MBC-20 is more than a memecoin factory; it is an **Agent-Native Asset Protocol**. The "V2 Deployer Fee" (1% lifetime royalties on volume) creates a massive incentive for Agents to launch useful tokens.

**Opportunity**:
- ** arbitrage**: Monitor the gap between V1 and V2 transition.
- **Service**: Build a "Deployer Agent" that helps non-technical users launch V2 tokens when it goes live.
