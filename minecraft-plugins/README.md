# minecraft-plugins

Unique Minecraft server plugins targeting Paper **1.21 -> 26.2** from a single jar
(compiled against the Paper 1.21 API, Java 21 bytecode, zero NMS).

## Plugins

| Plugin | Status | Concept |
|---|---|---|
| MobEcology | implemented | Adaptive mob ecosystems: populations, carrying capacity, food webs, mobs that adapt to being farmed |
| SovereignEconomy | planned | Floating player-driven macro economy |
| ChunkSovereignty | planned | Organic land claims that grow or shrink |
| SkillForge | planned | Crafting mastery trees with signed artifacts |
| ChronoShards | planned | Time-loop roguelite dungeons |
| TerraGenesis | planned | Living biomes, climate drift and seasons |

## Build

```
mvn package
```

Artifacts land in `<module>/target/*.jar`.
