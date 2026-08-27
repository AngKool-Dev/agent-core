package dev.mcplugins.echorealms;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

public final class EchoManager {

    private static final List<String> LORE_OPENERS = List.of(
            "Whoever raised these walls left in a hurry",
            "The mortar still remembers careful hands",
            "Wind moves through doorways no one closes anymore",
            "Something tended here once, and the ground knows it");
    private static final List<String> LORE_CLOSERS = List.of(
            "The echo does not judge. It only remembers",
            "Take what you need, but say it quietly",
            "Some visitors leave flowers. Some leave footprints. Both fade",
            "The shards hum when you look away from them");

    private final EchoRealmsPlugin plugin;
    private final Map<String, EchoRegion> regions = new HashMap<>();
    private final Map<String, Long> manifestedAt = new HashMap<>();
    private final Map<String, TextDisplay> holograms = new HashMap<>();

    public EchoManager(EchoRealmsPlugin plugin) {
        this.plugin = plugin;
    }

    public record RegionKey(String world, int rx, int rz) {
        String id() {
            return world + "|" + rx + "|" + rz;
        }
    }

    public RegionKey regionKey(World w, int chunkX, int chunkZ) {
        int rc = plugin.settings().regionChunks;
        return new RegionKey(w.getName(), Math.floorDiv(chunkX, rc), Math.floorDiv(chunkZ, rc));
    }

    public EchoRegion region(RegionKey key) {
        return regions.computeIfAbsent(key.id(), k -> new EchoRegion(key.world(), key.rx(), key.rz()));
    }

    public EchoRegion peek(RegionKey key) {
        return regions.get(key.id());
    }

    public void recordPlacement(Player p, World w, int x, int y, int z) {
        EchoManager.RegionKey rk = regionKey(w, x >> 4, z >> 4);
        EchoRegion region = region(rk);
        UUID builder = p.getUniqueId();
        BuilderSite site = region.site(builder);
        String siteKey = rk.id() + "|" + builder;
        boolean wasManifested = isManifested(siteKey);
        site.record(x, y, z, System.currentTimeMillis());
        plugin.markDirty();
        if (wasManifested) {
            dissolve(siteKey);
            p.sendMessage(Component.text(
                    "\u29E1 Your touch scatters the echo; the memory yields to living hands.",
                    NamedTextColor.LIGHT_PURPLE));
        }
    }

    public boolean isManifested(String siteKey) {
        return manifestedAt.containsKey(siteKey);
    }

    public long ageDays(String siteKey) {
        Long at = manifestedAt.get(siteKey);
        if (at == null) {
            return plugin.settings().inactiveDays;
        }
        long ageMs = System.currentTimeMillis() - at + plugin.settings().inactiveDays * 86_400_000L;
        return ageMs / 86_400_000L;
    }

    public boolean isDeep(String siteKey) {
        return ageDays(siteKey) >= plugin.settings().deepDays;
    }

    public void lifecyclePass() {
        Settings s = plugin.settings();
        long now = System.currentTimeMillis();
        final boolean dbg = s.debug;
        if (dbg) {
            plugin.getLogger().info(() -> "[debug] lifecycle pass: regions="
                    + regions.size() + " manifestedBefore=" + manifestedAt.size());
        }
        for (EchoRegion region : regions.values()) {
            if (s.disabled(region.world)) {
                continue;
            }
            RegionKey rk = new RegionKey(region.world, region.rx, region.rz);
            for (Map.Entry<UUID, BuilderSite> e : region.sites.entrySet()) {
                BuilderSite site = e.getValue();
                String key = rk.id() + "|" + e.getKey();
                long requiredMs = s.inactiveDays * 86_400_000L;
                if (s.inactiveDays == 0) {
                    // Test mode: require one full silent cycle so freshly
                    // active builders are not instantly re-manifested.
                    requiredMs = s.checkIntervalSeconds * 1000L;
                }
                boolean qualifies = site.count >= s.minBlocks
                        && now - site.lastActivity >= requiredMs;
                if (qualifies && !manifestedAt.containsKey(key)) {
                    manifest(rk, key, e.getKey(), site);
                } else if (!qualifies && manifestedAt.containsKey(key)) {
                    dissolve(key);
                }
            }
        }
        plugin.markDirty();
    }

