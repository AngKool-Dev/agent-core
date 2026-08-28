# Handoff Summary — ARGUS Launcher + Minecraft Plugin Ecosystem

## Objective
Continue development of the ARGUS Launcher ecosystem, focusing on 4 active Minecraft server plugins and a roadmap of 10 total plugin concepts.

---

## What We Did So Far

### 1. Unified Menu Commands Added to 4 Active Plugins
Added quick-menu commands to all 4 plugins in `D:\agent-core\minecraft-plugins\`:

| Plugin | Quick Command | Menu File | Features |
|--------|--------------|-----------|----------|
| ChunkSovereignty | `/cs` | `DomainCommand.java` | claim, unclaim, domain, trust, untrust, particles, help |
| EchoRealms | `/er` | `EchoCommand.java` | list, attune, scan, reload |
| MobEcology | `/me` | `EcologyCommand.java` | status, scan, top, reset, reload |
| SovereignEconomy | `/se` | `EconomyCommands.java` | money, pay, market, bank, reload |

- Command permission audit completed: admin commands gated behind `*admin` permissions (default: `op`); player commands safe with ownership/fund checks.
- All 4 plugins built with Maven, deployed to `D:\mc-test\plugins\`, and RCON-tested on a live Purpur 26.2 server.

### 2. Plugin Source Committed and Pushed
- Git repo: `D:\agent-core\` (remote `https://github.com/AngKool-Dev/agent-core.git`)
- Plugin source copied to `D:\agent-core\minecraft-plugins\`
- Commit `660ca021`: "Add minecraft-plugins source: /cs /er /me /se menu commands for ChunkSovereignty, EchoRealms, MobEcology, SovereignEconomy"
- Pushed to `origin/master`

### 3. Website Updated and Deployed
- Website project: `D:\agent-core\argus-site\`
- Cloudflare Pages project: `argus-launcher` (account `3b11ea20dc32f5e9b49877cdb721628d`)
- No Git provider connected — deployed manually via `wrangler pages deploy` with `--branch=main` as production
- Updated `index.html` with 4 new plugin cards + "Plugins" nav link
- Live URL: `https://argus-launcher.pages.dev/`

### 4. QuestBook v1.2.0 Released
- Source: `D:\agent-core\unified_folder\ObsidianVault\Projects\Minecraft-QuestBook\`
- Built JAR: `D:\agent-core\unified_folder\ObsidianVault\Projects\Minecraft-QuestBook\target\QuestBook-1.2.0.jar`
- GitHub repo: `AngKool-Dev/Minecraft-QuestBook`
- Release created and JAR uploaded to GitHub Releases

### 5. ARGUS v0.1.4 — Current Working Build (TUI-only, no WebView2)
- **Latest working build**: v0.1.4 TUI-only
- Source: `D:\agent-core\era-launcher\`
- Built exe: `D:\agent-core\era-launcher\target\release\era-launcher.exe` (~13.59 MB)
- SHA-256: `66B97692BFA4B91C78458A66FB4F7EF15C282F5994366CC99148C33D5565CC1D`
- **No WebView2 dependency** — pure Rust TUI binary (crossterm + ratatui)
- Build toolchain: Rust stable-x86_64-pc-windows-gnu + WinLibs MinGW-w64 UCRT (GCC 16.1.0)
- **Features**:
  - Update notifications: checks GitHub releases on startup, shows in status bar
  - Foreign asset cleanup: `SystemScanner::cleanup_foreign_assets()` removes known crack-launcher artifacts
  - Java 8 filtering: `JavaManager::detect_compatible()` hides Java < 17; `JavaManager::cleanup_old_managed_javas()` removes old managed runtimes
  - Custom icon embedded from `C:\Users\Administrator\Pictures\Aug 28, 2026, 05_08_02 PM.png`
  - Optimization profiles: Low/Mid/High/Custom JVM arg presets in SETTINGS tab
- GitHub release: `https://github.com/AngKool-Dev/argus-releases/releases/tag/v0.1.4`
- Public download: `https://github.com/AngKool-Dev/argus-releases/releases/latest/download/era-launcher.exe`

---

## Active Plugin Details

### SovereignEconomy
- **Description**: Player-Driven Currency with Real Economic Principles — floating market prices, central bank interest, boom/bust events, inflation.
- **Source**: `D:\agent-core\minecraft-plugins\sovereigneconomy\`
- **Main class**: `dev.mcplugins.sovereigneconomy.SovereignEconomyPlugin`
- **Commands file**: `EconomyCommands.java`
- **Version**: `0.2.0-SNAPSHOT`
- **API**: Paper 1.21.4, soft-depend on Vault
- **Commands**: `/se`, `/money`, `/pay`, `/market`, `/bank`, `/eco`
- **Permissions**: `sovoreconomy.use` (true default), `sovoreconomy.admin` (op default)
- **GitHub**: `https://github.com/Angkool-Dev/minecraft-plugins/tree/main/sovereigneconomy`

