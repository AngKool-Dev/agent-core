# BuiltByBit Listing — Sentinel

**Category:** Minecraft → Plugins (Auditing / Anti-grief / Administration)
**Price (suggested):** $15 one-time — permanent license key (adjustable)
**Version:** 1.3.0 (Paper / Purpur 1.21+, Java 21)

---

## Title

Sentinel — Audit Logging, Block Inspection & Rollback

## Tag line

Who did this, and can we undo it? Inspect every block, roll back griefing and theft, and recover lost items.

## Description (paste into the listing editor)

Sentinel is an **audit and recovery plugin** that records what happens on your server and answers one question: *"who did this, and can we undo it?"*

It runs entirely async (Java 21 virtual threads, bounded queue, LRU caches), so the hot path never blocks your main server thread.

### Premium features

- **Block inspection** — ray-traced inspect tool with a 3x3x3 neighborhood fallback. Find who placed, broke, or modified any block or entity, even blocks that were already removed.
- **Rollback** — restore blocks by player, region, radius, or whole world. Restore inventories and tile entities, and undo griefing or accidents to a previous state.
- **Item-loss recovery** — restore items lost to despawn, the void, fire and lava.
- **Player history** — last 30 actions by a player, or every edit around you in a radius.
- **License-based activation** — your key is bound to your server, verified on every join.

### Everything you get

| Area | What's recorded |
|---|---|
| Blocks | place / break / modify |
| Inventories | pickups, drops, container edits, item losses |
| Environment | TNT, explosions, fire, lava, water |
| Entities | kills, damage, spawn/despawn |
| Chat & commands | messages and command usage |
| Players | joins, leaves, deaths |

**38 audit action types**, each individually toggleable in config.

### Storage

- **SQLite** — zero setup, `sentinel.db` with WAL mode (default).
- **PostgreSQL** — for multi-server or heavy-traffic networks, with Flyway migrations.

### Commands

| Command | Description |
|---|---|
| `/sentinel inspect [on/off] [radius:N] [player:NAME]` | Inspect what happened around you |
| `/sentinel rollback <player:NAME \| radius:N \| world:NAME>` | Roll back blocks / inventories / items |
| `/sentinel status` | Database + license status |
| `/sentinel purge [older-than:N]` | Purge audit records |
| `/sentinel reload` | Reload configuration |
| `/sentinel license` | Check your license status |

All commands require the `sentinel.admin` permission (op by default).

### Requirements

- **Java 21**
- **Paper 1.21+** (or a Paper fork such as **Purpur**)

### How to install & activate

1. Drop the jar into `plugins/`.
2. Edit `plugins/Sentinel/config.yml` → set `license.key: YOUR-KEY`.
3. Restart the server. On the first start your key binds to your server's IP; from then on the plugin validates the license on every join.

> **Important:** Sentinel is fail-closed. If the license check can't reach the validation server, the plugin disables itself to protect you.

### How to get your license key

After purchase, **DM the author on BuiltByBit with your username** and you'll receive your license key within a few hours. (If you bought via our direct store, the key is sent with your receipt.)

### Try before you buy

A free Lite edition (audit logging + storage + `/sentinel status|purge|reload`) is available on **Modrinth** — search "Sentinel Lite". Premium features (inspection, rollback, item-loss recovery) require the paid key.

### Support

- Response time: typically within 24 hours
- Report bugs with the version, server software and the `/sentinel status` output
- Refunds: full refund within 7 days if the plugin doesn't work as described (subject to BuiltByBit refund policy)

---

## Checklist before publishing

- [ ] Set final **price** (suggested $15; BuiltByBit takes a commission, check current rates)
- [ ] **License model:** keys issued as permanent by default (buy-once). Change to time-limited via `--days N` if you switch to renewals.
- [ ] Add **screenshots** (in-game inspect overlay, rollback before/after, `/sentinel status`)
- [ ] Upload **Sentinel-1.3.0.jar** as the resource file (build: `mvn package -P release`)
- [ ] Replace **[Discord/support]** with your real contact method
- [ ] Set resource **license/EULA** (e.g., no redistribution, key per server)
