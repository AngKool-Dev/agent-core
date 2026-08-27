package dev.mcplugins.chunksovereignty;

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

public final class SovereigntyStore {

    private final SovereigntyPlugin plugin;
    private final Path file;

    SovereigntyStore(SovereigntyPlugin plugin) {
        this.plugin = plugin;
        this.file = plugin.getDataFolder().toPath().resolve("data").resolve("sovereignty.yml");
    }

    public void load(ChunkIndex idx) {
        if (!Files.isRegularFile(file)) {
            return;
        }
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file.toFile());
        ConfigurationSection chunks = y.getConfigurationSection("chunks");
        if (chunks != null) {
            for (String id : chunks.getKeys(false)) {
                ConfigurationSection c = chunks.getConfigurationSection(id);
                if (c == null) {
                    continue;
                }
                try {
                    idx.putClaim(ChunkIndex.Claim.parse(id),
                            UUID.fromString(c.getString("owner", "")),
                            c.getLong("at"));
                } catch (IllegalArgumentException ignored) {
                }
            }
        }
        Map<UUID, Double> inf = new HashMap<>();
        ConfigurationSection isec = y.getConfigurationSection("influence");
        if (isec != null) {
            for (String id : isec.getKeys(false)) {
                try {
                    inf.put(UUID.fromString(id), isec.getDouble(id));
                } catch (IllegalArgumentException ignored) {
                }
            }
        }
        idx.loadInfluence(inf);
        Map<UUID, Set<UUID>> trusts = new HashMap<>();
        ConfigurationSection tsec = y.getConfigurationSection("trust");
        if (tsec != null) {
            for (String id : tsec.getKeys(false)) {
                try {
                    Set<UUID> set = new HashSet<>();
                    for (String g : tsec.getStringList(id)) {
                        set.add(UUID.fromString(g));
                    }
                    trusts.put(UUID.fromString(id), set);
                } catch (IllegalArgumentException ignored) {
                }
            }
        }
        idx.loadTrusts(trusts);
    }

    public void saveAsync(ChunkIndex idx) {
        String data = serialize(idx);
        plugin.getServer().getScheduler().runTaskAsynchronously(plugin, () -> write(data));
    }

    public void saveSync(ChunkIndex idx) {
        write(serialize(idx));
    }

    private String serialize(ChunkIndex idx) {
        YamlConfiguration y = new YamlConfiguration();
        for (Map.Entry<String, ChunkIndex.ClaimData> e : idx.allClaims()) {
            String base = "chunks." + e.getKey() + ".";
            y.set(base + "owner", e.getValue().owner.toString());
            y.set(base + "at", e.getValue().claimedAt);
        }
        for (Map.Entry<UUID, Double> e : idx.influenceSnapshot().entrySet()) {
            y.set("influence." + e.getKey(), Math.round(e.getValue() * 100.0) / 100.0);
        }
        for (Map.Entry<UUID, Set<UUID>> e : idx.trustSnapshot().entrySet()) {
            y.set("trust." + e.getKey(), e.getValue().stream().map(UUID::toString).toList());
        }
        return y.saveToString();
    }

    private void write(String data) {
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, data);
        } catch (IOException ex) {
            plugin.getLogger().warning("Failed to save sovereignty data: " + ex.getMessage());
        }
    }
}
