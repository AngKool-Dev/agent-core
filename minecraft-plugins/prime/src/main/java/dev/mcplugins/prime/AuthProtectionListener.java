package dev.mcplugins.prime;

import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.player.*;

public final class AuthProtectionListener implements Listener {

    private final PrimePlugin plugin;
    private final AuthManager auth;

    public AuthProtectionListener(PrimePlugin plugin, AuthManager auth) {
        this.plugin = plugin;
        this.auth = auth;
    }

    private boolean isProtected(Player player) {
        if (plugin.getConfig().getBoolean("auth.premium-bypass", true) && auth.isPremium(player)) {
            return false;
        }
        AuthListener.AuthSession session = plugin.getListener().getSession(player.getUniqueId());
        return session == null || !session.isAuthenticated();
    }

    @EventHandler
    public void onChat(AsyncPlayerChatEvent event) {
        if (isProtected(event.getPlayer())) {
            event.setCancelled(true);
            event.getPlayer().sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auth-required", "&cPlease authenticate with /login <password>")));
        }
    }

    @EventHandler
    public void onCommand(PlayerCommandPreprocessEvent event) {
        if (isProtected(event.getPlayer())) {
            String msg = event.getMessage().toLowerCase();
            if (msg.startsWith("/login") || msg.startsWith("/register") || msg.startsWith("/auth")) {
                return;
            }
            event.setCancelled(true);
            event.getPlayer().sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auth-required", "&cPlease authenticate with /login <password>")));
        }
    }

    @EventHandler
    public void onInteract(PlayerInteractEvent event) {
        if (isProtected(event.getPlayer())) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onMove(PlayerMoveEvent event) {
        if (isProtected(event.getPlayer())) {
            // Allow looking around but not moving away
            if (event.getFrom().getX() != event.getTo().getX() || event.getFrom().getZ() != event.getTo().getZ()) {
                event.getPlayer().teleport(event.getFrom());
            }
        }
    }

    @EventHandler
    public void onDamage(EntityDamageEvent event) {
        if (event.getEntity() instanceof Player player && isProtected(player)) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onInventory(InventoryClickEvent event) {
        if (event.getWhoClicked() instanceof Player player && isProtected(player)) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onBreak(BlockBreakEvent event) {
        if (isProtected(event.getPlayer())) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onPlace(BlockPlaceEvent event) {
        if (isProtected(event.getPlayer())) {
            event.setCancelled(true);
        }
    }
}
