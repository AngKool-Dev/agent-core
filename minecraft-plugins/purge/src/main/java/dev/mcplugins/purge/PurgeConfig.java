package dev.mcplugins.purge;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.File;
import java.util.Locale;
import java.util.Set;
import java.util.HashSet;
import java.util.List;
import java.util.ArrayList;
import org.bukkit.Material;

public final class PurgeConfig {

    private final PurgePlugin plugin;
    private YamlConfiguration config;

    public boolean enabled = true;
    public long intervalSeconds = 600;
    public long warnBeforeSeconds = 10;
    public boolean broadcastClear = true;

    public boolean warn = true;
    public boolean broadcastSummary = true;

    public final ClearingSettings clearing = new ClearingSettings();
    public final Messages messages = new Messages();

    public PurgeConfig(PurgePlugin plugin) {
        this.plugin = plugin;
        reload(plugin);
    }

    public void reload(PurgePlugin plugin) {
        File file = new File(plugin.getDataFolder(), "config.yml");
        if (!file.exists()) {
            plugin.saveResource("config.yml", false);
        }
        config = YamlConfiguration.loadConfiguration(file);
        load();
    }

    private void load() {
        ConfigurationSection s = config.getConfigurationSection("settings");
        if (s != null) {
            enabled = s.getBoolean("enabled", true);
            intervalSeconds = Math.max(60, s.getLong("interval-seconds", 600));
            warnBeforeSeconds = Math.max(0, s.getLong("warn-before-seconds", 10));
            broadcastClear = s.getBoolean("broadcast-clear", true);
        }

        warn = config.getBoolean("warn", true);
        broadcastSummary = config.getBoolean("broadcast-summary", true);

        ConfigurationSection clearSec = config.getConfigurationSection("clearing");
        if (clearSec != null) {
            clearing.items = clearSec.getBoolean("items", true);

            ConfigurationSection itemsSec = clearSec.getConfigurationSection("items");
            if (itemsSec != null) {
                clearing.itemsSettings.enabled = itemsSec.getBoolean("enabled", true);
                clearing.itemsSettings.gracePeriodSeconds = Math.max(0, itemsSec.getInt("grace-period-seconds", 0));
                List<String> whitelistNames = itemsSec.getStringList("whitelist");
                if (!whitelistNames.isEmpty()) {
                    Set<Material> whitelist = new HashSet<>();
                    for (String name : whitelistNames) {
                        Material mat = Material.matchMaterial(name);
                        if (mat != null) {
                            whitelist.add(mat);
                        }
                    }
                    if (!whitelist.isEmpty()) {
                        clearing.itemsSettings.whitelist = whitelist;
                    }
                }
            }

            ConfigurationSection mobsSec = clearSec.getConfigurationSection("mobs");
            if (mobsSec != null) {
                clearing.mobs.enabled = mobsSec.getBoolean("enabled", true);
                clearing.mobs.hostiles = mobsSec.getBoolean("hostiles", true);
                clearing.mobs.passives = mobsSec.getBoolean("passives", true);
                clearing.mobs.passiveCapPerWorld = Math.max(0, mobsSec.getInt("passive-cap-per-world", 40));
                clearing.mobs.protectTamed = mobsSec.getBoolean("protect-tamed", true);
                clearing.mobs.protectNamed = mobsSec.getBoolean("protect-named", true);
                clearing.mobs.keepVillagers = mobsSec.getBoolean("keep-villagers", true);
                clearing.mobs.clearFallingBlocks = mobsSec.getBoolean("clear-falling-blocks", true);
                List<String> protectedTypes = mobsSec.getStringList("protected-entity-types");
                if (!protectedTypes.isEmpty()) {
                    clearing.mobs.protectedEntityTypes = protectedTypes;
                }

                ConfigurationSection disabledSec = mobsSec.getConfigurationSection("disabled-worlds");
                if (disabledSec != null) {
                    clearing.mobs.disabledWorlds = new HashSet<>(disabledSec.getStringList(""));
                } else {
                    clearing.mobs.disabledWorlds = new HashSet<>();
                }
            }
        }

        ConfigurationSection msgSec = config.getConfigurationSection("messages");
        if (msgSec != null) {
            messages.prefix = msgSec.getString("prefix", "&8[&6Purge&8] ");
            messages.enable = msgSec.getString("enable", "&aAuto-purge enabled. Interval: &e{interval}&a.");
            messages.disable = msgSec.getString("disable", "&cAuto-purge disabled.");
            messages.reload = msgSec.getString("reload", "&aPurge configuration reloaded.");
            messages.warn = msgSec.getString("warn", "&e&l! &cPurging dropped items and excess mobs in &e{seconds}&c second(s)...");
            messages.clearedItems = msgSec.getString("cleared-items", "&aRemoved &e{items}&a dropped item(s).");
            messages.clearedHostiles = msgSec.getString("cleared-hostiles", "&aRemoved &e{hostiles}&a hostile mob(s).");
            messages.clearedPassives = msgSec.getString("cleared-passives", "&aRemoved &e{passives}&a excess passive mob(s).");
            messages.summary = msgSec.getString("summary", "&7Auto-purge complete: &e{items} &7items, &e{hostiles} &7hostiles, &e{passives} &7excess passives removed.");
            messages.statusEnabled = msgSec.getString("status-enabled", "&aAuto-purge is &2ENABLED&a (every &e{interval}&a seconds).");
            messages.statusDisabled = msgSec.getString("status-disabled", "&cAuto-purge is &4DISABLED&c.");
            messages.manualClear = msgSec.getString("manual-clear", "&aManual purge complete: &e{items} &aitems, &e{hostiles} &ahostiles, &e{passives} &aexcess passives removed.");
            messages.nothingToClear = msgSec.getString("nothing-to-clear", "&7Nothing to purge.");
            messages.noPermission = msgSec.getString("no-permission", "&cYou don't have permission to do that.");
        }
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
        config.set("settings.enabled", enabled);
        save();
    }