### EchoRealms
- **Description**: Ghost Traces of Abandoned Structures — inactive players' builds become echo sites with lore, Memory Shards, and XP attunement.
- **Source**: `D:\agent-core\minecraft-plugins\echorealms\`
- **Main class**: `dev.mcplugins.echorealms.EchoRealmsPlugin`
- **Commands file**: `EchoCommand.java`
- **Version**: `0.2.0-SNAPSHOT`
- **API**: Paper 1.21.4
- **Commands**: `/er`, `/echo`
- **Permissions**: `echorealms.use` (true default), `echorealms.admin` (op default)
- **GitHub**: `https://github.com/Angkool-Dev/minecraft-plugins/tree/main/echorealms`

### MobEcology
- **Description**: Living Ecosystems Where Mob Behavior Evolves — adaptive mob populations, food chains, carrying capacity, territorial behavior.
- **Source**: `D:\agent-core\minecraft-plugins\mobecology\`
- **Main class**: `dev.mcplugins.mobecology.MobEcologyPlugin`
- **Commands file**: `EcologyCommand.java`
- **Version**: `0.2.0-SNAPSHOT`
- **API**: Paper 1.21.4
- **Commands**: `/me`, `/ecology`
- **Permissions**: `mobecology.use` (true default), `mobecology.admin` (op default)
- **GitHub**: `https://github.com/Angkool-Dev/minecraft-plugins/tree/main/mobecology`

### ChunkSovereignty
- **Description**: Organic Land Claims That Grow or Shrink — territory expands with influence, shrinks with neglect, border conflicts, terrain deformation.
- **Source**: `D:\agent-core\minecraft-plugins\chunksovereignty\`
- **Main class**: `dev.mcplugins.chunksovereignty.SovereigntyPlugin`
- **Commands file**: `DomainCommand.java`
- **Version**: `0.2.0-SNAPSHOT`
- **API**: Paper 1.21.4
- **Commands**: `/cs`, `/claim`, `/unclaim`, `/domain`, `/trust`, `/untrust`, `/sovereignty`
- **Permissions**: `sovereignty.admin` (op default)
- **GitHub**: `https://github.com/Angkool-Dev/minecraft-plugins/tree/main/chunksovereignty`

---

## Full Plugin Roadmap (10 Concepts)

### Active (In Development)
1. **SovereignEconomy** — Player-Driven Currency with Real Economic Principles
2. **EchoRealms** — Ghost Traces of Abandoned Structures
3. **MobEcology** — Living Ecosystems Where Mob Behavior Evolves
4. **ChunkSovereignty** — Organic Land Claims That Grow or Shrink

### Planned (Concept Phase)
5. **TerraGenesis** — Living, Evolving Biomes That Drift Over Time
   - Biomes shift based on player activity (over-mining = desertification)
   - Climate systems: temperature, humidity, wind affect crops/mobs/weather
   - Seasons change every in-game week with visual + gameplay effects
   - Compatible with multiverse for parallel world experiments

6. **ChronoShards** — Time-Loop Dungeons That Reset With Memory
   - Procedural dungeons where each "loop" resets but players retain permanent shards
   - Bosses learn from previous attempts and change tactics
   - Dungeon architecture morphs based on player deaths
   - Multiple parallel timelines players can switch between

7. **DiplomacyCraft** — Inter-Nation Politics, Espionage, and Treaties
   - Nations with constitutions, elections, and laws
   - Treaty system with binding contracts enforced by plugin
   - Espionage: spy players can infiltrate, steal intel, sabotage
   - War declarations require parliamentary votes with cooldowns
   - International court system for dispute resolution

8. **SkillForge** — Deep Crafting Specialization With Mastery Trees
   - Choose craft specialization (blacksmith, enchanter, architect, etc.)
   - Mastery tree with 50+ unlockable skills per craft
   - Items crafted by masters have unique, persistent lore/signatures
   - Apprenticeship system: master players can teach novices
   - Server-wide crafting rankings and artisan market

9. **NexusFlow** — Player-Wired Logistics Networks
   - Physical networks (pipes/channels) carrying items, fluids, signals, energy
   - Network topology matters: bandwidth limits, latency based on distance
   - Central hub for programmable logic routing
   - Network security: encrypted channels, permissions
   - Real-time monitoring dashboard of network traffic

10. **ArtifactRegistry** — Unique Named Items With Provenance Histories
    - Every unique item has blockchain-like immutable history
    - Tracks every owner, every event (enchantments, repairs, battles)
    - Items gain "renown" based on deeds
    - Players can quest to find legendary artifacts with backstory
    - Museum system where players donate artifacts with plaques

---

## All Important Locations

