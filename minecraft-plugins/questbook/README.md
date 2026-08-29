# QuestBook

A custom quest book plugin for **Minecraft Java Edition 26.2** (Spigot/Paper API).

## Features

- **Inventory-based Quest Book GUI** — 54-slot interactive interface for managing quests
- **Multiple Objective Types:**
  - `KILL_MOB` — Kill specified entities
  - `COLLECT_ITEM` — Pick up items or break blocks
  - `VISIT_BIOME` — Enter specific biomes
  - `PLACE_BLOCK` — Place specific blocks
- **Quest Persistence** — Progress saves across server restarts (YAML per-player)
- **Reward Distribution** — Experience, money, and items on completion
- **Level Requirements** — Gates quests behind player levels
- **Tab Completion** — Full command autocomplete

## Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/quest` | `/q` | Open quest book GUI |
| `/quest accept <id>` | `/q accept <id>` | Accept a quest |
| `/quest abandon <id>` | `/q abandon <id>` | Abandon active quest |
| `/quest info <id>` | `/q info <id>` | View quest details |
| `/quest list` | `/q list` | List all quests |
| `/quest give <player> <quest>` | `/q give <player> <quest>` | Give quest rewards to player |
| `/quest payout <player> <quest>` | `/q payout <player> <quest>` | Give quest rewards to player |
| `/quest balance [player]` | `/q bal [player]` | Check player's balance |

## Permissions

- `questbook.admin` — Access `/quest give`, `/quest payout`, and `/quest admin` commands (default: op)

## Installation

1. Build: `mvn clean package`
2. Copy `target/QuestBook-1.0.0.jar` to your server's `plugins/` folder
3. Restart server
4. Configure quests in `plugins/QuestBook/quests/`

## Quest Configuration

Create `.yml` files in `plugins/QuestBook/quests/`:

```yaml
id: demo_quest_1
title: "Beginner's First Quest"
description: "Slay 5 zombies and collect 3 rotten flesh as offerings."
type: COMBAT
required_level: 1
repeatable: false
objectives:
  - description: "Kill zombies"
    type: KILL_MOB
    target: ZOMBIE
    amount: 5
  - description: "Collect rotten flesh"
    type: COLLECT_ITEM
    target: ROTTEN_FLESH
    amount: 3
rewards:
  items:
    DIAMOND: 1
  experience: 100
  money: 50
```

### Objective Types

| Type | Target Format | Example |
|------|---------------|---------|
| `KILL_MOB` | Entity name (uppercase) | `ZOMBIE`, `SKELETON` |
| `COLLECT_ITEM` | Material name (uppercase) | `DIAMOND`, `ROTTEN_FLESH` |
| `VISIT_BIOME` | Biome name (uppercase) | `PLAINS`, `NETHER_WASTES` |
| `PLACE_BLOCK` | Material name (uppercase) | `COBBLESTONE`, `OAK_LOG` |

## Requirements

- **Java 21+**
- **Minecraft 26.2** (Spigot/Paper API `26.2-R0.1-SNAPSHOT`)

## Building

```bash
mvn clean package
```

Output: `target/QuestBook-1.0.0.jar`

## License

MIT