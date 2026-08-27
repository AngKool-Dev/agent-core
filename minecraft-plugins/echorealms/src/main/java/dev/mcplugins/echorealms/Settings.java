package dev.mcplugins.echorealms;

public final class Settings {

    public int inactiveDays = 30;
    public int deepDays = 60;
    public int minBlocks = 250;
    public int checkIntervalSeconds = 300;
    public boolean announceManifest = true;
    public int particleIntervalSeconds = 6;
    public int minRadius = 12;
    public int maxRadius = 48;
    public int attuneXp = 40;
    public int deepXp = 120;
    public double shardChance = 0.35;
    public int shardMin = 1;
    public int shardMax = 3;
    public int cooldownDays = 7;
    public int regionChunks = 8;
    public java.util.Set<String> disabledWorlds = java.util.Set.of();
    public int autosaveSeconds = 300;
    public boolean debug = false;

    public void load(EchoRealmsPlugin plugin) {
        var c = plugin.getConfig();
        inactiveDays = Math.max(0, c.getInt("lifecycle.inactive-days", 30));
        deepDays = Math.max(inactiveDays, c.getInt("lifecycle.deep-days", 60));
        minBlocks = Math.max(1, c.getInt("lifecycle.min-blocks", 250));
        checkIntervalSeconds = Math.max(30, c.getInt("lifecycle.check-interval-seconds", 300));
        announceManifest = c.getBoolean("lifecycle.announce-manifest", true);
        particleIntervalSeconds = Math.max(2, c.getInt("ambience.particle-interval-seconds", 6));
        minRadius = Math.max(6, c.getInt("ambience.min-radius", 12));
        maxRadius = Math.max(minRadius, c.getInt("ambience.max-radius", 48));
        attuneXp = Math.max(0, c.getInt("attune.xp", 40));
        deepXp = Math.max(attuneXp, c.getInt("attune.deep-xp", 120));
        shardChance = Math.min(1.0, Math.max(0, c.getDouble("attune.shard-chance", 0.35)));
        shardMin = Math.max(1, c.getInt("attune.shard-min", 1));
        shardMax = Math.max(shardMin, c.getInt("attune.shard-max", 3));
        cooldownDays = Math.max(0, c.getInt("attune.cooldown-days", 7));
        regionChunks = Math.max(2, c.getInt("grid.region-chunks", 8));
        disabledWorlds = new java.util.HashSet<>(c.getStringList("worlds.disabled"));
        autosaveSeconds = Math.max(60, c.getInt("storage.autosave-seconds", 300));
        debug = c.getBoolean("debug", false);
    }

    public boolean disabled(String world) {
        return disabledWorlds.contains(world);
    }
}
