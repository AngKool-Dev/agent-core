package dev.mcplugins.echorealms;

import org.bukkit.Bukkit;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class EchoRealmsPlugin extends JavaPlugin {

    private final Settings settings = new Settings();
    private EchoManager manager;
    private EchoStore store;
    private volatile boolean dirty;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        settings.load(this);

        manager = new EchoManager(this);
        store = new EchoStore(this);
        store.load(manager);

        Bukkit.getPluginManager().registerEvents(new EchoListener(this), this);
        EchoCommand executor = new EchoCommand(this);
        PluginCommand cmd = getCommand("echo");
        if (cmd != null) {
            cmd.setExecutor(executor);
            cmd.setTabCompleter(executor);
        }
        PluginCommand er = getCommand("er");
        if (er != null) {
            er.setExecutor(executor);
            er.setTabCompleter(executor);
        }

        long checkTicks = settings.checkIntervalSeconds * 20L;
        long ambientTicks = settings.particleIntervalSeconds * 20L;
        long autosaveTicks = settings.autosaveSeconds * 20L;

        Bukkit.getScheduler().runTaskLater(this, manager::lifecyclePass, 60L);
        Bukkit.getScheduler().runTaskTimer(this, manager::lifecyclePass,
                checkTicks, checkTicks);
        Bukkit.getScheduler().runTaskTimer(this, manager::ambientTick,
                ambientTicks, ambientTicks);
        Bukkit.getScheduler().runTaskTimer(this, () -> {
            if (dirty) {
                dirty = false;
                store.saveAsync(manager);
            }
        }, autosaveTicks, autosaveTicks);

        getLogger().info(() -> "EchoRealms enabled: echoes after "
                + settings.inactiveDays + "d of absence (deep at "
                + settings.deepDays + "d), min " + settings.minBlocks + " blocks.");
    }

    @Override
    public void onDisable() {
        if (manager != null) {
            manager.removeHolograms();
        }
        if (store != null && manager != null) {
            store.saveSync(manager);
        }
    }

    public void markDirty() {
        dirty = true;
    }

    public Settings settings() {
        return settings;
    }

    public EchoManager manager() {
        return manager;
    }

    public boolean playerHasAttuned(UUID uuid) {
        if (manager == null) return false;
        for (EchoRegion region : manager.regions()) {
            for (BuilderSite site : region.sites.values()) {
                if (site.attunedAt.containsKey(uuid)) return true;
            }
        }
        return false;
    }

    public void reloadSettings() {
        reloadConfig();
        settings.load(this);
    }
}
