package dev.mcplugins.mobecology;

import org.bukkit.Bukkit;
import org.bukkit.Chunk;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.world.ChunkLoadEvent;

import java.util.ArrayDeque;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public final class PopulationTracker implements Listener {

    private final MobEcologyPlugin plugin;
    private final BalanceEngine engine;
    private final AdaptationManager adaptation;
    private final Map<RegionKey, EcologyRegion> regions = new ConcurrentHashMap<>();
    private final ArrayDeque<RegionKey> censusQueue = new ArrayDeque<>();

    PopulationTracker(MobEcologyPlugin plugin, BalanceEngine engine, AdaptationManager adaptation) {
        this.plugin = plugin;
        this.engine = engine;
        this.adaptation = adaptation;
    }

    public Map<RegionKey, EcologyRegion> regions() {
        return regions;
    }

    public EcologyRegion region(RegionKey key) {
        EcologyRegion r = regions.get(key);
        if (r == null) {
            r = new EcologyRegion();
            regions.put(key, r);
            censusQueue.offer(key);
        }
        return r;
    }

    public EcologyRegion peek(RegionKey key) {
        return regions.get(key);
    }

    public double estimate(RegionKey key, String species) {
        EcologyRegion r = regions.get(key);
        return r == null ? 0 : r.pop.getOrDefault(species, 0.0);
    }

    public void census(RegionKey key) {
        World w = Bukkit.getWorld(key.world());
        if (w == null) {
            return;
        }
        EcologyRegion r = regions.get(key);
        if (r == null) {
            return;
        }
        double decayPerHour = plugin.settings().decayPerHour;
        if (r.lastCensus > 0 && decayPerHour > 0) {
            double hours = Math.min(48.0, (System.currentTimeMillis() - r.lastCensus) / 3_600_000.0);
            if (hours > 0.05) {
                double factor = Math.pow(1.0 - decayPerHour, hours);
                java.util.Iterator<Map.Entry<String, Double>> it = r.pressure.entrySet().iterator();
                while (it.hasNext()) {
                    Map.Entry<String, Double> e = it.next();
                    double v = e.getValue() * factor;
                    if (v < 0.5) {
                        it.remove();
                    } else {
                        e.setValue(v);
                    }
                }
            }
        }
        int grid = plugin.settings().regionChunks;
        java.util.Map<String, Double> counts = new java.util.HashMap<>();
        for (int cx = key.rx() * grid; cx < (key.rx() + 1) * grid; cx++) {
            for (int cz = key.rz() * grid; cz < (key.rz() + 1) * grid; cz++) {
                if (!w.isChunkLoaded(cx, cz)) {
                    continue;
                }
                Chunk chunk = w.getChunkAt(cx, cz);
                for (Entity e : chunk.getEntities()) {
                    if (!(e instanceof LivingEntity le) || le instanceof Player || !(le instanceof Mob)) {
                        continue;
                    }
                    if (plugin.classify(le) == MobEcologyPlugin.Category.IGNORED) {
                        continue;
                    }
                    counts.merge(plugin.typeId(le), 1.0, Double::sum);
                }
            }
        }
        r.pop.clear();
        r.pop.putAll(counts);
        long now = System.currentTimeMillis();
        for (Map.Entry<String, Double> e : counts.entrySet()) {
            if (e.getValue() > 0) {
                r.lastSeen.put(e.getKey(), now);
            }
        }
        r.lastCensus = now;
    }

    void startTasks() {
        long period = Math.max(5, plugin.settings().censusIntervalSeconds) * 20L;
        Bukkit.getScheduler().runTaskTimer(plugin, this::censusStep, period, period);
    }

    private void censusStep() {
        int budget = Math.max(1, plugin.settings().regionsPerTick);
        while (budget-- > 0 && !censusQueue.isEmpty()) {
            RegionKey key = censusQueue.poll();
            if (key == null) {
                break;
            }
            if (!plugin.disabled(key.world())) {
                census(key);
            }
            censusQueue.offer(key);
        }
    }

    void seedLoadedChunks() {
        int grid = plugin.settings().regionChunks;
        for (World w : Bukkit.getWorlds()) {
            if (plugin.disabled(w.getName())) {
                continue;
            }
            for (Chunk c : w.getLoadedChunks()) {
                region(RegionKey.of(w, c.getX(), c.getZ(), grid));
            }
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onSpawn(CreatureSpawnEvent event) {
        LivingEntity le = event.getEntity();
        MobEcologyPlugin.Category cat = plugin.classify(le);
        if (cat == MobEcologyPlugin.Category.IGNORED || !(le instanceof Mob)) {
            return;
        }
        World w = event.getLocation().getWorld();
        if (w == null || plugin.disabled(w.getName())) {
            return;
        }
        RegionKey key = RegionKey.of(w, event.getLocation().getBlockX() >> 4,
                event.getLocation().getBlockZ() >> 4, plugin.settings().regionChunks);
        String id = plugin.typeId(le);
        if (engine.shouldGate(event.getSpawnReason(), key, cat, id)) {
            event.setCancelled(true);
            return;
        }
        EcologyRegion r = region(key);
        r.pop.merge(id, 1.0, Double::sum);
        r.lastSeen.put(id, System.currentTimeMillis());
        if (!(le instanceof org.bukkit.entity.AbstractVillager)) {
            adaptation.apply(le, cat, r, id);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onDeath(EntityDeathEvent event) {
        LivingEntity le = event.getEntity();
        if (le instanceof Player || !(le instanceof Mob)) {
            return;
        }
        MobEcologyPlugin.Category cat = plugin.classify(le);
        if (cat == MobEcologyPlugin.Category.IGNORED) {
            return;
        }
        World w = le.getWorld();
        if (plugin.disabled(w.getName())) {
            return;
        }
        EcologyRegion r = regions.get(RegionKey.of(w, le.getLocation().getBlockX() >> 4,
                le.getLocation().getBlockZ() >> 4, plugin.settings().regionChunks));
        if (r == null) {
            return;
        }
        String id = plugin.typeId(le);
        r.pop.merge(id, -1.0, Double::sum);
        if (r.pop.get(id) < 0) {
            r.pop.put(id, 0.0);
        }
        r.lastSeen.put(id, System.currentTimeMillis());
        r.pressure.merge(id, plugin.settings().killWeight, Double::sum);
    }

    @EventHandler
    public void onChunkLoad(ChunkLoadEvent event) {
        if (plugin.disabled(event.getWorld().getName())) {
            return;
        }
        RegionKey key = RegionKey.of(event.getWorld(), event.getChunk().getX(),
                event.getChunk().getZ(), plugin.settings().regionChunks);
        if (!regions.containsKey(key)) {
            region(key);
        }
    }
}
