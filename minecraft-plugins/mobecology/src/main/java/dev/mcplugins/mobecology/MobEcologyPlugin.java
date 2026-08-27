package dev.mcplugins.mobecology;

import org.bukkit.attribute.Attribute;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.AbstractVillager;
import org.bukkit.entity.Allay;
import org.bukkit.entity.Ambient;
import org.bukkit.entity.Animals;
import org.bukkit.entity.Ghast;
import org.bukkit.entity.Golem;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Monster;
import org.bukkit.entity.Phantom;
import org.bukkit.entity.Shulker;
import org.bukkit.entity.Slime;
import org.bukkit.entity.WaterMob;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public final class MobEcologyPlugin extends JavaPlugin {

    public enum Category {
        PASSIVE, HOSTILE, WATER, AMBIENT, IGNORED;

        public String label() {
            return switch (this) {
                case PASSIVE -> "Passive";
                case HOSTILE -> "Hostile";
                case WATER -> "Water";
                case AMBIENT -> "Ambient";
                case IGNORED -> "Ignored";
            };
        }
    }

    public static final class Settings {
        public int regionChunks = 8;
        public Set<String> disabledWorlds = Set.of();
        public double capPassive = 24;
        public double capHostile = 16;
        public double capWater = 20;
        public double capAmbient = 8;
        public double overFactor = 1.5;
        public double underFraction = 0.3;
        public EnumSet<CreatureSpawnEvent.SpawnReason> gatedReasons =
                EnumSet.of(CreatureSpawnEvent.SpawnReason.NATURAL, CreatureSpawnEvent.SpawnReason.REINFORCEMENTS);
        public int censusIntervalSeconds = 60;
        public int regionsPerTick = 4;
        public boolean boostEnabled = true;
        public int boostIntervalSeconds = 90;
        public int boostPerRun = 6;
        public int boostRadius = 48;
        public Map<String, java.util.List<String>> boostDefaults = new HashMap<>();
        public java.util.List<String> daySafeHostiles =
                java.util.List.of("creeper", "spider", "cave_spider", "slime", "husk");
        public Map<String, java.util.List<String>> foodWeb = new HashMap<>();
        public boolean adaptEnabled = true;
        public double killWeight = 1.0;
        public int[] tierThresholds = {40, 120, 300};
        public double decayPerHour = 0.02;
        public boolean variedTraits = true;
        public Map<String, Double> capacityOverrides = new HashMap<>();

        public double capacity(Category c) {
            return switch (c) {
                case PASSIVE -> capPassive;
                case HOSTILE -> capHostile;
                case WATER -> capWater;
                case AMBIENT -> capAmbient;
                default -> 0;
            };
        }
    }

    private volatile Settings settings = new Settings();
    private final Map<String, String> speciesCategories = new ConcurrentHashMap<>();
    private PopulationTracker tracker;
    private BalanceEngine engine;
    private AdaptationManager adaptation;
    private EcologyStore store;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        settings = readSettings();
        store = new EcologyStore(this);

        Attribute hpAttr = Compat.attribute("max_health", "generic.max_health");
        Attribute speedAttr = Compat.attribute("movement_speed", "generic.movement_speed");
        Attribute armorAttr = Compat.attribute("armor", "generic.armor");
        Attribute damageAttr = Compat.attribute("attack_damage", "generic.attack_damage");
        Attribute followAttr = Compat.attribute("follow_range", "generic.follow_range");
        Attribute kbAttr = Compat.attribute("knockback_resistance", "generic.knockback_resistance");
        Attribute toughAttr = Compat.attribute("armor_toughness", "generic.armor_toughness");
        int missing = 0;
        for (Attribute a : new Attribute[]{hpAttr, speedAttr, armorAttr, damageAttr, followAttr,
                kbAttr, toughAttr}) {
            if (a == null) {
                missing++;
            }
        }
        if (missing > 0) {
            getLogger().warning(missing + " attribute(s) unresolved on this server version; related traits disabled.");
        }

        adaptation = new AdaptationManager(this, hpAttr, speedAttr, armorAttr, damageAttr,
                followAttr, kbAttr, toughAttr);
        engine = new BalanceEngine(this);
        tracker = new PopulationTracker(this, engine, adaptation);

        for (Map.Entry<RegionKey, EcologyRegion> e : store.load().entrySet()) {
            tracker.regions().put(e.getKey(), e.getValue());
        }
        tracker.seedLoadedChunks();

        getServer().getPluginManager().registerEvents(tracker, this);
        tracker.startTasks();
        engine.startBoostTask();
        long autosaveTicks = 6000L;
        getServer().getScheduler().runTaskTimer(this, () -> store.saveAsync(tracker.regions()),
                autosaveTicks, autosaveTicks);

        EcologyCommand executor = new EcologyCommand(this);
        PluginCommand cmd = getCommand("ecology");
        if (cmd != null) {
            cmd.setExecutor(executor);
            cmd.setTabCompleter(executor);
        }
        PluginCommand me = getCommand("me");
        if (me != null) {
            me.setExecutor(executor);
            me.setTabCompleter(executor);
        }

        getLogger().info(() -> "MobEcology enabled: region=" + settings.regionChunks + "x"
                + settings.regionChunks + " chunks, adaptations="
                + (settings.adaptEnabled ? "on" : "off") + ", boosts="
                + (settings.boostEnabled ? "on" : "off"));
    }

    @Override
    public void onDisable() {
        if (engine != null) {
            engine.stopTasks();
        }
        if (store != null && tracker != null) {
            store.saveSync(tracker.regions());
        }
    }

    public Settings settings() {
        return settings;
    }

    public void reloadSettings() {
        reloadConfig();
        settings = readSettings();
    }

    public PopulationTracker tracker() {
        return tracker;
    }

    public BalanceEngine engine() {
        return engine;
    }

    public AdaptationManager adaptation() {
        return adaptation;
    }

    public Map<String, String> speciesCategories() {
        return speciesCategories;
    }

    public String typeId(LivingEntity le) {
        return le.getType().getName();
    }

    public boolean disabled(String worldName) {
        return settings.disabledWorlds.contains(worldName);
    }

    public Category classify(LivingEntity le) {
        String id = typeId(le);
        String cached = speciesCategories.get(id);
        if (cached != null) {
            return Category.valueOf(cached);
        }
        Category c = computeCategory(le);
        speciesCategories.put(id, c.name());
        return c;
    }

    private Category computeCategory(LivingEntity le) {
        if (le instanceof Monster || le instanceof Slime || le instanceof Ghast
                || le instanceof Phantom || le instanceof Shulker) {
            return Category.HOSTILE;
        }
        if (le instanceof WaterMob) {
            return Category.WATER;
        }
        if (le instanceof Ambient) {
            return Category.AMBIENT;
        }
        if (le instanceof Animals || le instanceof AbstractVillager || le instanceof Golem
                || le instanceof Allay) {
            return Category.PASSIVE;
        }
        return Category.IGNORED;
    }

    private Settings readSettings() {
        var c = getConfig();
        Settings s = new Settings();        s.regionChunks = Math.max(2, c.getInt("grid.region-chunks", 8));
        s.disabledWorlds = new HashSet<>(c.getStringList("worlds.disabled"));
        s.capPassive = c.getDouble("capacity.passive", 24);
        s.capHostile = c.getDouble("capacity.hostile", 16);
        s.capWater = c.getDouble("capacity.water", 20);
        s.capAmbient = c.getDouble("capacity.ambient", 8);
        s.overFactor = Math.max(1.0, c.getDouble("capacity.over-spawn-factor", 1.5));
        s.underFraction = Math.min(1.0, Math.max(0.05, c.getDouble("capacity.under-fraction", 0.3)));
        s.gatedReasons = EnumSet.noneOf(CreatureSpawnEvent.SpawnReason.class);
        for (String r : c.getStringList("gating.reasons")) {
            try {
                s.gatedReasons.add(CreatureSpawnEvent.SpawnReason.valueOf(r.toUpperCase(Locale.ROOT)));
            } catch (IllegalArgumentException ignored) {
            }
        }
        if (s.gatedReasons.isEmpty()) {
            s.gatedReasons.add(CreatureSpawnEvent.SpawnReason.NATURAL);
        }
        s.censusIntervalSeconds = Math.max(10, c.getInt("census.interval-seconds", 60));
        s.regionsPerTick = Math.max(1, c.getInt("census.regions-per-tick", 4));
        s.boostEnabled = c.getBoolean("boost.enabled", true);
        s.boostIntervalSeconds = Math.max(15, c.getInt("boost.interval-seconds", 90));
        s.boostPerRun = Math.max(1, c.getInt("boost.max-per-run", 6));
        s.boostRadius = Math.max(16, c.getInt("boost.radius", 48));
        Map<String, java.util.List<String>> defaults = new HashMap<>();
        ConfigurationSection bs = c.getConfigurationSection("boost.defaults");
        if (bs != null) {
            for (String k : bs.getKeys(false)) {
                defaults.put(k.toLowerCase(Locale.ROOT), bs.getStringList(k));
            }
        }
        s.boostDefaults = defaults;
        java.util.List<String> safe = c.getStringList("boost.day-safe-hostiles");
        s.daySafeHostiles = safe.isEmpty()
                ? s.daySafeHostiles
                : safe.stream().map(x -> x.toLowerCase(Locale.ROOT)).collect(java.util.stream.Collectors.toList());
        Map<String, java.util.List<String>> web = new HashMap<>();
        ConfigurationSection fs = c.getConfigurationSection("food-web");
        if (fs != null) {
            for (String k : fs.getKeys(false)) {
                web.put(k.toLowerCase(Locale.ROOT), fs.getStringList(k));
            }
        }
        s.foodWeb = web;
        s.adaptEnabled = c.getBoolean("adaptation.enabled", true);
        s.killWeight = Math.max(0, c.getDouble("adaptation.kill-weight", 1.0));
        java.util.List<Integer> thresholds = c.getIntegerList("adaptation.tier-thresholds");
        if (thresholds.size() >= 3) {
            s.tierThresholds = new int[]{thresholds.get(0), thresholds.get(1), thresholds.get(2)};
        }
        s.decayPerHour = Math.min(0.9, Math.max(0, c.getDouble("adaptation.decay-per-hour", 0.02)));
        s.variedTraits = c.getBoolean("adaptation.varied-traits", true);
        Map<String, Double> overrides = new HashMap<>();
        ConfigurationSection os = c.getConfigurationSection("capacity-overrides");
        if (os != null) {
            for (String k : os.getKeys(false)) {
                double v = os.getDouble(k, -1);
                if (v > 0) {
                    overrides.put(k.toLowerCase(Locale.ROOT), v);
                }
            }
        }
        s.capacityOverrides = overrides;
        return s;
    }
}
