package com.questbook.gui;

import com.questbook.quest.Quest;
import com.questbook.quest.QuestObjective;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.List;

public class QuestItemBuilder {

    public static ItemStack buildActiveQuestItem(Quest quest, List<Integer> progress) {
        ItemStack item = new ItemStack(Material.ENCHANTED_BOOK);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) return item;

        meta.setDisplayName(ChatColor.GOLD + quest.getTitle());

        List<String> lore = new ArrayList<>();
        lore.add(ChatColor.GRAY + quest.getDescription());
        lore.add("");
        lore.add(ChatColor.YELLOW + "Type: " + ChatColor.WHITE + quest.getType());
        lore.add(ChatColor.YELLOW + "Progress: " + ChatColor.WHITE + String.format("%.0f%%", progressPercent(quest.getObjectives(), progress)));
        lore.add("");
        lore.add(ChatColor.YELLOW + "Objectives:");

        List<QuestObjective> objectives = quest.getObjectives();
        for (int i = 0; i < objectives.size(); i++) {
            QuestObjective obj = objectives.get(i);
            int completed = i < progress.size() ? progress.get(i) : 0;
            boolean done = obj.isComplete() || completed >= obj.getAmountRequired();
            ChatColor status = done ? ChatColor.GREEN : ChatColor.RED;
            lore.add(status + "- " + obj.getDescription() + " " +
                ChatColor.WHITE + "(" + completed + "/" + obj.getAmountRequired() + ")");
        }

        lore.add("");
        lore.add(ChatColor.GREEN + "Click to view details");
        lore.add(ChatColor.DARK_GRAY + "[quest_id:" + quest.getId() + "]");

