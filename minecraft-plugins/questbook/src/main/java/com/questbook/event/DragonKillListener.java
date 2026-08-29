package com.questbook.event;

import com.questbook.QuestBookPlugin;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.entity.EnderDragon;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDeathEvent;

public class DragonKillListener implements Listener {

    private final QuestBookPlugin plugin;

    public DragonKillListener(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onEnderDragonDeath(EntityDeathEvent event) {
        if (!(event.getEntity() instanceof EnderDragon)) return;

        boolean wasFirstKill = !plugin.getWorldState().isEnderDragonKilled();
        plugin.getWorldState().setEnderDragonKilled(true);

        Player killer = event.getEntity().getKiller();
        String name = killer != null ? killer.getName() : "The Ender Dragon";

        if (wasFirstKill) {
            announceWorldConqueror(killer, true);
        } else {
            announceWorldConqueror(killer, false);
        }
    }

    private void announceWorldConqueror(Player killer, boolean firstKill) {
        String playerName = killer != null ? killer.getName() : "The World";

        Bukkit.broadcastMessage(ChatColor.DARK_PURPLE + "=============================================");
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(ChatColor.LIGHT_PURPLE + "\u2728 " + ChatColor.GOLD + playerName + ChatColor.LIGHT_PURPLE + " has vanquished the Ender Dragon!");
        if (firstKill) {
            Bukkit.broadcastMessage(ChatColor.AQUA + "The realm has never seen such a slayer. The Great Dragon of the Abyss fills the sky no more.");
        } else {
            Bukkit.broadcastMessage(ChatColor.AQUA + "The resurrected horror has been cast down once more!");
        }
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(ChatColor.LIGHT_PURPLE + "\u2728 " + ChatColor.AQUA + "A new legend is born: " +
            ChatColor.GOLD + "[World_Conqueror]" + ChatColor.AQUA + " \u2728");
        Bukkit.broadcastMessage(ChatColor.DARK_GRAY + "Marking " + playerName + " forever as the one who dared the abyss and won.");
        Bukkit.broadcastMessage(ChatColor.DARK_PURPLE + "=============================================");

        for (Player online : Bukkit.getOnlinePlayers()) {
            if (killer != null && online.getUniqueId().equals(killer.getUniqueId())) {
                online.resetTitle();
                online.sendTitle(ChatColor.GOLD + "\u2728 [World_Conqueror] \u2728",
                    ChatColor.LIGHT_PURPLE + "You have conquered the End!",
                    10, 80, 20);
                plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
                    online.sendTitle(ChatColor.GOLD + "The Abyss Trembles",
                        ChatColor.AQUA + "Your name will be sung for a thousand years",
                        10, 100, 20);
                }, 100L);
            } else {
                online.sendTitle(ChatColor.GOLD + "The Ender Dragon has fallen!",
                    ChatColor.AQUA + playerName + " earned [World_Conqueror]",
                    10, 80, 20);
            }
        }
    }
}