package dev.mcplugins.chunksovereignty;

import org.bukkit.configuration.ConfigurationSection;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class Settings {

    public record Tier(int at, String name, int cropBonus) {
    }

    public double startInfluence = 50;
    public double costPerChunk = 25;
    public double upkeepPerChunkHour = 1.0;
    public double playtimePerMinute = 0.5;
    public double placeInfluence = 0.05;
    public int maxChunks = 24;
    public List<Tier> tiers = new ArrayList<>();
    public boolean protection = true;
    public boolean announceEnter = true;
    public boolean showParticles = true;
    public int particleIntervalSeconds = 5;
    public int particlePoints = 16;
    public int particleDensity = 2;
    public double particleHeightInside = 2.0;
    public double particleHeightBorder = 1.2;
    public int checkIntervalMinutes = 60;
    public int playtimeIntervalSeconds = 60;
    public Set<String> disabledWorlds = new HashSet<>();
    public int autosaveSeconds = 300;
    public boolean debug = false;

    public void load(SovereigntyPlugin plugin) {
        var c = plugin.getConfig();
        startInfluence = Math.max(0, c.getDouble("economy.start-influence", 50));
        costPerChunk = Math.max(1, c.getDouble("economy.cost-per-chunk", 25));
        upkeepPerChunkHour = Math.max(0, c.getDouble("economy.upkeep-per-chunk-hour", 1.0));
        playtimePerMinute = Math.max(0, c.getDouble("economy.playtime-per-minute", 0.5));
        placeInfluence = Math.max(0, c.getDouble("economy.place-influence", 0.05));
        maxChunks = Math.max(1, c.getInt("claims.max-chunks", 24));
        protection = c.getBoolean("protection.enabled", true);
        announceEnter = c.getBoolean("protection.announce-enter", true);
        particleIntervalSeconds = Math.max(2, c.getInt("ambience.particle-interval-seconds", 5));
        showParticles = c.getBoolean("ambience.show-particles", true);
        particlePoints = Math.max(4, Math.min(32, c.getInt("ambience.particle-points", 16)));
        particleDensity = Math.max(1, Math.min(10, c.getInt("ambience.particle-density", 2)));
        particleHeightInside = c.getDouble("ambience.particle-height-inside", 2.0);
        particleHeightBorder = c.getDouble("ambience.particle-height-border", 1.2);
        checkIntervalMinutes = Math.max(1, c.getInt("engine.check-interval-minutes", 60));
        playtimeIntervalSeconds = Math.max(10, c.getInt("engine.playtime-interval-seconds", 60));
        disabledWorlds = new HashSet<>(c.getStringList("worlds.disabled"));
        autosaveSeconds = Math.max(60, c.getInt("storage.autosave-seconds", 300));
        debug = c.getBoolean("debug", false);

        tiers.clear();
        ConfigurationSection sec = c.getConfigurationSection("claims.tiers");
        if (sec != null) {
            for (String key : sec.getKeys(false)) {
                ConfigurationSection t = sec.getConfigurationSection(key);
                if (t == null) {
                    continue;
                }
                try {
                    tiers.add(new Tier(Integer.parseInt(key), t.getString("name", "Tier"),
                            t.getInt("crop-bonus", 0)));
                } catch (NumberFormatException ignored) {
                }
            }
            tiers.sort((a, b) -> Integer.compare(a.at(), b.at()));
        }
        if (tiers.isEmpty()) {
            tiers.add(new Tier(1, "Hamlet", 0));
        }
    }

    public Tier tierFor(int chunks) {
        Tier best = tiers.get(0);
        for (Tier t : tiers) {
            if (chunks >= t.at()) {
                best = t;
            }
        }
        return best;
    }

    public boolean disabled(String world) {
        return disabledWorlds.contains(world);
    }
}