        meta.setLore(lore);
        meta.addItemFlags(ItemFlag.HIDE_ENCHANTS);
        item.setItemMeta(meta);
        return item;
    }

    public static ItemStack buildAvailableQuestItem(Quest quest) {
        ItemStack item = new ItemStack(Material.BOOK);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) return item;

        meta.setDisplayName(ChatColor.AQUA + quest.getTitle());

        List<String> lore = new ArrayList<>();
        lore.add(ChatColor.GRAY + quest.getDescription());
        lore.add("");
        lore.add(ChatColor.YELLOW + "Type: " + ChatColor.WHITE + quest.getType());
        lore.add(ChatColor.YELLOW + "Required Level: " + ChatColor.WHITE + quest.getRequiredLevel());
        lore.add("");
        lore.add(ChatColor.YELLOW + "Objectives:");

        for (QuestObjective obj : quest.getObjectives()) {
            lore.add(ChatColor.DARK_GRAY + "- " + obj.getDescription() + " " +
                ChatColor.WHITE + "(0/" + obj.getAmountRequired() + ")");
        }

        lore.add("");
        lore.add(ChatColor.YELLOW + "Rewards:");
        lore.add(ChatColor.GREEN + "- Experience: " + quest.getRewards().getExperience());
        lore.add(ChatColor.GREEN + "- Money: " + (long) (quest.getRewards().getMoney() * quest.getDifficulty().getMoneyMultiplier()) + " (" + quest.getDifficulty().getDisplayName() + " x" + (int) quest.getDifficulty().getMoneyMultiplier() + ")");
        if (!quest.getRewards().getItems().isEmpty()) {
            quest.getRewards().getItems().forEach((itemName, amount) ->
                lore.add(ChatColor.GREEN + "- " + itemName + " x" + amount));
        }
        if (!quest.getRewards().getRareRewards().isEmpty()) {
            lore.add(ChatColor.LIGHT_PURPLE + "- Rare drops:");
            for (com.questbook.quest.RareReward rare : quest.getRewards().getRareRewards()) {
                lore.add(ChatColor.LIGHT_PURPLE + "  * " + rare.getMaterial().name().toLowerCase() + " x" + rare.getAmount() + " (" + (int) rare.getChance() + "% chance)");
            }
        }

        lore.add("");
        lore.add(ChatColor.GREEN + "Click to accept");
        lore.add(ChatColor.DARK_GRAY + "[quest_id:" + quest.getId() + "]");

        meta.setLore(lore);
        item.setItemMeta(meta);
        return item;
    }

    public static ItemStack buildCompletedQuestItem(Quest quest) {
        ItemStack item = new ItemStack(Material.ENCHANTED_BOOK);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) return item;

        meta.setDisplayName(ChatColor.GREEN + quest.getTitle());

        List<String> lore = new ArrayList<>();
        lore.add(ChatColor.GRAY + quest.getDescription());
        lore.add("");
        lore.add(ChatColor.YELLOW + "Type: " + ChatColor.WHITE + quest.getType());
        lore.add(ChatColor.GREEN + "Status: Completed");
        lore.add("");
        lore.add(ChatColor.YELLOW + "Objectives:");

        for (QuestObjective obj : quest.getObjectives()) {
            lore.add(ChatColor.GREEN + "- " + obj.getDescription() + " " +
                ChatColor.WHITE + "(" + obj.getAmountRequired() + "/" + obj.getAmountRequired() + ")");
        }

        lore.add("");
        lore.add(ChatColor.DARK_GRAY + "[quest_id:" + quest.getId() + "]");

        meta.setLore(lore);
        meta.addItemFlags(ItemFlag.HIDE_ENCHANTS);
        item.setItemMeta(meta);
        return item;
    }

    public static double progressPercent(List<QuestObjective> objectives, List<Integer> progress) {
        int total = 0, completed = 0;
        for (int i = 0; i < objectives.size(); i++) {
            QuestObjective obj = objectives.get(i);
            total += obj.getAmountRequired();
            completed += Math.min(i < progress.size() ? progress.get(i) : 0, obj.getAmountRequired());
        }
        return total > 0 ? (double) completed / total * 100 : 0;
    }

    public static String extractQuestId(ItemStack item) {
        if (item == null || !item.hasItemMeta()) return null;
        ItemMeta meta = item.getItemMeta();
        if (meta == null || !meta.hasLore()) return null;

        for (String line : meta.getLore()) {
            if (line.contains("[quest_id:")) {
                int start = line.indexOf("[quest_id:") + 10;
                int end = line.indexOf("]", start);
                if (end > start) {
                    return line.substring(start, end).trim();
                }
            }
        }
        return null;
    }

    public static ItemStack buildLockedQuestItem(Quest quest, String requiredQuestTitle) {
        ItemStack item = new ItemStack(Material.GRAY_DYE);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) return item;

        meta.setDisplayName(ChatColor.DARK_GRAY + "" + ChatColor.STRIKETHROUGH + quest.getTitle());

        List<String> lore = new ArrayList<>();
        lore.add(ChatColor.GRAY + quest.getDescription());
        lore.add("");
        lore.add(ChatColor.RED + "Locked");
        lore.add(ChatColor.GRAY + "Complete \"" + requiredQuestTitle + "\" to unlock");
        lore.add(ChatColor.DARK_GRAY + "[quest_id:" + quest.getId() + "]");

        meta.setLore(lore);
        item.setItemMeta(meta);
        return item;
    }

    public static ItemStack buildBackButton() {
        ItemStack item = new ItemStack(Material.ARROW);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.YELLOW + "Back");
            meta.setLore(List.of(ChatColor.GRAY + "Return to quest list"));
            item.setItemMeta(meta);
        }
        return item;
    }

    public static ItemStack buildPrevButton() {
        ItemStack item = new ItemStack(Material.ARROW);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.YELLOW + "Previous Page");
            item.setItemMeta(meta);
        }
        return item;
    }

    public static ItemStack buildNextButton() {
        ItemStack item = new ItemStack(Material.ARROW);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.YELLOW + "Next Page");
            item.setItemMeta(meta);
        }
        return item;
    }

    public static ItemStack createQuestBackground() {
        ItemStack item = new ItemStack(Material.BLACK_STAINED_GLASS_PANE);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.DARK_GRAY + " ");
            item.setItemMeta(meta);
        }
        return item;
    }

    public static ItemStack buildQuestBackground() {
        return createQuestBackground();
    }

    public static ItemStack buildQuestDetail(Quest quest, List<Integer> progress) {
        ItemStack item = new ItemStack(Material.BOOK);
        ItemMeta meta = item.getItemMeta();
        if (meta == null) return item;

        meta.setDisplayName(ChatColor.GOLD + quest.getTitle());

        List<String> lore = new ArrayList<>();
        lore.add(ChatColor.GRAY + quest.getDescription());
        lore.add("");
        lore.add(ChatColor.YELLOW + "Type: " + ChatColor.WHITE + quest.getType());
        lore.add(ChatColor.YELLOW + "Required Level: " + ChatColor.WHITE + quest.getRequiredLevel());
        lore.add(ChatColor.YELLOW + "Repeatable: " + ChatColor.WHITE + quest.isRepeatable());
        lore.add("");
        lore.add(ChatColor.YELLOW + "Objectives:");

        List<QuestObjective> objectives = quest.getObjectives();
        for (int i = 0; i < objectives.size(); i++) {
            QuestObjective obj = objectives.get(i);
            int completed = i < progress.size() ? progress.get(i) : 0;
            boolean done = obj.isComplete() || completed >= obj.getAmountRequired();
            ChatColor status = done ? ChatColor.GREEN : ChatColor.RED;
            lore.add(status + "- " + obj.getDescription() + " " +
                ChatColor.WHITE + "(" + completed + "/" + obj.getAmountRequired() + ")");
        }

        lore.add("");
        lore.add(ChatColor.YELLOW + "Rewards:");
        lore.add(ChatColor.GREEN + "- Experience: " + quest.getRewards().getExperience());
        lore.add(ChatColor.GREEN + "- Money: " + (long) (quest.getRewards().getMoney() * quest.getDifficulty().getMoneyMultiplier()) + " (" + quest.getDifficulty().getDisplayName() + " x" + (int) quest.getDifficulty().getMoneyMultiplier() + ")");
        if (!quest.getRewards().getItems().isEmpty()) {
            quest.getRewards().getItems().forEach((itemName, amount) ->
                lore.add(ChatColor.GREEN + "- " + itemName + " x" + amount));
        }
        if (!quest.getRewards().getRareRewards().isEmpty()) {
            lore.add(ChatColor.LIGHT_PURPLE + "- Rare drops:");
            for (com.questbook.quest.RareReward rare : quest.getRewards().getRareRewards()) {
                lore.add(ChatColor.LIGHT_PURPLE + "  * " + rare.getMaterial().name().toLowerCase() + " x" + rare.getAmount() + " (" + (int) rare.getChance() + "% chance)");
            }
        }

        lore.add("");
        lore.add(ChatColor.GREEN + "Click to accept this quest");
        lore.add(ChatColor.DARK_GRAY + "[quest_id:" + quest.getId() + "]");

        meta.setLore(lore);
        item.setItemMeta(meta);
        return item;
    }
}
