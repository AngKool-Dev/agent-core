package dev.mcplugins.mobecology;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public final class EcologyStore {

    private final MobEcologyPlugin plugin;
    private final Path file;

    EcologyStore(MobEcologyPlugin plugin) {
        this.plugin = plugin;
        this.file = plugin.getDataFolder().toPath().resolve("data").resolve("ecology.yml");
    }

    public Map<RegionKey, EcologyRegion> load() {
        Map<RegionKey, EcologyRegion> out = new HashMap<>();
        if (!Files.isRegularFile(file)) {
            return out;
        }
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file.toFile());
        ConfigurationSection root = y.getConfigurationSection("regions");
        if (root == null) {
            return out;
        }
        for (String key : root.getKeys(false)) {
            RegionKey rk;
            try {
                rk = RegionKey.parse(key);
            } catch (Exception ex) {
                continue;
            }
            EcologyRegion r = new EcologyRegion();
            ConfigurationSection sec = root.getConfigurationSection(key);
            if (sec == null) {
                continue;
            }
            copyDoubles(sec, "pop", r.pop);
            copyLongs(sec, "seen", r.lastSeen);
            copyDoubles(sec, "pressure", r.pressure);
            r.lastCensus = sec.getLong("lastCensus");
            out.put(rk, r);
        }
        return out;
    }

    public void saveAsync(Map<RegionKey, EcologyRegion> regions) {
        String data = serialize(regions);
        plugin.getServer().getScheduler().runTaskAsynchronously(plugin, () -> write(data));
    }

    public void saveSync(Map<RegionKey, EcologyRegion> regions) {
        write(serialize(regions));
    }

    private String serialize(Map<RegionKey, EcologyRegion> regions) {
        YamlConfiguration y = new YamlConfiguration();
        for (Map.Entry<RegionKey, EcologyRegion> e : regions.entrySet()) {
            EcologyRegion r = e.getValue();
            String base = "regions." + e.getKey().serialize() + ".";
            y.set(base + "pop", new HashMap<>(r.pop));
            y.set(base + "seen", new HashMap<>(r.lastSeen));
            y.set(base + "pressure", new HashMap<>(r.pressure));
            y.set(base + "lastCensus", r.lastCensus);
        }
        return y.saveToString();
    }

    private void write(String data) {
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, data);
        } catch (IOException ex) {
            plugin.getLogger().warning("Failed to save ecology data: " + ex.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    private static void copyDoubles(ConfigurationSection sec, String name, Map<String, Double> into) {
        if (!sec.contains(name)) {
            return;
        }
        ConfigurationSection s = sec.getConfigurationSection(name);
        if (s == null) {
            return;
        }
        for (Map.Entry<String, Object> e : s.getValues(false).entrySet()) {
            if (e.getValue() instanceof Number n) {
                into.put(e.getKey(), n.doubleValue());
            }
        }
    }

    private static void copyLongs(ConfigurationSection sec, String name, Map<String, Long> into) {
        ConfigurationSection s = sec.getConfigurationSection(name);
        if (s == null) {
            return;
        }
        for (Map.Entry<String, Object> e : s.getValues(false).entrySet()) {
            if (e.getValue() instanceof Number n) {
                into.put(e.getKey(), n.longValue());
            }
        }
    }
}
