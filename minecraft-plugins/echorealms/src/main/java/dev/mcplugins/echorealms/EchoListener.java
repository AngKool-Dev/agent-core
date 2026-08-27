package dev.mcplugins.echorealms;

import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.player.PlayerJoinEvent;

public final class EchoListener implements Listener {

    private final EchoRealmsPlugin plugin;

    public EchoListener(EchoRealmsPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler(ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        if (plugin.settings().disabled(event.getBlock().getWorld().getName())) {
            return;
        }
        plugin.manager().recordPlacement(event.getPlayer(),
                event.getBlock().getWorld(),
                event.getBlock().getX(), event.getBlock().getY(), event.getBlock().getZ());
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        if (!plugin.settings().disabled(event.getPlayer().getWorld().getName())) {
            plugin.manager().dissolveAllOf(event.getPlayer().getUniqueId());
        }
    }
}