    private void manifest(RegionKey rk, String key, UUID builder, BuilderSite site) {
        if (manifestedAt.containsKey(key)) {
            return;
        }
        World w = Bukkit.getWorld(rk.world());
        if (w == null) {
            return;
        }
        if (plugin.settings().debug) {
            plugin.getLogger().info(() -> "[debug] manifesting " + key
                    + " (manifested=" + manifestedAt.size() + ")");
        }
        manifestedAt.put(key, site.lastActivity);
        Location loc = new Location(w, site.centroidX() + 0.5,
                Math.min(w.getMaxHeight() - 2.0, site.maxY + 3.0), site.centroidZ() + 0.5);
        String name = Bukkit.getOfflinePlayer(builder).getName();
        String shown = name == null ? "a forgotten hand" : name;
        TextDisplay td = w.spawn(loc, TextDisplay.class, display -> {
            display.text(Component.text("\u29E1 Echo of " + shown + "'s works",
                            NamedTextColor.LIGHT_PURPLE)
                    .append(Component.text("\n" + site.count + " blocks, fading into memory",
                            NamedTextColor.GRAY)));
            display.setBillboard(Display.Billboard.CENTER);
            display.setViewRange(0.6f);
            display.setSeeThrough(false);
            display.setPersistent(false);
        });
        holograms.put(key, td);
        if (plugin.settings().announceManifest) {
            int bx = rk.rx() * plugin.settings().regionChunks * 16;
            int bz = rk.rz() * plugin.settings().regionChunks * 16;
            Bukkit.broadcast(Component.text("\u29E1 An echo stirs near " + bx + ", " + bz
                    + " (" + rk.world() + ") - works of " + shown + " have begun to fade.",
                    NamedTextColor.LIGHT_PURPLE));
        }
    }

    private void dissolve(String key) {
        manifestedAt.remove(key);
        TextDisplay td = holograms.remove(key);
        if (td != null && td.isValid()) {
            td.remove();
        }
        plugin.markDirty();
    }

    public void dissolveAllOf(UUID builder) {
        for (String key : new ArrayList<>(manifestedAt.keySet())) {
            int idx = key.lastIndexOf('|');
            if (idx <= 0) {
                continue;
            }
            try {
                if (!UUID.fromString(key.substring(idx + 1)).equals(builder)) {
                    continue;
                }
            } catch (IllegalArgumentException ignored) {
                continue;
            }
            dissolve(key);
            Player p = Bukkit.getPlayer(builder);
            if (p != null && p.isOnline()) {
                p.sendMessage(Component.text(
                        "\u29E1 Your returning presence dissolves an old echo.",
                        NamedTextColor.LIGHT_PURPLE));
            }
        }
    }

    public void ambientTick() {
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        for (EchoRegion region : regions.values()) {
            World w = Bukkit.getWorld(region.world);
            if (w == null || plugin.settings().disabled(region.world)) {
                continue;
            }
            RegionKey rk = new RegionKey(region.world, region.rx, region.rz);
            for (Map.Entry<UUID, BuilderSite> e : region.sites.entrySet()) {
                String key = rk.id() + "|" + e.getKey();
                if (!manifestedAt.containsKey(key)) {
                    continue;
                }
                BuilderSite site = e.getValue();
                Location center = new Location(w, site.centroidX(), site.maxY, site.centroidZ());
                boolean anyNear = false;
                for (Player p : Bukkit.getOnlinePlayers()) {
                    if (p.getWorld().equals(w)
                            && p.getLocation().toVector().distanceSquared(center.toVector()) < 96 * 96) {
                        anyNear = true;
                        break;
                    }
                }
                if (!anyNear) {
                    continue;
                }
                double r = Math.min(plugin.settings().maxRadius, site.radius());
                double height = Math.max(4, site.maxY - site.minY + 4);
                for (int i = 0; i < 8; i++) {
                    double ang = rnd.nextDouble() * Math.PI * 2;
                    double dist = rnd.nextDouble() * r;
                    w.spawnParticle(Particle.PORTAL,
                            site.centroidX() + Math.cos(ang) * dist,
                            site.minY + rnd.nextDouble() * height,
                            site.centroidZ() + Math.sin(ang) * dist,
                            6, 0.3, 0.5, 0.3, 0.02);
                }
            }
        }
    }

