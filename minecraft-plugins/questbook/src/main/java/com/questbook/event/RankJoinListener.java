package com.questbook.event;

import com.questbook.QuestBookPlugin;
import com.questbook.data.PlayerData;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;

public class RankJoinListener implements Listener {
    private final QuestBookPlugin plugin;

    public RankJoinListener(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(event.getPlayer().getUniqueId());
        plugin.getRankManager().refreshOnJoin(event.getPlayer(), data);
    }
}
