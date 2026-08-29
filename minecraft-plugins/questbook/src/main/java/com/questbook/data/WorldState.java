package com.questbook.data;

import com.questbook.QuestBookPlugin;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.File;
import java.io.IOException;

public class WorldState {
    private final QuestBookPlugin plugin;
    private final File file;
    private boolean enderDragonKilled;

    public WorldState(QuestBookPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), "worldstate.yml");
        load();
    }

    public void load() {
        if (!file.exists()) {
            save();
            return;
        }
        YamlConfiguration config = YamlConfiguration.loadConfiguration(file);
        enderDragonKilled = config.getBoolean("ender_dragon_killed", false);
    }

    public void save() {
        YamlConfiguration config = new YamlConfiguration();
        config.set("ender_dragon_killed", enderDragonKilled);
        try {
            config.save(file);
        } catch (IOException e) {
            plugin.getLogger().severe("Failed to save world state!");
        }
    }

    public boolean isEnderDragonKilled() {
        return enderDragonKilled;
    }

    public void setEnderDragonKilled(boolean value) {
        this.enderDragonKilled = value;
        save();
    }
}
