package dev.mcplugins.echorealms;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public final class EchoStore {

    private final EchoRealmsPlugin plugin;
    private final Path file;

    EchoStore(EchoRealmsPlugin plugin) {
        this.plugin = plugin;
        this.file = plugin.getDataFolder().toPath().resolve("data").resolve("echoes.yml");
    }

    public void load(EchoManager manager) {
        if (!Files.isRegularFile(file)) {
            return;
        }
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file.toFile());
        ConfigurationSection regions = y.getConfigurationSection("regions");
        if (regions != null) {
            for (String rk : regions.getKeys(false)) {
                String[] parts = rk.split("\\|");
                if (parts.length != 3) {
                    continue;
                }
                EchoRegion region = manager.region(new EchoManager.RegionKey(
                        parts[0], Integer.parseInt(parts[1]), Integer.parseInt(parts[2])));
                ConfigurationSection sites = regions.getConfigurationSection(rk + ".sites");
                if (sites == null) {
                    continue;
                }
                for (String id : sites.getKeys(false)) {
                    try {
                        UUID builder = UUID.fromString(id);
                        ConfigurationSection s = sites.getConfigurationSection(id);
                        if (s == null) {
                            continue;
                        }
                        BuilderSite bs = region.site(builder);
                        bs.count = s.getLong("count");
                        bs.sumX = s.getLong("sumx");
                        bs.sumZ = s.getLong("sumz");
                        bs.minY = s.getInt("miny");
                        bs.maxY = s.getInt("maxy");
                        bs.lastActivity = s.getLong("last");
                        ConfigurationSection att = s.getConfigurationSection("attuned");
                        if (att != null) {
                            for (String a : att.getKeys(false)) {
                                bs.attunedAt.put(UUID.fromString(a), att.getLong(a));
                            }
                        }
                    } catch (IllegalArgumentException ignored) {
                    }
                }
            }
        }
        ConfigurationSection man = y.getConfigurationSection("manifested");
        Map<String, Long> state = new HashMap<>();
        if (man != null) {
            for (String k : man.getKeys(false)) {
                state.put(k, man.getLong(k));
            }
        }
        manager.restoreState(state);
    }

    public void saveAsync(EchoManager manager) {
        String data = serialize(manager);
        plugin.getServer().getScheduler().runTaskAsynchronously(plugin, () -> write(data));
    }

    public void saveSync(EchoManager manager) {
        write(serialize(manager));
    }

    private String serialize(EchoManager manager) {
        YamlConfiguration y = new YamlConfiguration();
        for (EchoRegion region : manager.regions()) {
            String base = "regions." + region.world + "|" + region.rx + "|" + region.rz + ".sites.";
            for (Map.Entry<UUID, BuilderSite> e : region.sites.entrySet()) {
                BuilderSite s = e.getValue();
                String b = base + e.getKey() + ".";
                y.set(b + "count", s.count);
                y.set(b + "sumx", s.sumX);
                y.set(b + "sumz", s.sumZ);
                y.set(b + "miny", s.minY == Integer.MAX_VALUE ? 0 : s.minY);
                y.set(b + "maxy", s.maxY == Integer.MIN_VALUE ? 0 : s.maxY);
                y.set(b + "last", s.lastActivity);
                for (Map.Entry<UUID, Long> a : s.attunedAt.entrySet()) {
                    y.set(b + "attuned." + a.getKey(), a.getValue());
                }
            }
        }
        for (Map.Entry<String, Long> e : manager.manifestState().entrySet()) {
            y.set("manifested." + e.getKey(), e.getValue());
        }
        return y.saveToString();
    }

    private void write(String data) {
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, data);
        } catch (IOException ex) {
            plugin.getLogger().warning("Failed to save echo data: " + ex.getMessage());
        }
    }
}
