package dev.mcplugins.chunksovereignty;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Color;
import org.bukkit.Particle;
import org.bukkit.block.Block;
import org.bukkit.block.data.Ageable;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.Objects;
import java.util.UUID;

public final class SovereigntyPlugin extends JavaPlugin {

    private final Settings settings = new Settings();
    private ChunkIndex index;
    private DomainEngine engine;
    private SovereigntyStore store;
    private volatile boolean dirty;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        settings.load(this);

        index = new ChunkIndex();
        engine = new DomainEngine(this);
        store = new SovereigntyStore(this);
        store.load(index);

        Bukkit.getPluginManager().registerEvents(new ProtectionListener(this), this);
        DomainCommand commands = new DomainCommand(this);
        for (String name : new String[]{"claim", "unclaim", "domain", "trust",
                "untrust", "sovereignty", "cs"}) {
            PluginCommand cmd = getCommand(name);
            if (cmd != null) {
                cmd.setExecutor(commands);
                cmd.setTabCompleter(commands);
            }
        }

        long passTicks = settings.checkIntervalMinutes * 60L * 20L;
        long playTicks = settings.playtimeIntervalSeconds * 20L;
        long ambientTicks = settings.particleIntervalSeconds * 20L;
        long autosaveTicks = settings.autosaveSeconds * 20L;

        Bukkit.getScheduler().runTaskTimer(this, this::playtimeTick,
                playTicks, playTicks);
        Bukkit.getScheduler().runTaskTimer(this, this::passTick,
                passTicks, passTicks);
        Bukkit.getScheduler().runTaskTimer(this, this::borderAmbience,
                ambientTicks, ambientTicks);
        Bukkit.getScheduler().runTaskTimer(this, this::cropBoost,
                200L, 200L);
        Bukkit.getScheduler().runTaskTimer(this, () -> {
            if (dirty) {
                dirty = false;
                store.saveAsync(index);
            }
        }, autosaveTicks, autosaveTicks);

        getLogger().info(() -> "ChunkSovereignty enabled: expansion cost "
                + String.format("%.0f", settings.costPerChunk) + ", upkeep "
                + String.format("%.1f", settings.upkeepPerChunkHour) + "/chunk/h, cap "
                + settings.maxChunks + " chunks.");
    }

    private void playtimeTick() {
        double amount = settings.playtimePerMinute
                * (settings.playtimeIntervalSeconds / 60.0);
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (settings.disabled(p.getWorld().getName())) {
                continue;
            }
            if (index.countOwned(p.getUniqueId()) > 0) {
                index.addInfluence(p.getUniqueId(), amount);
                markDirty();
            }
        }
    }

    private void passTick() {
        var log = engine.runPass();
        if (!log.isEmpty() && settings.debug) {
            log.forEach(l -> getLogger().info("[debug] " + l));
        }
        engine.decayTension(0.9);
    }

    private void borderAmbience() {
        if (!settings.showParticles) {
            return;
        }
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (settings.disabled(p.getWorld().getName())) {
                continue;
            }
            int cx = p.getLocation().getBlockX() >> 4;
            int cz = p.getLocation().getBlockZ() >> 4;
            String w = p.getWorld().getName();
            ChunkIndex.Claim center = new ChunkIndex.Claim(w, cx, cz);
            boolean inClaim = index.ownerAt(center) != null;
            int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
            for (int[] d : dirs) {
                boolean neighborClaimed = index.isClaimed(new ChunkIndex.Claim(
                        w, cx + d[0], cz + d[1]));
                if (inClaim == neighborClaimed && !(inClaim
                        && !sameOwner(center, cx + d[0], cz + d[1]))) {
                    continue;
                }
                double baseX = (cx + 0.5) * 16 + d[0] * 7.5;
                double baseZ = (cz + 0.5) * 16 + d[1] * 7.5;
                double y = p.getLocation().getY();
                double heightOffset = inClaim ? settings.particleHeightInside : settings.particleHeightBorder;
                float dustSize = inClaim ? 0.5f : 0.3f;
                int dustCount = settings.particleDensity;
                for (int i = 0; i < settings.particlePoints; i++) {
                    double along = (i / (double)(settings.particlePoints - 1) - 0.5) * 14.0;
                    double px = d[1] != 0 ? baseX + along : baseX;
                    double pz = d[0] != 0 ? baseZ + along : baseZ;
                    p.spawnParticle(Particle.DUST,
                            new Location(p.getWorld(), px, y + rnd(heightOffset), pz),
                            dustCount, 0, 0.5, 0, 0.02,
                            new Particle.DustOptions(Color.fromRGB(150, 50, 200), dustSize));
                }
            }
        }
    }

    private boolean sameOwner(ChunkIndex.Claim c, int nx, int nz) {
        UUID a = index.ownerAt(c);
        UUID b = index.ownerAt(new ChunkIndex.Claim(c.world(), nx, nz));
        return Objects.equals(a, b);
    }

    private void cropBoost() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (settings.disabled(p.getWorld().getName())) {
                continue;
            }
            ChunkIndex.Claim here = new ChunkIndex.Claim(p.getWorld().getName(),
                    p.getLocation().getBlockX() >> 4, p.getLocation().getBlockZ() >> 4);
            UUID owner = index.ownerAt(here);
            if (owner == null || !owner.equals(p.getUniqueId())) {
                continue;
            }
            int bonus = settings.tierFor(index.countOwned(owner)).cropBonus();
            if (bonus <= 0) {
                continue;
            }
            double chance = bonus / 100.0;
            Location base = p.getLocation();
            for (int i = 0; i < 16; i++) {
                Block b = p.getWorld().getBlockAt(
                        base.getBlockX() + (int) ((Math.random() - 0.5) * 24),
                        base.getBlockY() + (int) ((Math.random() - 0.5) * 8),
                        base.getBlockZ() + (int) ((Math.random() - 0.5) * 24));
                if (!index.ownerAt(new ChunkIndex.Claim(b.getWorld().getName(),
                        b.getX() >> 4, b.getZ() >> 4)).equals(owner)) {
                    continue;
                }
                if (b.getBlockData() instanceof Ageable age
                        && age.getAge() < age.getMaximumAge()
                        && Math.random() < chance) {
                    age.setAge(age.getAge() + 1);
                    b.setBlockData(age);
                }
            }
        }
    }

    private static double rnd(double r) {
        return (Math.random() - 0.5) * r;
    }

    @Override
    public void onDisable() {
        if (store != null && index != null) {
            store.saveSync(index);
        }
    }

    public void markDirty() {
        dirty = true;
    }

    public Settings settings() {
        return settings;
    }

    public ChunkIndex index() {
        return index;
    }

    public DomainEngine engine() {
        return engine;
    }

    public void reloadSettings() {
        reloadConfig();
        settings.load(this);
    }

    static Component text(String msg, NamedTextColor color) {
        return Component.text(msg, color);
    }
}