    public long getIntervalSeconds() {
        return intervalSeconds;
    }

    public long getIntervalTicks() {
        return intervalSeconds * 20L;
    }

    public long getWarnBeforeTicks() {
        return warnBeforeSeconds * 20L;
    }

    public long getWarnBeforeSeconds() {
        return warnBeforeSeconds;
    }

    public Messages getMessages() {
        return messages;
    }

    private void save() {
        try {
            config.save(new File(plugin.getDataFolder(), "config.yml"));
        } catch (Exception e) {
            plugin.getLogger().severe("Could not save config.yml: " + e.getMessage());
        }
    }

    public static final class ClearingSettings {
        public boolean items = true;
        public final ItemSettings itemsSettings = new ItemSettings();
        public final MobSettings mobs = new MobSettings();
    }

    public static final class ItemSettings {
        public boolean enabled = true;
        public int gracePeriodSeconds = 0;
        public Set<Material> whitelist = Set.of(
                Material.NETHERITE_INGOT, Material.NETHERITE_SWORD, Material.NETHERITE_PICKAXE,
                Material.NETHERITE_AXE, Material.NETHERITE_SHOVEL, Material.NETHERITE_HOE,
                Material.NETHERITE_HELMET, Material.NETHERITE_CHESTPLATE, Material.NETHERITE_LEGGINGS,
                Material.NETHERITE_BOOTS, Material.TOTEM_OF_UNDYING, Material.ELYTRA,
                Material.DRAGON_HEAD, Material.DRAGON_EGG, Material.BEACON, Material.NETHER_STAR
        );
    }

    public static final class MobSettings {
        public boolean enabled = true;
        public boolean hostiles = true;
        public boolean passives = true;
        public int passiveCapPerWorld = 40;
        public boolean protectTamed = true;
        public boolean protectNamed = true;
        public boolean keepVillagers = true;
        public boolean clearFallingBlocks = true;
        public Set<String> disabledWorlds = new HashSet<>();
        public List<String> protectedEntityTypes = List.of(
                "COW", "PIG", "SHEEP", "CHICKEN", "MOOSHROOM", "RABBIT",
                "HORSE", "DONKEY", "MULE", "LLAMA", "TRADER_LLAMA", "CAMEL",
                "FOX", "FROG", "GOAT", "HORSE", "SKELETON_HORSE", "ZOMBIE_HORSE",
                "BEE", "CAT", "WOLF", "PARROT", "AXOLOTL", "TURTLE", "DOLPHIN",
                "POLAR_BEAR", "ARMADILLO", "BREEZE", "BOGGED"
        );
    }

    public static final class Messages {
        public String prefix = "&8[&6Purge&8] ";
        public String enable = "&aAuto-purge enabled. Interval: &e{interval}&a.";
        public String disable = "&cAuto-purge disabled.";
        public String reload = "&aPurge configuration reloaded.";
        public String warn = "&e&l! &cPurging dropped items and excess mobs in &e{seconds}&c second(s)...";
        public String clearedItems = "&aRemoved &e{items}&a dropped item(s).";
        public String clearedHostiles = "&aRemoved &e{hostiles}&a hostile mob(s).";
        public String clearedPassives = "&aRemoved &e{passives}&a excess passive mob(s).";
        public String summary = "&7Auto-purge complete: &e{items} &7items, &e{hostiles} &7hostiles, &e{passives} &7excess passives removed.";
        public String statusEnabled = "&aAuto-purge is &2ENABLED&a (every &e{interval}&a seconds).";
        public String statusDisabled = "&cAuto-purge is &4DISABLED&c.";
        public String manualClear = "&aManual purge complete: &e{items} &aitems, &e{hostiles} &ahostiles, &e{passives} &aexcess passives removed.";
        public String nothingToClear = "&7Nothing to purge.";
        public String noPermission = "&cYou don't have permission to do that.";
    }
}
