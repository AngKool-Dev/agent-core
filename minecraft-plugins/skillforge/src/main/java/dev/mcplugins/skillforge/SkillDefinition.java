package dev.mcplugins.skillforge;

public final class SkillDefinition {

    public final String id;
    public final String name;
    public final String description;
    public final boolean signature;

    public SkillDefinition(String id, String name, String description, boolean signature) {
        this.id = id;
        this.name = name;
        this.description = description;
        this.signature = signature;
    }
}
