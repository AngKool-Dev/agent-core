package com.questbook.gui;

import com.questbook.QuestBookPlugin;
import com.questbook.data.PlayerData;
import com.questbook.quest.Quest;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.List;

public class QuestBookGUI {
    private final QuestBookPlugin plugin;

    public QuestBookGUI(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }

    public void openQuestBook(Player player) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        Inventory inventory = Bukkit.createInventory(null, 27, ChatColor.GOLD + "Quest Book");

        int active = data.getActiveQuestProgress().size();
        int available = 0;
        for (Quest quest : plugin.getQuestManager().getAvailableQuests(data.getLevel())) {
            if (plugin.getQuestManager().isQuestVisible(data, quest)
                && !data.isActive(quest.getId()) && !data.getCompletedQuests().containsKey(quest.getId())) {
                available++;
            }
        }
        int completed = data.getCompletedQuests().size();

        inventory.setItem(11, createSectionButton(Material.COMPASS, ChatColor.GOLD + "Active Quests", active + " quest(s) in progress"));
        inventory.setItem(13, createSectionButton(Material.BOOK, ChatColor.YELLOW + "Available Quests", available + " quest(s) available"));
        inventory.setItem(15, createSectionButton(Material.ENCHANTED_BOOK, ChatColor.GREEN + "Completed Quests", completed + " quest(s) completed"));

        setFillers(inventory);

        player.openInventory(inventory);
    }

    public void openQuestList(Player player, QuestSection section) {
        openQuestList(player, section, 0);
    }

    public void openQuestList(Player player, QuestSection section, int page) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        String baseTitle = ChatColor.GOLD + "Quest Book: " + section.getDisplayName();
        int perPage = 45;
        int pages = 1;

        // Build the full ordered list for this section once.
        List<Quest> list = new ArrayList<>();
        switch (section) {
            case ACTIVE -> {
                for (String questId : data.getActiveQuestProgress().keySet()) {
                    Quest quest = plugin.getQuestManager().getQuest(questId);
                    if (quest != null) list.add(quest);
                }
            }
            case AVAILABLE -> {
                List<Quest> unlocked = new ArrayList<>();
                List<Quest> locked = new ArrayList<>();
                for (Quest quest : plugin.getQuestManager().getAvailableQuests(data.getLevel())) {
                    if (!plugin.getQuestManager().isQuestVisible(data, quest)
                        || data.isActive(quest.getId())
                        || (!quest.isRepeatable() && data.getCompletedQuests().containsKey(quest.getId()))) {
                        continue;
                    }
                    String required = quest.getRequiredQuestId();
                    if (required != null && !data.getCompletedQuests().containsKey(required)) {
                        locked.add(quest);
                    } else {
                        unlocked.add(quest);
                    }
                }
                list.addAll(unlocked);
                list.addAll(locked);
            }
            case COMPLETED -> {
                for (String questId : data.getCompletedQuests().keySet()) {
                    Quest quest = plugin.getQuestManager().getQuest(questId);
                    if (quest != null) list.add(quest);
                }
            }
        }

        pages = Math.max(1, (list.size() + perPage - 1) / perPage);
        page = Math.min(Math.max(page, 0), pages - 1);

        String title = baseTitle + ChatColor.GRAY + " p" + (page + 1) + "/" + pages;
        Inventory inventory = Bukkit.createInventory(null, 54, title);

        int start = page * perPage;
        int end = Math.min(start + perPage, list.size());
        int slot = 0;
        for (int i = start; i < end; i++) {
            Quest quest = list.get(i);
            String questId = quest.getId();
            if (section == QuestSection.ACTIVE) {
                inventory.setItem(slot, QuestItemBuilder.buildActiveQuestItem(quest, data.getObjectiveProgress(questId)));
            } else if (section == QuestSection.COMPLETED) {
                inventory.setItem(slot, QuestItemBuilder.buildCompletedQuestItem(quest));
            } else {
                String required = quest.getRequiredQuestId();
                if (required != null && !data.getCompletedQuests().containsKey(required)) {
                    Quest requiredQuest = plugin.getQuestManager().getQuest(required);
                    inventory.setItem(slot, QuestItemBuilder.buildLockedQuestItem(quest, requiredQuest != null ? requiredQuest.getTitle() : required));
                } else {
                    inventory.setItem(slot, QuestItemBuilder.buildAvailableQuestItem(quest));
                }
            }
            slot++;
        }

        if (list.isEmpty()) {
            String msg = switch (section) {
                case ACTIVE -> "No active quests";
                case AVAILABLE -> "No available quests";
                case COMPLETED -> "No completed quests yet";
            };
            inventory.setItem(22, createEmptyNotice(msg));
        }

        // Navigation + back (bottom row)
        if (page > 0) inventory.setItem(45, QuestItemBuilder.buildPrevButton());
        if (page < pages - 1) inventory.setItem(53, QuestItemBuilder.buildNextButton());
        inventory.setItem(49, QuestItemBuilder.buildBackButton());

        for (int i = 45; i < 54; i++) {
            if (inventory.getItem(i) == null) inventory.setItem(i, QuestItemBuilder.buildQuestBackground());
        }

        player.openInventory(inventory);
    }

    private ItemStack createSectionButton(Material material, String name, String lore) {
        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(name);
            meta.setLore(List.of(ChatColor.GRAY + lore));
            item.setItemMeta(meta);
        }
        return item;
    }

    private ItemStack createEmptyNotice(String message) {
        ItemStack item = new ItemStack(Material.BARRIER);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.RED + message);
            item.setItemMeta(meta);
        }
        return item;
    }

    private void setFillers(Inventory inventory) {
        for (int i = 0; i < inventory.getSize(); i++) {
            if (inventory.getItem(i) == null) {
                inventory.setItem(i, QuestItemBuilder.createQuestBackground());
            }
        }
    }

    public enum QuestSection {
        ACTIVE("Active"),
        AVAILABLE("Available"),
        COMPLETED("Completed");

        private final String displayName;

        QuestSection(String displayName) {
            this.displayName = displayName;
        }

        public String getDisplayName() {
            return displayName;
        }
    }

    public void openQuestDetail(Player player, Quest quest, List<Integer> progress) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        Inventory inventory = Bukkit.createInventory(null, 27, ChatColor.GOLD + "Quest: " + quest.getTitle());

        // Quest info item
        inventory.setItem(4, QuestItemBuilder.buildQuestDetail(quest, progress));

        // Accept button (only if not active or completed)
        if (!data.isActive(quest.getId()) && !data.getCompletedQuests().containsKey(quest.getId())) {
            String error = plugin.getQuestManager().canAcceptQuest(data, quest);
            if (error == null || !error.contains("have already") ) {
                String required = quest.getRequiredQuestId();
                boolean locked = required != null && !data.getCompletedQuests().containsKey(required);
                if (!locked) {
                    inventory.setItem(12, createActionButton(quest, data.getLevel()));
                } else {
                    Quest requiredQuest = plugin.getQuestManager().getQuest(required);
                    inventory.setItem(12, createLockedButton(requiredQuest != null ? requiredQuest.getTitle() : required));
                }
            }
        }

        // Abandon button (only if active)
