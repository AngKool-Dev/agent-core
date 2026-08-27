package dev.mcplugins.mobecology;

import org.bukkit.Location;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.scheduler.BukkitTask;

import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

public final class BalanceEngine {

    private final MobEcologyPlugin plugin;
    private final Map<String, EntityType> typeCache = new HashMap<>();
    private BukkitTask boostTask;

    BalanceEngine(MobEcologyPlugin plugin) {
        this.plugin = plugin;
        for (EntityType t : EntityType.values()) {
            typeCache.put(t.name().toLowerCase(Locale.ROOT), t);
        }
    }

    boolean shouldGate(CreatureSpawnEvent.SpawnReason reason, RegionKey key,
                       MobEcologyPlugin.Category cat, String id) {
        MobEcologyPlugin.Settings s = plugin.settings();
        if (!s.gatedReasons.contains(reason)) {
            return false;
        }
        EcologyRegion r = plugin.tracker().peek(key);
        if (r == null) {
            return false;
        }
        String idLow = id.toLowerCase(Locale.ROOT);
        Double speciesCap = s.capacityOverrides.get(idLow);
        if (speciesCap != null && speciesCap > 0) {
            if (plugin.tracker().estimate(key, id) >= speciesCap * s.overFactor) {
                return true;
            }
        } else {
            double total = r.total(plugin.speciesCategories(), cat);
            double cap = s.capacity(cat);
            if (total >= cap * s.overFactor) {
                return true;
            }
        }
        List<String> prey = s.foodWeb.get(id.toLowerCase(Locale.ROOT));
        if (prey != null && !prey.isEmpty()) {
            boolean any = false;
            for (String p : prey) {
                if (plugin.tracker().estimate(key, p) > 0.5) {
                    any = true;
                    break;
                }
            }
            if (!any) {
                return true;
            }
        }
        return false;
    }

    void startBoostTask() {
        MobEcologyPlugin.Settings s = plugin.settings();
        if (!s.boostEnabled) {
            return;
        }
        long period = Math.max(10, s.boostIntervalSeconds) * 20L;
        boostTask = Bukkit.getScheduler().runTaskTimer(plugin, this::boostRun, period, period);
    }

    void stopTasks() {
        if (boostTask != null) {
            boostTask.cancel();
        }
    }

    public double effectiveCapacity(String speciesLower, MobEcologyPlugin.Category cat) {
        MobEcologyPlugin.Settings s = plugin.settings();
        Double o = s.capacityOverrides.get(speciesLower);
        if (o != null && o > 0) {
            return o;
        }
        return s.capacity(cat);
    }

    private void boostRun() {
        MobEcologyPlugin.Settings s = plugin.settings();
        int spawned = 0;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (spawned >= s.boostPerRun) {
                break;
            }
            World w = p.getWorld();
            if (plugin.disabled(w.getName())) {
                continue;
            }
            RegionKey key = RegionKey.of(w, p.getLocation().getBlockX() >> 4,
                    p.getLocation().getBlockZ() >> 4, s.regionChunks);
            EcologyRegion r = plugin.tracker().peek(key);
            if (r == null) {
                continue;
            }
            MobEcologyPlugin.Category weakest = weakestUnder(r);
            if (weakest == null) {
                continue;
            }
            List<String> candidates = s.boostDefaults.get(weakest.name().toLowerCase(Locale.ROOT));
            if (candidates == null || candidates.isEmpty()) {
                continue;
            }
            if (weakest == MobEcologyPlugin.Category.HOSTILE
                    && w.getTime() < 12_300L && !w.hasStorm()) {
                candidates = candidates.stream()
                        .filter(cd -> s.daySafeHostiles.contains(cd.toLowerCase(Locale.ROOT)))
                        .toList();
                if (candidates.isEmpty()) {
                    continue;
                }
            }
            String species = candidates.get(ThreadLocalRandom.current().nextInt(candidates.size()));
            EntityType type = typeCache.get(species.toLowerCase(Locale.ROOT));
            if (type == null || !type.isAlive()) {
                continue;
            }
            ThreadLocalRandom rnd = ThreadLocalRandom.current();
            Location at = weakest == MobEcologyPlugin.Category.WATER
                    ? findWaterSpot(w, p, s.boostRadius)
                    : landSpot(w, p, s.boostRadius, rnd);
            if (at == null) {
                continue;
            }
            int group = 1 + rnd.nextInt(2);
            for (int i = 0; i < group && spawned < s.boostPerRun; i++) {
                w.spawnEntity(at, type);
                spawned++;
            }
        }
    }

    private Location landSpot(World w, Player p, int radius, ThreadLocalRandom rnd) {
        int bx = p.getLocation().getBlockX() + rnd.nextInt(-radius, radius + 1);
        int bz = p.getLocation().getBlockZ() + rnd.nextInt(-radius, radius + 1);
        if (!w.isChunkLoaded(bx >> 4, bz >> 4)) {
            return null;
        }
        return w.getHighestBlockAt(bx, bz).getLocation().add(0.5, 1.05, 0.5);
    }

    private Location findWaterSpot(World w, Player p, int radius) {
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        for (int attempt = 0; attempt < 4; attempt++) {
            int bx = p.getLocation().getBlockX() + rnd.nextInt(-radius, radius + 1);
            int bz = p.getLocation().getBlockZ() + rnd.nextInt(-radius, radius + 1);
            if (!w.isChunkLoaded(bx >> 4, bz >> 4)) {
                continue;
            }
            int topY = Math.min((int) Math.min(p.getLocation().getY() + 20, 100), w.getMaxHeight() - 1);
            for (int y = topY; y >= Math.max(20, w.getMinHeight()); y--) {
                if (w.getBlockAt(bx, y, bz).getType() == org.bukkit.Material.WATER) {
                    return new Location(w, bx + 0.5, y + 0.1, bz + 0.5);
                }
            }
        }
        return null;
    }

    private MobEcologyPlugin.Category weakestUnder(EcologyRegion r) {
        MobEcologyPlugin.Settings s = plugin.settings();
        MobEcologyPlugin.Category best = null;
        double bestRatio = Double.MAX_VALUE;
        for (MobEcologyPlugin.Category cat : new MobEcologyPlugin.Category[]{
                MobEcologyPlugin.Category.PASSIVE, MobEcologyPlugin.Category.HOSTILE,
                MobEcologyPlugin.Category.AMBIENT, MobEcologyPlugin.Category.WATER}) {
            double cap = s.capacity(cat);
            if (cap <= 0) {
                continue;
            }
            double total = r.total(plugin.speciesCategories(), cat);
            if (total < cap * s.underFraction) {
                double ratio = total / cap;
                if (ratio < bestRatio) {
                    bestRatio = ratio;
                    best = cat;
                }
            }
        }
        return best;
    }

    double imbalanceScore(EcologyRegion r) {
        MobEcologyPlugin.Settings s = plugin.settings();
        double sum = 0;
        double caps = 0;
        for (MobEcologyPlugin.Category cat : MobEcologyPlugin.Category.values()) {
            if (cat == MobEcologyPlugin.Category.IGNORED) {
                continue;
            }
            double cap = s.capacity(cat);
            if (cap <= 0) {
                continue;
            }
            double total = r.total(plugin.speciesCategories(), cat);
            sum += Math.abs(Math.min(total, cap * 1.25) - cap);
            caps += cap;
        }
        return caps <= 0 ? 0 : sum / caps;
    }
}
