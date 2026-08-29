package com.questbook.data;

import com.questbook.QuestBookPlugin;
import com.questbook.quest.Quest;
import com.questbook.quest.QuestManager;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.Material;
import org.bukkit.inventory.ItemStack;
import org.bukkit.scheduler.BukkitRunnable;

import java.io.File;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

public class PlayerDataManager {
    private final QuestBookPlugin plugin;
    private final Map<UUID, PlayerData> playerData = new ConcurrentHashMap<>();
    
    public PlayerDataManager(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }
    
    public void loadAllData() {
        File dataDir = new File(plugin.getDataFolder(), "playerdata");
        if (!dataDir.exists()) dataDir.mkdirs();
        
        File[] files = dataDir.listFiles((dir, name) -> name.endsWith(".yml"));
        if (files != null) {
            for (File file : files) {
                String uuidStr = file.getName().replace(".yml", "");
                UUID playerId = UUID.fromString(uuidStr);
                
                 YamlConfiguration config = YamlConfiguration.loadConfiguration(file);
                 PlayerData data = new PlayerData(playerId.toString());
                 data.setLevel(config.getInt("level", 1));
                 data.setExperience(config.getInt("experience", 0));
                 data.setRankId(config.getString("rank", null));
                 
                 List<String> completed = config.getStringList("completed_quests");
                 for (String questId : completed) {
                     data.getCompletedQuests().put(questId, true);
                 }
                 
                 ConfigurationSection activeSection = config.getConfigurationSection("active_quests");
                 if (activeSection != null) {
                     QuestManager questManager = plugin.getQuestManager();
                     for (String questId : activeSection.getKeys(false)) {
                         Quest quest = questManager.getQuest(questId);
                         if (quest == null) continue;
                         
                         List<Integer> progress = activeSection.getIntegerList(questId + ".objective_progress");
                         int[] arr = progress.stream().mapToInt(Integer::intValue).toArray();
                         data.restoreActiveQuest(quest, arr);
                     }
                 }
                 
                 playerData.put(playerId, data);
            }
        }
        
        // Auto-save every 5 minutes
        new BukkitRunnable() {
            @Override
            public void run() {
                saveAllData();
            }
        }.runTaskTimer(plugin, 6000L, 6000L);
    }
    
    public PlayerData getPlayerData(UUID playerId) {
        return playerData.computeIfAbsent(playerId, id -> new PlayerData(id.toString()));
    }
    
    public void saveData(UUID playerId) {
        PlayerData data = playerData.get(playerId);
        if (data == null) return;
        
        File dataDir = new File(plugin.getDataFolder(), "playerdata");
        if (!dataDir.exists()) dataDir.mkdirs();
        
        File file = new File(dataDir, playerId.toString() + ".yml");
        YamlConfiguration config = new YamlConfiguration();
        config.set("level", data.getLevel());
        config.set("experience", data.getExperience());
        config.set("rank", data.getRankId());

        config.set("completed_quests", new ArrayList<>(data.getCompletedQuests().keySet()));

        for (String questId : data.getActiveQuestProgress().keySet()) {
            List<Integer> progress = data.getObjectiveProgress(questId);
            config.set("active_quests." + questId + ".objective_progress", progress);
        }

        try {
            config.save(file);
        } catch (Exception e) {
            plugin.getLogger().severe("Failed to save data for " + playerId);
        }
    }
    
    public void giveRewards(org.bukkit.entity.Player player, com.questbook.quest.Quest quest) {
        com.questbook.quest.QuestRewards rewards = quest.getRewards();
        
        int experience = rewards.getExperience();
        if (experience > 0) {
            player.giveExp(experience);
        }
        
        double payout = rewards.getMoney() * quest.getDifficulty().getMoneyMultiplier();
        if (payout > 0) {
            if (plugin.getVaultEconomy().isAvailable()) {
                double deposited = plugin.getVaultEconomy().deposit(player, payout);
                if (deposited > 0) {
                    player.sendMessage(org.bukkit.ChatColor.GOLD + "$" + formatMoney(deposited) + " " + plugin.getVaultEconomy().currencyName(player) + " earned! (rewarded for " + quest.getTitle() + ")");
                }
            } else {
                player.sendMessage(org.bukkit.ChatColor.GOLD + "Received " + (int) payout + " coins!");
            }
        }
        
        java.util.Map<String, Integer> items = rewards.getItems();
        if (items != null) {
            for (java.util.Map.Entry<String, Integer> entry : items.entrySet()) {
                try {
                    org.bukkit.Material material = org.bukkit.Material.valueOf(entry.getKey());
                    int amount = Math.min(entry.getValue(), material.getMaxStackSize());
                    org.bukkit.inventory.ItemStack item = new org.bukkit.inventory.ItemStack(material, amount);
                    player.getInventory().addItem(item);
                    player.sendMessage(org.bukkit.ChatColor.GREEN + "Received " + amount + " " + material.name().toLowerCase() + "!");
                } catch (IllegalArgumentException e) {
                    plugin.getLogger().warning("Invalid reward item: " + entry.getKey());
                }
            }
        }

        // Rare item rewards
        for (com.questbook.quest.RareReward rare : rewards.getRareRewards()) {
            double roll = Math.random() * 100.0;
            if (roll <= rare.getChance()) {
                org.bukkit.inventory.ItemStack rareItem = new org.bukkit.inventory.ItemStack(rare.getMaterial(), rare.getAmount());
                player.getInventory().addItem(rareItem);
                player.sendMessage(org.bukkit.ChatColor.LIGHT_PURPLE + "RARE REWARD: " + rare.getMaterial().name().toLowerCase() + " x" + rare.getAmount() + "!");
            }
        }
    }

    private static String formatMoney(double amount) {
        if (amount >= 1000000) return String.format("%.2fM", amount / 1000000.0);
        if (amount >= 1000) return String.format("%.1fK", amount / 1000.0);
        return String.valueOf((int) amount);
    }
    
    public void saveAllData() {
        File dataDir = new File(plugin.getDataFolder(), "playerdata");
        if (!dataDir.exists()) dataDir.mkdirs();
        
        playerData.forEach((uuid, data) -> {
            File file = new File(dataDir, uuid.toString() + ".yml");
            YamlConfiguration config = new YamlConfiguration();
            config.set("level", data.getLevel());
            config.set("experience", data.getExperience());
            config.set("rank", data.getRankId());

            config.set("completed_quests", new ArrayList<>(data.getCompletedQuests().keySet()));
            
            for (String questId : data.getActiveQuestProgress().keySet()) {
                List<Integer> progress = data.getObjectiveProgress(questId);
                config.set("active_quests." + questId + ".objective_progress", progress);
            }
            
            try {
                config.save(file);
            } catch (Exception e) {
                plugin.getLogger().severe("Failed to save data for " + uuid);
            }
        });
    }
}