if (data.isActive(quest.getId())) {
                inventory.setItem(14, createAbandonButton(quest.getId()));
            }

        // Back button
        inventory.setItem(22, QuestItemBuilder.buildBackButton());

        player.openInventory(inventory);
    }

    private ItemStack createActionButton(Quest quest, int playerLevel) {
        ItemStack item;
        ItemMeta meta;
        if (quest.getRequiredLevel() <= playerLevel) {
            item = new ItemStack(Material.EMERALD);
            meta = item.getItemMeta();
            if (meta != null) {
                meta.setDisplayName(ChatColor.GREEN + "Accept Quest");
                meta.setLore(List.of(
                    ChatColor.GRAY + "Click to accept " + quest.getTitle(),
                    ChatColor.GRAY + "[quest_id:" + quest.getId() + "]"
                ));
                item.setItemMeta(meta);
            }
        } else {
            item = new ItemStack(Material.BARRIER);
            meta = item.getItemMeta();
            if (meta != null) {
                meta.setDisplayName(ChatColor.RED + "Cannot Accept");
                meta.setLore(List.of(
                    ChatColor.RED + "Requires level " + quest.getRequiredLevel(),
                    ChatColor.GRAY + "[quest_id:" + quest.getId() + "]"
                ));
                item.setItemMeta(meta);
            }
        }
        return item;
    }

    private ItemStack createLockedButton(String requiredQuestTitle) {
        ItemStack item = new ItemStack(Material.BARRIER);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.RED + "Locked");
            meta.setLore(List.of(
                ChatColor.GRAY + "Complete \"" + requiredQuestTitle + "\" first"
            ));
            item.setItemMeta(meta);
        }
        return item;
    }

    private ItemStack createAbandonButton(String questId) {
        ItemStack item = new ItemStack(Material.REDSTONE);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.RED + "Abandon Quest");
            meta.setLore(List.of(
                ChatColor.GRAY + "Click to abandon",
                ChatColor.GRAY + "[quest_id:" + questId + "]"
            ));
            item.setItemMeta(meta);
        }
        return item;
    }
}