### Source Code
- `D:\agent-core\minecraft-plugins\` — 4 active plugins (ChunkSovereignty, EchoRealms, MobEcology, SovereignEconomy)
- `D:\agent-core\unified_folder\ObsidianVault\Projects\Minecraft-QuestBook\` — QuestBook source (separate project)
- `D:\agent-core\argus-site\` — ARGUS website source

### Build Artifacts
- `D:\agent-core\unified_folder\ObsidianVault\Projects\Minecraft-QuestBook\target\QuestBook-1.2.0.jar`
- `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\plugins\` — deployed plugin JARs

### Website
- Source: `D:\agent-core\argus-site\`
- Live URL: `https://argus-launcher.pages.dev/`
- GitHub releases: `https://github.com/AngKool-Dev/argus-releases`
- Download page: `https://argus-launcher.pages.dev/download`
- No Git provider connected to Cloudflare Pages — manual deploys only

### Server & Deployment
- **Test server**: `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\`
- Server software: Purpur 26.2 (`D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\versions\26.2\purpur-26.2.jar`)
- RCON: port 25575, password `kilotest`
- Live plugins dir: `D:\mc-test\plugins\`
- Deployed plugin JARs also in: `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\plugins\`

### Git
- Main repo: `D:\agent-core\` → `https://github.com/AngKool-Dev/agent-core.git`
- Plugin source also at: `D:\agent-core\minecraft-plugins\`
- GitHub token stored in Windows Credential Manager for `git:https://github.com` (username `AngKool-Dev`)

### License Infrastructure (Sentinel — paused)
- Worker URL: `https://license.asoniojohnpaul.workers.dev`
- Worker source: `D:\agent-core\unified_folder\ObsidianVault\Projects\Sentinel\license-server\cloudflare\worker.js`
- KV namespace: `LICENSE` / `fc50360dfad7490f961e13ce177ac94e`
- Secrets: `LICENSE_PRIVATE_KEY`, `LICENSE_TOKEN`
- Keypair location: `D:\agent-core\unified_folder\ObsidianVault\Minecraft\LicenseServer\`

### Build Tools
- Maven: `D:\agent-core\maven\apache-maven-3.9.6\bin\mvn.cmd`
- Java: Java 21 (for compilation)

### Test Artifacts On-Disk
- `D:\agent-core\unified_folder\ObsidianVault\Projects\Minecraft-QuestBook\target\QuestBook-1.2.0.jar`
- `D:\agent-core\unified_folder\ObsidianVault\Projects\Sentinel\target\Sentinel-1.3.0.jar`
- `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\plugins\QuestBook-1.1.0.jar`
- `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\plugins\Sentinel-1.3.0.jar`

---

## What We Are Doing Next

1. **SovereignEconomy** — Continue building the dynamic economy system (market mechanics, interest rates, economic events)
2. **EchoRealms** — Expand echo site mechanics, lore system, and Memory Shard crafting integration
3. **MobEcology** — Add food chain mechanics, migratory patterns, and domestication features
4. **ChunkSovereignty** — Implement terrain deformation, border conflicts, and diplomatic alliances
5. **TerraGenesis** — Start concept/prototype for dynamic biome evolution
6. **Website** — Add download links for plugin JARs, consider connecting Git provider for automated deploys

---

## Quick Reference for Hermes

| Item | Value |
|------|-------|
| Main workspace | `D:\agent-core\` |
| Plugin source | `D:\agent-core\minecraft-plugins\` |
| Build tool | Maven (`D:\agent-core\maven\apache-maven-3.9.6\bin\mvn.cmd`) |
| Java version | 21 |
| Test server | `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\` (Purpur 26.2) |
| Server RCON | `D:\mc-test\` on port 25575, password `kilotest` |
| Deployed plugins | `D:\mc-test\plugins\` and `D:\agent-core\unified_folder\ObsidianVault\Minecraft\TestServer\plugins\` |
| Website | Cloudflare Pages `argus-launcher`, manual deploys |
| GitHub org/user | `AngKool-Dev` |
| Wrangler | `C:\Users\Administrator\AppData\Local\hermes\node\npx.cmd wrangler` |
| Cloudflare auth | `C:\Users\Administrator\.wrangler\config\default.toml` |
| Launcher build | Rust + MinGW-w64 UCRT, TUI-only, no WebView2 |

---

## Notes
- The Minecraft client process (PID 5716, Java 25) must NOT be killed during development.
- Wrangler CLI is available via `npx` at `C:\Users\Administrator\AppData\Local\hermes\node\npx.cmd`.
- Cloudflare auth is via OAuth token stored in `C:\Users\Administrator\.wrangler\config\default.toml`.
- All 4 active plugins use Paper API 1.21.4 and are Maven-based.
- Focus is on the 4 active plugins + 6 planned concepts — NOT Sentinel at this time.
