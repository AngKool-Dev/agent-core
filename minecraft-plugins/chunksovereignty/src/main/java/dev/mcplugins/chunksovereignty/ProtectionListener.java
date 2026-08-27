package dev.mcplugins.chunksovereignty;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.title.Title;
import org.bukkit.block.Block;
import org.bukkit.block.data.Ageable;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Event.Result;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerMoveEvent;

import java.time.Duration;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.UUID;

public final class ProtectionListener implements Listener {

    private final SovereigntyPlugin plugin;
    private final Map<UUID, String> lastChunk = new HashMap<>();

    public ProtectionListener(SovereigntyPlugin plugin) {
        this.plugin = plugin;
    }

    private boolean allowed(Player p, Block b) {
        ChunkIndex idx = plugin.index();
        var claim = idx.claimAt(new ChunkIndex.Claim(b.getWorld().getName(),
                b.getX() >> 4, b.getZ() >> 4));
        if (claim == null) {
            return true;
        }
        UUID id = p.getUniqueId();
        return claim.owner.equals(id) || idx.isTrusted(claim.owner, id)
                || p.hasPermission("sovereignty.admin");
    }

    @EventHandler(ignoreCancelled = true)
    public void onBreak(BlockBreakEvent event) {
        if (!plugin.settings().protection
                || plugin.settings().disabled(event.getBlock().getWorld().getName())) {
            return;
        }
        Player p = event.getPlayer();
        if (allowed(p, event.getBlock())) {
            ChunkIndex.Claim c = new ChunkIndex.Claim(event.getBlock().getWorld().getName(),
                    event.getBlock().getX() >> 4, event.getBlock().getZ() >> 4);
            if (p.getUniqueId().equals(plugin.index().ownerAt(c))) {
                plugin.index().addInfluence(p.getUniqueId(), 0);
            }
            return;
        }
        event.setCancelled(true);
        deny(p, "This land belongs to another sovereign.");
    }

    @EventHandler(ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        if (plugin.settings().disabled(event.getBlock().getWorld().getName())) {
            return;
        }
        Player p = event.getPlayer();
        ChunkIndex.Claim c = new ChunkIndex.Claim(event.getBlock().getWorld().getName(),
                event.getBlock().getX() >> 4, event.getBlock().getZ() >> 4);
        UUID owner = plugin.index().ownerAt(c);
        boolean ownChunk = p.getUniqueId().equals(owner);
        if (ownChunk && plugin.settings().placeInfluence > 0) {
            plugin.index().addInfluence(p.getUniqueId(), plugin.settings().placeInfluence);
        }
        if (!plugin.settings().protection || owner == null || ownChunk) {
            return;
        }
        if (plugin.index().isTrusted(owner, p.getUniqueId())
                || p.hasPermission("sovereignty.admin")) {
            return;
        }
        event.setCancelled(true);
        deny(p, "You cannot build in the domain of "
                + nameOf(owner) + ".");
    }

    @EventHandler(ignoreCancelled = true)
    public void onInteract(PlayerInteractEvent event) {
        if (!event.getAction().isRightClick() || !event.hasBlock()) {
            return;
        }
        Block b = event.getClickedBlock();
        if (b == null || !(b.getState() instanceof org.bukkit.inventory.InventoryHolder)) {
            return;
        }
        if (!plugin.settings().protection
                || plugin.settings().disabled(b.getWorld().getName())) {
            return;
        }
        Player p = event.getPlayer();
        if (allowed(p, b)) {
            return;
        }
        event.setUseInteractedBlock(Result.DENY);
        event.setUseItemInHand(Result.DENY);
        deny(p, "Foreign containers stay sealed to you.");
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent event) {
        filterBlast(event.blockList().iterator());
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent event) {
        filterBlast(event.blockList().iterator());
    }

    private void filterBlast(Iterator<Block> it) {
        while (it.hasNext()) {
            Block b = it.next();
            if (plugin.index().ownerAt(new ChunkIndex.Claim(
                    b.getWorld().getName(), b.getX() >> 4, b.getZ() >> 4)) != null) {
                it.remove();
            }
        }
    }

    @EventHandler
    public void onMove(PlayerMoveEvent event) {
        if (!event.hasChangedBlock()) {
            return;
        }
        Player p = event.getPlayer();
        if (plugin.settings().disabled(p.getWorld().getName())) {
            return;
        }
        int cx = event.getTo().getBlockX() >> 4;
        int cz = event.getTo().getBlockZ() >> 4;
        String key = p.getWorld().getName() + "|" + cx + "|" + cz;
        String prev = lastChunk.put(p.getUniqueId(), key);
        if (key.equals(prev)) {
            return;
        }
        ChunkIndex idx = plugin.index();
        UUID nowOwner = idx.ownerAt(new ChunkIndex.Claim(p.getWorld().getName(), cx, cz));
        String before = prev == null ? null : ownerNameOfKey(prev, idx);
        String after = nowOwner == null ? null : nameOf(nowOwner);
        if (java.util.Objects.equals(before, after)) {
            return;
        }
        if (!plugin.settings().announceEnter) {
            return;
        }
        Component title = after == null
                ? Component.text("The Wilds", NamedTextColor.GREEN)
                : Component.text(after + "'s Domain", NamedTextColor.GOLD);
        String subtitle = after == null ? "unclaimed territory"
                : plugin.settings().tierFor(idx.countOwned(nowOwner)).name()
                + " - " + idx.countOwned(nowOwner) + " chunks";
        p.showTitle(Title.title(title,
                Component.text(subtitle, NamedTextColor.GRAY),
                Title.Times.times(Duration.ofMillis(100), Duration.ofMillis(1200),
                        Duration.ofMillis(300))));
    }

    private String ownerNameOfKey(String key, ChunkIndex idx) {
        UUID owner = idx.ownerAt(ChunkIndex.Claim.parse(key));
        return owner == null ? null : nameOf(owner);
    }

    private String nameOf(UUID id) {
        String n = org.bukkit.Bukkit.getOfflinePlayer(id).getName();
        return n == null ? "Unknown" : n;
    }

    private void deny(Player p, String msg) {
        p.sendActionBar(Component.text(msg, NamedTextColor.RED));
    }
}
