package com.questbook.rank;

import com.questbook.QuestBookPlugin;
import com.questbook.data.PlayerData;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.entity.Player;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.Team;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class RankManager {

    private final QuestBookPlugin plugin;
    private final List<RankTier> tiers = new ArrayList<>();

    public static class RankTier {
        final String id;
        final String name;
        final String prefix;   // color code + tag, shown in chat AND above head
        final int minCompleted;
        final boolean announce;

        public RankTier(String id, String name, String prefix, int minCompleted, boolean announce) {
            this.id = id;
            this.name = name;
            this.prefix = prefix;
            this.minCompleted = minCompleted;
            this.announce = announce;
        }
    }

    public RankManager(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }

    /** Load tiers from config.yml (ranks: section). Falls back to built-ins if absent. */
    public void loadRanks() {
        tiers.clear();
        var ranksSection = plugin.getConfig().getConfigurationSection("ranks");
        if (ranksSection != null) {
            for (String key : ranksSection.getKeys(false)) {
                var sec = ranksSection.getConfigurationSection(key);
                if (sec == null) continue;
                String name = sec.getString("name", key);
                String prefix = ChatColor.translateAlternateColorCodes('&', sec.getString("prefix", "[" + name + "] "));
                int min = sec.getInt("min-completed", Integer.MAX_VALUE);
                boolean announce = sec.getBoolean("announce", false);
                tiers.add(new RankTier(key, name, prefix, min, announce));
            }
        } else {
            // Built-in defaults
            tiers.add(new RankTier("initiate", "Initiate", ChatColor.GRAY + "[Initiate] ", 0, false));
            tiers.add(new RankTier("hero", "Hero", ChatColor.GOLD + "[Hero] ", 100, true));
            tiers.add(new RankTier("legend", "Legend", ChatColor.AQUA + "[Legend] ", 300, true));
            tiers.add(new RankTier("mythic", "Mythic", ChatColor.LIGHT_PURPLE + "[Mythic] ", 600, true));
            tiers.add(new RankTier("god", "God", ChatColor.RED + "[God] ", 1000, true));
        }
        tiers.sort(Comparator.comparingInt(t -> t.minCompleted));
        plugin.getLogger().info("Loaded " + tiers.size() + " rank tiers");
    }

    public RankTier getTierFor(int completed) {
        RankTier result = tiers.get(0);
        for (RankTier t : tiers) {
            if (completed >= t.minCompleted) result = t;
            else break;
        }
        return result;
    }

    public RankTier getTier(String id) {
        for (RankTier t : tiers) if (t.id.equalsIgnoreCase(id)) return t;
        return tiers.get(0);
    }

    /** Apply rank teams for every loaded player at startup (offline-safe by name).
     *  Ensures chat + nametag prefixes are correct before the player's first join. */
    public void applyAllRanks(com.questbook.data.PlayerDataManager pdm) {
        for (org.bukkit.OfflinePlayer op : Bukkit.getOfflinePlayers()) {
            PlayerData data = pdm.getPlayerData(op.getUniqueId());
            if (data.getCompletedCount() == 0 && data.getRankId() == null) continue;
            RankTier tier = data.getRankId() != null ? getTier(data.getRankId()) : getTierFor(data.getCompletedCount());
            data.setRankId(tier.id);
            // Apply to the online player if present, else register the name so the
            // nametag is correct the moment they connect.
            Player online = op.getPlayer();
            if (online != null) {
                applyTeam(online, tier);
            } else {
                Scoreboard board = Bukkit.getScoreboardManager().getMainScoreboard();
                String teamName = "qb_" + tier.id.toLowerCase();
                Team team = board.getTeam(teamName);
                if (team == null) {
                    team = board.registerNewTeam(teamName);
                    team.setPrefix(tier.prefix);
                    team.setOption(Team.Option.NAME_TAG_VISIBILITY, Team.OptionStatus.ALWAYS);
                    team.setOption(Team.Option.COLLISION_RULE, Team.OptionStatus.NEVER);
                }
                if (op.getName() != null && !team.hasEntry(op.getName())) {
                    team.addEntry(op.getName());
                }
            }
        }
        plugin.getLogger().info("Applied rank teams to loaded players");
    }

    /**
     * Evaluated after a quest is completed. Updates the player's stored rank,
     * refreshes their scoreboard team (chat + nametag prefix), and broadcasts
     * a promotion if they crossed into a new announce tier.
     */
    public void onQuestCompleted(Player player, PlayerData data) {
        int completed = data.getCompletedCount();
        RankTier newTier = getTierFor(completed);

        String oldId = data.getRankId();
        RankTier oldTier = oldId != null ? getTier(oldId) : tiers.get(0);

        data.setRankId(newTier.id);
        applyTeam(player, newTier);
        plugin.getPlayerDataManager().saveData(player.getUniqueId());

        boolean promoted = oldTier == null || newTier.minCompleted > oldTier.minCompleted;
        if (promoted && newTier.announce) {
            announcePromotion(player, newTier, completed);
        }
    }

    /** Offline variant: completion came from an admin command for a not-logged-in player.
     *  Computes/persists rank, applies the team by name, and broadcasts the promotion. */
    public void onQuestCompletedOffline(PlayerData data) {
        int completed = data.getCompletedCount();
        RankTier newTier = getTierFor(completed);
        String oldId = data.getRankId();
        RankTier oldTier = oldId != null ? getTier(oldId) : tiers.get(0);
        data.setRankId(newTier.id);
        Scoreboard board = Bukkit.getScoreboardManager().getMainScoreboard();
        String teamName = "qb_" + newTier.id.toLowerCase();
        Team team = board.getTeam(teamName);
        if (team == null) {
            team = board.registerNewTeam(teamName);
            team.setPrefix(newTier.prefix);
            team.setOption(Team.Option.NAME_TAG_VISIBILITY, Team.OptionStatus.ALWAYS);
            team.setOption(Team.Option.COLLISION_RULE, Team.OptionStatus.NEVER);
        }
        org.bukkit.OfflinePlayer off = Bukkit.getOfflinePlayer(java.util.UUID.fromString(data.getPlayerId()));
        if (off.getName() != null && !team.hasEntry(off.getName())) {
            team.addEntry(off.getName());
        }
        boolean promoted = oldTier == null || newTier.minCompleted > oldTier.minCompleted;
        if (promoted && newTier.announce) {
            announcePromotionOffline(data.getPlayerId(), newTier);
        }
    }

    private void announcePromotionOffline(String playerId, RankTier tier) {
        org.bukkit.OfflinePlayer off = Bukkit.getOfflinePlayer(java.util.UUID.fromString(playerId));
        String name = off.getName() != null ? off.getName() : playerId;
        Bukkit.broadcastMessage(ChatColor.DARK_PURPLE + "=============================================");
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(ChatColor.LIGHT_PURPLE + "\u2728 " + ChatColor.GOLD + name
                + ChatColor.LIGHT_PURPLE + " has ascended to the rank of " + tier.prefix + ChatColor.LIGHT_PURPLE + "!");
        Bukkit.broadcastMessage(ChatColor.AQUA + rankFlavor(tier.id));
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(ChatColor.DARK_PURPLE + "=============================================");
        for (Player online : Bukkit.getOnlinePlayers()) {
            online.sendTitle(ChatColor.GOLD + name + " promoted!",
                    ChatColor.AQUA + "Reached " + tier.name, 10, 80, 20);
        }
    }

    /** Apply (or refresh) the scoreboard team so the prefix shows in chat AND above the head. */
    public void applyTeam(Player player, RankTier tier) {
        Scoreboard board = Bukkit.getScoreboardManager().getMainScoreboard();
        String teamName = "qb_" + tier.id.toLowerCase();
        Team team = board.getTeam(teamName);
        if (team == null) {
            team = board.registerNewTeam(teamName);
            team.setPrefix(tier.prefix);
            team.setOption(Team.Option.NAME_TAG_VISIBILITY, Team.OptionStatus.ALWAYS);
            team.setOption(Team.Option.COLLISION_RULE, Team.OptionStatus.NEVER);
        }
        // Remove from any other qb_ team first
        for (Team t : board.getTeams()) {
            if (t.getName().startsWith("qb_") && !t.getName().equals(teamName) && t.hasEntry(player.getName())) {
                t.removeEntry(player.getName());
            }
        }
        if (!team.hasEntry(player.getName())) {
            team.addEntry(player.getName());
        }
    }

    /** Re-apply stored rank on join (keeps chat + nametag after restart). */
    public void refreshOnJoin(Player player, PlayerData data) {
        // Ensure the player is on the main scoreboard so the team prefix (chat + nametag) renders.
        Scoreboard main = Bukkit.getScoreboardManager().getMainScoreboard();
        if (player.getScoreboard() != main) {
            player.setScoreboard(main);
        }
        RankTier tier = data.getRankId() != null ? getTier(data.getRankId()) : getTierFor(data.getCompletedCount());
        data.setRankId(tier.id);
        applyTeam(player, tier);
    }

    private void announcePromotion(Player player, RankTier tier, int completedCount) {
        String name = player.getName();
        Bukkit.broadcastMessage(ChatColor.DARK_PURPLE + "=============================================");
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(ChatColor.LIGHT_PURPLE + "\u2728 " + ChatColor.GOLD + name
                + ChatColor.LIGHT_PURPLE + " has ascended to the rank of " + tier.prefix + ChatColor.LIGHT_PURPLE + "!");
        Bukkit.broadcastMessage(ChatColor.AQUA + rankFlavor(tier.id));
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(ChatColor.DARK_GRAY + "Completed quests: " + completedCount);
        Bukkit.broadcastMessage(ChatColor.DARK_PURPLE + "=============================================");

        for (Player online : Bukkit.getOnlinePlayers()) {
            if (online.getUniqueId().equals(player.getUniqueId())) {
                online.resetTitle();
                online.sendTitle(ChatColor.GOLD + tier.prefix.trim(),
                        ChatColor.LIGHT_PURPLE + "You have been promoted!", 10, 80, 20);
                plugin.getServer().getScheduler().runTaskLater(plugin, () ->
                        online.sendTitle(ChatColor.GOLD + "A new rank achieved",
                                ChatColor.AQUA + tier.name + " — " + rankFlavor(tier.id), 10, 100, 20), 100L);
            } else {
                online.sendTitle(ChatColor.GOLD + name + " promoted!",
                        ChatColor.AQUA + "Reached " + tier.name, 10, 80, 20);
            }
        }
    }

    private String rankFlavor(String id) {
        return switch (id.toLowerCase()) {
            case "hero" -> "The realm whispers your name among the brave.";
            case "legend" -> "Bards will sing of your deeds for generations.";
            case "mythic" -> "Your legend bends the fabric of the world.";
            case "god" -> "You have transcended mortality. The heavens themselves bow.";
            default -> "Your journey continues.";
        };
    }
}
