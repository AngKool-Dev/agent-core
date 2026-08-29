package dev.mcplugins.skillforge;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

class SkillStore {

    private final SkillForgePlugin plugin;
    private final Path file;

    SkillStore(SkillForgePlugin plugin) {
        this.plugin = plugin;
        this.file = plugin.getDataFolder().toPath().resolve("data").resolve("skillforge.yml");
    }

    void load(SkillEngine engine) {
        if (!Files.isRegularFile(file)) return;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file.toFile());

        // XP per player per specialization
        ConfigurationSection xpSec = y.getConfigurationSection("xp");
        if (xpSec != null) {
            for (String uuidStr : xpSec.getKeys(false)) {
                try {
                    UUID uuid = UUID.fromString(uuidStr);
                    ConfigurationSection playerSec = xpSec.getConfigurationSection(uuidStr);
                    if (playerSec == null) continue;
                    Map<String, Integer> specMap = new HashMap<>();
                    for (String specId : playerSec.getKeys(false)) {
                        specMap.put(specId.toLowerCase(), playerSec.getInt(specId));
                    }
                    for (Map.Entry<String, Integer> e : specMap.entrySet()) {
                        engine.addXP(uuid, e.getKey(), e.getValue());
                    }
                } catch (IllegalArgumentException ignored) {}
            }
        }

        // Unlocked skills
        ConfigurationSection unSec = y.getConfigurationSection("unlocked");
        if (unSec != null) {
            for (String uuidStr : unSec.getKeys(false)) {
                try {
                    UUID uuid = UUID.fromString(uuidStr);
                    ConfigurationSection playerSec = unSec.getConfigurationSection(uuidStr);
                    if (playerSec == null) continue;
                    for (String specId : playerSec.getKeys(false)) {
                        ConfigurationSection skillSec = playerSec.getConfigurationSection(specId);
                        if (skillSec == null) continue;
                        for (String skillId : skillSec.getKeys(false)) {
                            if (skillSec.getBoolean(skillId)) {
                                engine.unlockSkill(uuid, specId, skillId);
                            }
                        }
                    }
                } catch (IllegalArgumentException ignored) {}
            }
        }

        // Active spec
        ConfigurationSection actSec = y.getConfigurationSection("active");
        if (actSec != null) {
            for (String uuidStr : actSec.getKeys(false)) {
                try {
                    UUID uuid = UUID.fromString(uuidStr);
                    String specId = actSec.getString(uuidStr);
                    if (specId != null) engine.setActiveSpec(uuid, specId);
                } catch (IllegalArgumentException ignored) {}
            }
        }

        // Total crafts
        ConfigurationSection craSec = y.getConfigurationSection("crafts");
        if (craSec != null) {
            for (String uuidStr : craSec.getKeys(false)) {
                try {
                    UUID uuid = UUID.fromString(uuidStr);
                    int count = craSec.getInt(uuidStr);
                    AtomicInteger ai = engine.totalCrafts.get(uuid);
                    if (ai == null) engine.totalCrafts.put(uuid, new AtomicInteger(count));
                    else ai.set(count);
                } catch (IllegalArgumentException ignored) {}
            }
        }

        // Reputation
        ConfigurationSection repSec = y.getConfigurationSection("reputation");
        if (repSec != null) {
            for (String uuidStr : repSec.getKeys(false)) {
                try {
                    UUID uuid = UUID.fromString(uuidStr);
                    int rep = repSec.getInt(uuidStr);
                    engine.reputation.merge(uuid, rep, Integer::sum);
                } catch (IllegalArgumentException ignored) {}
            }
        }
    }

    void saveAsync(SkillEngine engine) {
        String data = serialize(engine);
        plugin.getServer().getScheduler().runTaskAsynchronously(plugin, () -> write(data));
    }

    void saveSync(SkillEngine engine) {
        write(serialize(engine));
    }

    private String serialize(SkillEngine engine) {
        YamlConfiguration y = new YamlConfiguration();

        // XP
        for (Map.Entry<UUID, Map<String, Integer>> playerXp : engine.xp.entrySet()) {
            String base = "xp." + playerXp.getKey() + ".";
            for (Map.Entry<String, Integer> specXp : playerXp.getValue().entrySet()) {
                y.set(base + specXp.getKey(), specXp.getValue());
            }
        }

        // Unlocked skills
        for (Map.Entry<UUID, Map<String, Set<String>>> playerUn : engine.unlocked.entrySet()) {
            String base = "unlocked." + playerUn.getKey() + ".";
            for (Map.Entry<String, Set<String>> specSkills : playerUn.getValue().entrySet()) {
                for (String skillId : specSkills.getValue()) {
                    y.set(base + specSkills.getKey() + "." + skillId, true);
                }
            }
        }

        // Active spec
        for (Map.Entry<UUID, String> act : engine.activeSpec.entrySet()) {
            y.set("active." + act.getKey(), act.getValue());
        }

        // Total crafts
        for (Map.Entry<UUID, AtomicInteger> cra : engine.totalCrafts.entrySet()) {
            y.set("crafts." + cra.getKey(), cra.getValue().get());
        }

        // Reputation
        for (Map.Entry<UUID, Integer> rep : engine.reputation.entrySet()) {
            y.set("reputation." + rep.getKey(), rep.getValue());
        }

        return y.saveToString();
    }

    private void write(String data) {
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, data);
        } catch (IOException ex) {
            plugin.getLogger().warning("Failed to save skillforge data: " + ex.getMessage());
        }
    }
}
