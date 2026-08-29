package dev.mcplugins.skillforge;

public final class Tier {

    public final String id;
    public final String name;
    public final String shortName;
    public final int xp;

    public Tier(String id, String name, String shortName, int xp) {
        this.id = id;
        this.name = name;
        this.shortName = shortName;
        this.xp = xp;
    }
}