    public List<String> listLines() {
        List<String> out = new ArrayList<>();
        if (manifestedAt.isEmpty()) {
            out.add("No echoes are currently manifest.");
            return out;
        }
        out.add("Manifest echoes: " + manifestedAt.size());
        for (Map.Entry<String, Long> e : new TreeMap<>(manifestedAt).entrySet()) {
            String[] parts = e.getKey().split("\\|");
            String builderName = "unknown";
            try {
                String n = Bukkit.getOfflinePlayer(UUID.fromString(parts[3])).getName();
                if (n != null) {
                    builderName = n;
                }
            } catch (Exception ignored) {
            }
            out.add(String.format(" %s (%s,%s) - %s's works - faded %dd ago%s",
                    parts[0], parts[1], parts[2], builderName, ageDays(e.getKey()),
                    isDeep(e.getKey()) ? " [DEEP]" : ""));
        }
        return out;
    }

    public ManifestedSite at(Location loc) {
        for (EchoRegion region : regions.values()) {
            if (!region.world.equals(loc.getWorld().getName())) {
                continue;
            }
            RegionKey rk = new RegionKey(region.world, region.rx, region.rz);
            for (Map.Entry<UUID, BuilderSite> e : region.sites.entrySet()) {
                String key = rk.id() + "|" + e.getKey();
                if (!manifestedAt.containsKey(key)) {
                    continue;
                }
                BuilderSite site = e.getValue();
                double dx = loc.getX() - site.centroidX();
                double dz = loc.getZ() - site.centroidZ();
                double above = loc.getY() - (site.maxY + 6);
                double below = (site.minY - 4) - loc.getY();
                if (dx * dx + dz * dz <= site.radius() * site.radius()
                        && above <= 0 && below <= 0) {
                    return new ManifestedSite(key, e.getKey(), site);
                }
            }
        }
        return null;
    }

    public record ManifestedSite(String key, UUID builder, BuilderSite site) {
    }

    public String loreFor(ManifestedSite site, Player viewer) {
        int seed = (site.key() + viewer.getName()).hashCode();
        String opener = LORE_OPENERS.get(Math.floorMod(seed, LORE_OPENERS.size()));
        String closer = LORE_CLOSERS.get(Math.floorMod(seed / 7, LORE_CLOSERS.size()));
        return opener + ". " + closer + ".";
    }

    public boolean attuneAllowed(ManifestedSite site, Player p) {
        Long at = site.site().attunedAt.get(p.getUniqueId());
        if (at == null) {
            return true;
        }
        return System.currentTimeMillis() - at >= plugin.settings().cooldownDays * 86_400_000L;
    }

    public void markAttuned(ManifestedSite site, Player p) {
        site.site().attunedAt.put(p.getUniqueId(), System.currentTimeMillis());
        plugin.markDirty();
    }

    public Iterable<EchoRegion> regions() {
        return regions.values();
    }

    public Map<String, Long> manifestState() {
        return manifestedAt;
    }

    public void restoreState(Map<String, Long> state) {
        manifestedAt.putAll(state);
    }

    public void removeHolograms() {
        for (TextDisplay td : holograms.values()) {
            if (td.isValid()) {
                td.remove();
            }
        }
        holograms.clear();
    }
}
