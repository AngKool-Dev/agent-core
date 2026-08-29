package com.questbook.event;

import com.questbook.QuestBookPlugin;
import com.questbook.data.PlayerData;
import com.questbook.gui.QuestBookGUI;
import com.questbook.gui.QuestItemBuilder;
import com.questbook.quest.Quest;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.ItemStack;

public class QuestBookClickListener implements Listener {
    private final QuestBookPlugin plugin;

    public QuestBookClickListener(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onInventoryClick(InventoryClickEvent event) {
        if (!(event.getWhoClicked() instanceof Player player)) return;

        String title = event.getView().getTitle();
        String questBookTitle = ChatColor.GOLD + "Quest Book";
        String questSectionPrefix = ChatColor.GOLD + "Quest Book: ";
        String questDetailPrefix = ChatColor.GOLD + "Quest: ";

        if (!title.equals(questBookTitle) && !title.startsWith(questSectionPrefix) && !title.startsWith(questDetailPrefix)) {
            return;
        }

        event.setCancelled(true);

        ItemStack clicked = event.getCurrentItem();
        if (clicked == null || clicked.getType() == Material.AIR) return;

        // Pagination navigation
        if (clicked.getType() == Material.ARROW) {
            String name = clicked.hasItemMeta() && clicked.getItemMeta() != null ? clicked.getItemMeta().getDisplayName() : "";
            if (name.equals(ChatColor.YELLOW + "Previous Page") || name.equals(ChatColor.YELLOW + "Next Page")) {
                int cur = parsePage(title);
                int next = name.equals(ChatColor.YELLOW + "Next Page") ? cur + 1 : cur - 1;
                if (title.startsWith(questSectionPrefix)) {
                    String sectionName = title.substring(questSectionPrefix.length()).split(" §7p")[0];
                    QuestBookGUI.QuestSection section = switch (sectionName) {
                        case "Active" -> QuestBookGUI.QuestSection.ACTIVE;
                        case "Available" -> QuestBookGUI.QuestSection.AVAILABLE;
                        case "Completed" -> QuestBookGUI.QuestSection.COMPLETED;
                        default -> null;
                    };
                    if (section != null) new QuestBookGUI(plugin).openQuestList(player, section, next);
                }
            }
            return;
        }

        if (title.equals(questBookTitle)) {
            handleQuestBookClick(player, clicked);
        } else if (title.startsWith(questSectionPrefix)) {
            handleQuestListClick(player, clicked);
        } else if (title.startsWith(questDetailPrefix)) {
            handleQuestDetailClick(player, event.getRawSlot(), clicked);
        }
    }

    private int parsePage(String title) {
        int idx = title.lastIndexOf("§7p");
        if (idx >= 0) {
            String part = title.substring(idx + 3);
            int slash = part.indexOf('/');
            try {
                return Integer.parseInt(part.substring(0, slash).trim()) - 1;
            } catch (Exception ignored) {}
        }
        return 0;
    }

    private void handleQuestBookClick(Player player, ItemStack clicked) {
        Material type = clicked.getType();

        QuestBookGUI.QuestSection section = switch (type) {
            case COMPASS -> QuestBookGUI.QuestSection.ACTIVE;
            case BOOK -> QuestBookGUI.QuestSection.AVAILABLE;
            case ENCHANTED_BOOK -> QuestBookGUI.QuestSection.COMPLETED;
            default -> null;
        };

        if (section != null) {
            new QuestBookGUI(plugin).openQuestList(player, section);
        }
    }

    private void handleQuestListClick(Player player, ItemStack clicked) {
        if (clicked.getType() == Material.ARROW) {
            new QuestBookGUI(plugin).openQuestBook(player);
            return;
        }

        String questId = QuestItemBuilder.extractQuestId(clicked);
        if (questId != null) {
            Quest quest = plugin.getQuestManager().getQuest(questId);
            if (quest != null) {
                PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());
                new QuestBookGUI(plugin).openQuestDetail(player, quest, data.getObjectiveProgress(questId));
            }
        }
    }

    private void handleQuestDetailClick(Player player, int slot, ItemStack clicked) {
        Material type = clicked.getType();

        if (type == Material.ARROW) {
            new QuestBookGUI(plugin).openQuestBook(player);
            return;
        }

        if (type == Material.EMERALD) {
            String questId = QuestItemBuilder.extractQuestId(clicked);
            if (questId != null) {
                Quest quest = plugin.getQuestManager().getQuest(questId);
                if (quest != null) {
                    acceptQuest(player, questId, quest);
                }
            }
            return;
        }

        if (type == Material.REDSTONE) {
            String questId = QuestItemBuilder.extractQuestId(clicked);
            if (questId != null) {
                Quest quest = plugin.getQuestManager().getQuest(questId);
                if (quest != null) {
                    abandonQuest(player, questId, quest);
                }
            }
            return;
        }
    }

    private void acceptQuest(Player player, String questId, Quest quest) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        String required = quest.getRequiredQuestId();
        if (required != null && !data.getCompletedQuests().containsKey(required)) {
            Quest requiredQuest = plugin.getQuestManager().getQuest(required);
            player.sendMessage(ChatColor.RED + "This quest is locked! Complete \"" +
                (requiredQuest != null ? requiredQuest.getTitle() : required) + "\" first.");
            player.closeInventory();
            return;
        }

        String error = plugin.getQuestManager().canAcceptQuest(data, quest);
        if (error != null) {
            player.sendMessage(ChatColor.RED + error);
            player.closeInventory();
            return;
        }

        data.setActiveQuest(quest);
        player.sendMessage(ChatColor.GREEN + "Quest accepted: " + quest.getTitle());
        player.closeInventory();
    }

    private void abandonQuest(Player player, String questId, Quest quest) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        if (!data.isActive(questId)) {
            return;
        }

        data.getActiveQuestProgress().remove(questId);
        player.sendMessage(ChatColor.YELLOW + "Quest abandoned: " + quest.getTitle());
        player.closeInventory();
    }
}