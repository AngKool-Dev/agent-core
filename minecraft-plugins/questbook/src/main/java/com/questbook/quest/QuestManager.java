package com.questbook.quest;

import com.questbook.QuestBookPlugin;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.File;
import java.util.*;

public class QuestManager {

    private final QuestBookPlugin plugin;
    private final Map<String, Quest> quests = new HashMap<>();
    
    public QuestManager(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }
    
    public void loadQuests() {
        File questsDir = new File(plugin.getDataFolder(), "quests");
        if (!questsDir.exists()) {
            questsDir.mkdirs();
        }
        extractBundledQuests(questsDir);
        
        File[] files = questsDir.listFiles((dir, name) -> name.endsWith(".yml"));
        if (files == null) return;
        
        for (File file : files) {
            YamlConfiguration config = YamlConfiguration.loadConfiguration(file);
            String id = config.getString("id", file.getName().replace(".yml", ""));
            
            List<QuestObjective> objectives = new ArrayList<>();
            List<?> objList = config.getList("objectives");
            if (objList != null) {
                for (Object entry : objList) {
                    if (!(entry instanceof Map<?, ?> map)) continue;
                    
                    String description = String.valueOf(map.get("description"));
                    ObjectiveType type = ObjectiveType.valueOf(String.valueOf(map.get("type")).toUpperCase());
                    String targetId = String.valueOf(map.get("target"));
                    int amount = Integer.parseInt(String.valueOf(map.get("amount")));
                    
                    objectives.add(new QuestObjective(description, type, targetId, amount));
                }
            }
            
            Map<String, Integer> rewardItems = new HashMap<>();
            ConfigurationSection itemsSection = config.getConfigurationSection("rewards.items");
            if (itemsSection != null) {
                for (String item : itemsSection.getKeys(false)) {
                    rewardItems.put(item, itemsSection.getInt(item));
                }
            }
            
            QuestRewards rewards = new QuestRewards(
                rewardItems,
                config.getInt("rewards.experience", 0),
                config.getInt("rewards.money", 0),
                parseRareRewards(config)
            );
            
            QuestDifficulty difficulty = QuestDifficulty.fromString(config.getString("difficulty", "NORMAL"));
            
            Quest quest = new Quest(
                id,
                config.getString("title", "Untitled"),
                config.getString("description", ""),
                QuestType.valueOf(config.getString("type", "COLLECTION")),
                objectives,
                rewards,
                config.getInt("required_level", 1),
                config.getBoolean("repeatable", false),
                config.getString("required_quest", null),
                config.getBoolean("requires_dragon_killed", false),
                config.getBoolean("only_when_dragon_alive", false),
                difficulty
            );
            
            quests.put(id, quest);
            plugin.getLogger().info("Loaded quest " + id + " with " + objectives.size() + " objectives (" +
                objectives.stream().map(QuestObjective::getTargetId).toList() + ")");
        }
        
        plugin.getLogger().info("Loaded " + quests.size() + " quests");
    }
    
    private void extractBundledQuests(File questsDir) {
        File jarFile = plugin.jarFile();
        if (jarFile == null || !jarFile.isFile()) {
            return;
        }
        java.util.zip.ZipFile zip = null;
        try {
            zip = new java.util.zip.ZipFile(jarFile);
            java.util.Enumeration<? extends java.util.zip.ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                java.util.zip.ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                if (entry.isDirectory() || !name.startsWith("quests/") || !name.endsWith(".yml")) {
                    continue;
                }
                File out = new File(questsDir, name.substring("quests/".length()));
                if (out.exists()) {
                    continue;
                }
                try (java.io.InputStream in = zip.getInputStream(entry);
                     java.io.OutputStream os = new java.io.FileOutputStream(out)) {
                    in.transferTo(os);
                }
            }
        } catch (java.io.IOException ex) {
            plugin.getLogger().warning("Failed to extract bundled quests: " + ex.getMessage());
        } finally {
            if (zip != null) {
                try {
                    zip.close();
                } catch (java.io.IOException ignored) {
                }
            }
        }
    }
    
    public Quest getQuest(String id) {
        return quests.get(id);
    }
    
    public String canAcceptQuest(com.questbook.data.PlayerData data, Quest quest) {
        if (data.isActive(quest.getId())) {
            return "You already have this quest active!";
        }
        if (!quest.isRepeatable() && data.getCompletedQuests().containsKey(quest.getId())) {
            return "You have already completed this quest!";
        }
        if (data.hasActiveQuest()) {
            return "You can only work on one quest at a time. Finish or abandon your current quest first!";
        }
        if (quest.getRequiredLevel() > data.getLevel()) {
            return "You need level " + quest.getRequiredLevel() + " to accept this quest. (You are level " + data.getLevel() + ")";
        }
        boolean dragonKilled = plugin.getWorldState().isEnderDragonKilled();
        if (quest.requiresDragonKilled() && !dragonKilled) {
            return "This quest is sealed. You must face the Ender Dragon first!";
        }
        if (quest.onlyWhenDragonAlive() && dragonKilled) {
            return "The great dragon has fallen. New trials await instead.";
        }
        String required = quest.getRequiredQuestId();
        if (required != null && !data.getCompletedQuests().containsKey(required)) {
            Quest requiredQuest = getQuest(required);
            String requiredTitle = requiredQuest != null ? requiredQuest.getTitle() : required;
            return "You must complete \"" + requiredTitle + "\" first before you can accept this quest!";
        }
        return null;
    }
    
    public boolean isQuestVisible(com.questbook.data.PlayerData data, Quest quest) {
        if (data.isActive(quest.getId())) return true;
        if (!quest.isRepeatable() && data.getCompletedQuests().containsKey(quest.getId())) return true;

        boolean dragonKilled = plugin.getWorldState().isEnderDragonKilled();
        if (quest.requiresDragonKilled() && !dragonKilled) return false;
        if (quest.onlyWhenDragonAlive() && dragonKilled) return false;
        return true;
    }

    public List<Quest> getAllQuests() {
        return quests.values().stream().toList();
    }
    
    public List<Quest> getAvailableQuests(int playerLevel) {
        return quests.values().stream()
            .filter(q -> q.getRequiredLevel() <= playerLevel)
            .toList();
    }
    
    private List<RareReward> parseRareRewards(YamlConfiguration config) {
        List<RareReward> rare = new ArrayList<>();
        List<?> list = config.getList("rewards.rare_items");
        if (list != null) {
            for (Object entry : list) {
                if (!(entry instanceof Map<?, ?> map)) continue;
                String materialName = String.valueOf(map.get("material")).toUpperCase();
                Object amtObj = map.get("amount");
                int amount = amtObj == null ? 1 : (amtObj instanceof Number ? ((Number) amtObj).intValue() : Integer.parseInt(String.valueOf(amtObj)));
                Object chObj = map.get("chance");
                double chance = chObj == null ? 100.0 : (chObj instanceof Number ? ((Number) chObj).doubleValue() : Double.parseDouble(String.valueOf(chObj)));
                try {
                    rare.add(new RareReward(org.bukkit.Material.valueOf(materialName), amount, chance));
                } catch (IllegalArgumentException e) {
                    plugin.getLogger().warning("Invalid rare reward material: " + materialName);
                }
            }
        }
        return rare;
    }
}
