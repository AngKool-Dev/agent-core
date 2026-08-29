package com.questbook.command;

import com.questbook.QuestBookPlugin;
import com.questbook.data.PlayerData;
import com.questbook.gui.QuestBookGUI;
import com.questbook.quest.Quest;
import com.questbook.quest.QuestManager;
import org.bukkit.ChatColor;
import org.bukkit.OfflinePlayer;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class QuestCommand implements CommandExecutor, TabCompleter {
    private final QuestBookPlugin plugin;
    
    public QuestCommand(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }
    
    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            if (sender instanceof Player player) {
                new QuestBookGUI(plugin).openQuestBook(player);
            } else {
                sender.sendMessage(ChatColor.RED + "Usage: /quest list");
            }
            return true;
        }
        
        switch (args[0].toLowerCase()) {
            case "give":
            case "payout":
                if (!sender.hasPermission("questbook.admin")) {
                    sender.sendMessage(ChatColor.RED + "You don't have permission to use /quest " + args[0].toLowerCase() + ".");
                    return true;
                }
                if (args.length < 3) {
                    sender.sendMessage(ChatColor.RED + "Usage: /quest " + args[0].toLowerCase() + " <player> <quest>");
                    return true;
                }
                Player target = plugin.getServer().getPlayer(args[1]);
                if (target == null) {
                    sender.sendMessage(ChatColor.RED + "Player not found: " + args[1]);
                    return true;
                }
                Quest quest = plugin.getQuestManager().getQuest(args[2]);
                if (quest == null) {
                    sender.sendMessage(ChatColor.RED + "Quest not found: " + args[2]);
                    return true;
                }
                plugin.getPlayerDataManager().giveRewards(target, quest);
                sender.sendMessage(ChatColor.YELLOW + "Granted all rewards for " + quest.getTitle() + " to " + target.getName() + ".");
                target.sendMessage(ChatColor.GOLD + "You have been awarded the rewards for: " + quest.getTitle() + "!");
                break;
            case "list":
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("This command can only be used by a player!");
                    return true;
                }
                listQuests(player);
                break;
            case "info":
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("This command can only be used by a player!");
                    return true;
                }
                if (args.length > 1) {
                    showQuestInfo(player, args[1]);
                } else {
                    player.sendMessage(ChatColor.RED + "Usage: /quest info <quest_id>");
                }
                break;
            case "accept":
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("This command can only be used by a player!");
                    return true;
                }
                if (args.length > 1) {
                    acceptQuest(player, args[1]);
                } else {
                    player.sendMessage(ChatColor.RED + "Usage: /quest accept <quest_id>");
                }
                break;
            case "abandon":
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("This command can only be used by a player!");
                    return true;
                }
                if (args.length > 1) {
                    abandonQuest(player, args[1]);
                } else {
                    player.sendMessage(ChatColor.RED + "Usage: /quest abandon <quest_id>");
                }
                break;
            case "balance":
                Player balPlayer = null;
                String balName = null;
                if (args.length > 1) {
                    balPlayer = plugin.getServer().getPlayer(args[1]);
                    balName = args[1];
                } else if (sender instanceof Player p) {
                    balPlayer = p;
                    balName = p.getName();
                }
                if (balName == null) {
                    sender.sendMessage(ChatColor.RED + "Usage: /quest balance [player]");
                    break;
                }
                OfflinePlayer offline = balPlayer != null ? balPlayer : plugin.getServer().getOfflinePlayer(balName);
                double bal = plugin.getVaultEconomy().balance(offline);
                sender.sendMessage(ChatColor.GOLD + balName + "'s balance: " + formatBalance(bal) + " " + plugin.getVaultEconomy().currencyName(balPlayer != null ? balPlayer : (sender instanceof Player sp ? sp : null)));
                break;
            case "admin":
                if (!sender.hasPermission("questbook.admin")) {
                    sender.sendMessage(ChatColor.RED + "You don't have permission to use /quest admin!");
                    return true;
                }
                handleAdminCmd(sender, args.length > 1 ? Arrays.copyOfRange(args, 1, args.length) : new String[0]);
                break;
            default:
                sender.sendMessage(ChatColor.RED + "Unknown subcommand. Use /quest list, /quest info <id>, /quest accept <id>, /quest abandon <id>, /quest give <player> <quest>, /quest payout <player> <quest>, or /quest balance [player]");
        }
        
        return true;
    }
    
    private void acceptQuest(Player player, String questId) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());
        Quest quest = plugin.getQuestManager().getQuest(questId);
        
        if (quest == null) {
            player.sendMessage(ChatColor.RED + "Quest not found: " + questId);
            return;
        }
        
        String error = plugin.getQuestManager().canAcceptQuest(data, quest);
        if (error != null) {
            player.sendMessage(ChatColor.RED + error);
            return;
        }
        
        data.setActiveQuest(quest);
        player.sendMessage(ChatColor.GREEN + "Quest accepted: " + quest.getTitle());
        player.sendMessage(ChatColor.GRAY + quest.getDescription());
        quest.getObjectives().forEach(obj ->
            player.sendMessage(ChatColor.DARK_GRAY + "- " + obj.getDescription() + " (" + obj.getAmountCompleted() + "/" + obj.getAmountRequired() + ")"));
    }
    
    private void abandonQuest(Player player, String questId) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());
        
        if (!data.isActive(questId)) {
            player.sendMessage(ChatColor.RED + "You don't have this quest active.");
            return;
        }
        
        data.getActiveQuestProgress().remove(questId);
        player.sendMessage(ChatColor.YELLOW + "Quest abandoned.");
    }
    
    private void handleAdminCmd(CommandSender sender, String[] args) {
        if (args.length < 1) {
            sender.sendMessage(ChatColor.YELLOW + "Usage: /quest admin complete <player> <questId> | /quest admin rank <player>");
            return;
        }
        switch (args[0].toLowerCase()) {
            case "complete": {
                if (args.length < 3) {
                    sender.sendMessage(ChatColor.YELLOW + "Usage: /quest admin complete <player> <questId>");
                    return;
                }
                org.bukkit.OfflinePlayer off = plugin.getServer().getOfflinePlayer(args[1]);
                if (off.getUniqueId() == null) {
                    sender.sendMessage(ChatColor.RED + "Player not found: " + args[1]);
                    return;
                }
                Quest quest = plugin.getQuestManager().getQuest(args[2]);
                if (quest == null) {
                    sender.sendMessage(ChatColor.RED + "Quest not found: " + args[2]);
                    return;
                }
                PlayerData data = plugin.getPlayerDataManager().getPlayerData(off.getUniqueId());
                if (data.getCompletedQuests().containsKey(quest.getId())) {
                    sender.sendMessage(ChatColor.RED + args[1] + " already completed " + quest.getId());
                    return;
                }
                // Mark complete, reward, and run the rank pipeline exactly like a real completion.
                Player online = off.getPlayer();
                if (online != null) {
                    plugin.getPlayerDataManager().giveRewards(online, quest);
                    data.completeQuest(quest.getId());
                    plugin.getRankManager().onQuestCompleted(online, data);
                } else {
                    // Offline target: still grant completion + rank (broadcast skipped personal title).
                    data.completeQuest(quest.getId());
                    plugin.getRankManager().onQuestCompletedOffline(data);
                }
                plugin.getPlayerDataManager().saveData(off.getUniqueId());
                sender.sendMessage(ChatColor.GREEN + "Completed " + quest.getId() + " for " + args[1]
                    + " (total: " + data.getCompletedCount() + ", rank: " + data.getRankId() + ")");
                break;
            }
            case "rank": {
                if (args.length < 2) {
                    sender.sendMessage(ChatColor.YELLOW + "Usage: /quest admin rank <player>");
                    return;
                }
                Player target = plugin.getServer().getPlayer(args[1]);
                if (target == null) {
                    sender.sendMessage(ChatColor.RED + "Player not found (must be online): " + args[1]);
                    return;
                }
                PlayerData data = plugin.getPlayerDataManager().getPlayerData(target.getUniqueId());
                sender.sendMessage(ChatColor.AQUA + target.getName() + ": completed=" + data.getCompletedCount()
                    + ", rank=" + data.getRankId());
                break;
            }
            default:
                sender.sendMessage(ChatColor.YELLOW + "Usage: /quest admin complete <player> <questId> | /quest admin rank <player>");
        }
    }

    private void listQuests(Player player) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());
        player.sendMessage(ChatColor.GOLD + "=== All Quests ===");
        plugin.getQuestManager().getAllQuests().forEach(q -> {
            String suffix = "";
            if (data.getCompletedQuests().containsKey(q.getId())) {
                suffix = ChatColor.GREEN + " [DONE]";
            } else if (q.getRequiredQuestId() != null && !data.getCompletedQuests().containsKey(q.getRequiredQuestId())) {
                suffix = ChatColor.RED + " [LOCKED]";
            }
            player.sendMessage(ChatColor.AQUA + "- " + q.getId() + ": " + q.getTitle() + suffix);
        });
    }
    
    private void showQuestInfo(Player player, String questId) {
        Quest quest = plugin.getQuestManager().getQuest(questId);
        if (quest == null) {
            player.sendMessage(ChatColor.RED + "Quest not found: " + questId);
            return;
        }
        
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());
        
        player.sendMessage(ChatColor.GOLD + "=== " + quest.getTitle() + " ===");
        player.sendMessage(quest.getDescription());
        player.sendMessage(ChatColor.YELLOW + "Type: " + quest.getType());
        player.sendMessage(ChatColor.YELLOW + "Required Level: " + quest.getRequiredLevel());
        
        List<Integer> progress = data.getObjectiveProgress(questId);
        player.sendMessage(ChatColor.YELLOW + "Objectives:");
        List<com.questbook.quest.QuestObjective> objectives = quest.getObjectives();
        for (int i = 0; i < objectives.size(); i++) {
            com.questbook.quest.QuestObjective obj = objectives.get(i);
            int completed = i < progress.size() ? progress.get(i) : 0;
            String status = obj.isComplete() || completed >= obj.getAmountRequired() ? ChatColor.GREEN.toString() : ChatColor.RED.toString();
            player.sendMessage(ChatColor.GRAY + "- " + status + obj.getDescription() + " (" + completed + "/" + obj.getAmountRequired() + ")");
        }
        
        if (data.isActive(questId)) {
            player.sendMessage(ChatColor.YELLOW + "Status: Active - " + String.format("%.0f%%", com.questbook.gui.QuestItemBuilder.progressPercent(objectives, progress)) + "%");
        } else if (data.getCompletedQuests().containsKey(questId)) {
            player.sendMessage(ChatColor.GREEN + "Status: Completed");
        } else {
            player.sendMessage(ChatColor.GRAY + "Status: Available (use /quest accept " + questId + ")");
        }
    }
    
    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            return Arrays.asList("list", "info", "accept", "abandon", "give", "payout", "balance", "admin").stream()
                .filter(s -> s.startsWith(args[0].toLowerCase()))
                .sorted()
                .toList();
        }
        String sub = args[0].toLowerCase();
        boolean adminTarget = sub.equals("give") || sub.equals("payout") || sub.equals("balance");
        if (args.length == 2) {
            if (adminTarget) {
                return plugin.getServer().getOnlinePlayers().stream()
                    .map(Player::getName)
                    .filter(n -> n.toLowerCase().startsWith(args[1].toLowerCase()))
                    .sorted()
                    .toList();
            }
            return plugin.getQuestManager().getAllQuests().stream()
                .map(Quest::getId)
                .filter(id -> id.startsWith(args[1].toLowerCase()))
                .sorted()
                .toList();
        }
        if (args.length == 3 && (sub.equals("give") || sub.equals("payout"))) {
            return plugin.getQuestManager().getAllQuests().stream()
                .map(Quest::getId)
                .filter(id -> id.startsWith(args[2].toLowerCase()))
                .sorted()
                .toList();
        }
        return Collections.emptyList();
    }

    private static String formatBalance(double amount) {
        if (amount >= 1000000) return String.format("%.2fM", amount / 1000000.0);
        if (amount >= 1000) return String.format("%.1fK", amount / 1000.0);
        if (amount == (long) amount) return String.valueOf((long) amount);
        return String.format("%.2f", amount);
    }
}