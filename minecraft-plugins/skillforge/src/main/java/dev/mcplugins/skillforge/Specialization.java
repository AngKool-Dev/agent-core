package dev.mcplugins.skillforge;

public final class Specialization {

    public final String id;
    public final String name;
    public final String description;
    public final String color;
    public final int maxApprentices;
    public final java.util.List<String> starterSkills;

    public Specialization(String id, String name, String description, String color,
                         int maxApprentices, java.util.List<String> starterSkills) {
        this.id = id;
        this.name = name;
        this.description = description;
        this.color = color;
        this.maxApprentices = maxApprentices;
        this.starterSkills = starterSkills != null ? starterSkills :
                java.util.Collections.emptyList();
    }
}
