package dev.mcplugins.skillforge;

import org.bukkit.Bukkit;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class SkillForgePlugin extends JavaPlugin {

    private final Settings settings = new Settings();
    private SkillEngine engine;
    private SkillStore store;
    private volatile boolean dirty;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        settings.load(this);

        engine = new SkillEngine(this);
        store = new SkillStore(this);
        store.load(engine);

        new CraftListener(this);

        SkillCommand commands = new SkillCommand(this);
        register("skillforge", commands);
        register("sf", commands);
        register("skill", commands);
        register("apprentice", commands);
        register("award", commands);
        register("craft", commands);

        long autosaveTicks = settings.autosaveSeconds * 20L;
        Bukkit.getScheduler().runTaskTimer(this, () -> {
            if (dirty) {
                dirty = false;
                store.saveAsync(engine);
            }
        }, autosaveTicks, autosaveTicks);

        getLogger().info(() -> String.format(
                "SkillForge enabled — %d specializations, %d skills, %d tiers, "
                        + "bossbars=%s, vault=%s",
                settings.specializations().size(),
                settings.totalSkills(),
                settings.tiers().size(),
                settings.bossbarEnabled,
                settings.vaultEnabled));
    }

    private void register(String name, SkillCommand executor) {
        var cmd = getCommand(name);
        if (cmd != null) {
            cmd.setExecutor(executor);
            cmd.setTabCompleter(executor);
        }
    }
    @Override
    public void onDisable() {
        if (store != null && engine != null) {
            store.saveSync(engine);
        }
    }

    public void markDirty() {
        dirty = true;
    }

    public Settings settings() {
        return settings;
    }

    public SkillEngine engine() {
        return engine;
    }
}
