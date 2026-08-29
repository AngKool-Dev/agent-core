/*
 * MIT License
 *
 * Copyright (c) 2026 Sentinel Audit Contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
package dev.sentinel.audit.listeners;

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.api.AuditService;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.database.model.InventoryChangeRecord;
import dev.sentinel.audit.models.AuditAction;
import dev.sentinel.audit.models.InventorySnapshot;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.ItemStack;
import org.jetbrains.annotations.NotNull;

/**
 * Listens to player-related events and records them to the audit log.
 *
 * <p>Tracks player joins, quits, chat messages, and commands for
 * comprehensive player activity auditing.</p>
 */
public final class PlayerListener implements Listener {

    private final AuditService auditService;
    private final SentinelConfig config;

    /**
     * Constructs a new player listener.
     *
     * @param auditService the audit service
     * @param config the plugin configuration
     */
    public PlayerListener(@NotNull AuditService auditService, @NotNull SentinelConfig config) {
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Handles player join events.
     *
     * @param event the player join event
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onPlayerJoin(PlayerJoinEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!config.isWorldEnabled(event.getPlayer().getWorld().getName())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.PLAYER_JOIN.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.PLAYER_JOIN,
                event.getPlayer(),
                event.getPlayer().getLocation(),
                Map.of(
                        "address",
                        event.getPlayer().getAddress() != null
                                ? event.getPlayer().getAddress().getAddress().getHostAddress()
                                : "unknown"));
        auditService.record(auditEvent);
    }

    /**
     * Handles player quit events.
     *
     * @param event the player quit event
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onPlayerQuit(PlayerQuitEvent event) {
        if (auditService == null || config == null) {
            return;
        }
        if (!config.isWorldEnabled(event.getPlayer().getWorld().getName())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.PLAYER_QUIT.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.PLAYER_QUIT, event.getPlayer(), event.getPlayer().getLocation(), Map.of());
        auditService.record(auditEvent);
    }

    /**
     * Handles player chat events.
     *
     * @param event the async chat event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlayerChat(AsyncPlayerChatEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!config.getAudit().isLogChat()) {
            return;
        }
        if (!config.isWorldEnabled(event.getPlayer().getWorld().getName())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.PLAYER_CHAT.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.PLAYER_CHAT,
                event.getPlayer(),
                event.getPlayer().getLocation(),
                Map.of(
                        "message", event.getMessage(),
                        "format", event.getFormat()));
        auditService.record(auditEvent);
    }

    /**
     * Handles player command events.
     *
     * @param event the command preprocess event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlayerCommand(PlayerCommandPreprocessEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!config.getAudit().isLogCommands()) {
            return;
        }
        if (!config.isWorldEnabled(event.getPlayer().getWorld().getName())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.PLAYER_COMMAND.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.PLAYER_COMMAND,
                event.getPlayer(),
                event.getPlayer().getLocation(),
                Map.of("command", event.getMessage()));
        auditService.record(auditEvent);
    }

    /**
     * Handles player death events by capturing the dropped items.
     *
     * @param event the player death event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onPlayerDeath(PlayerDeathEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Player player = event.getEntity();
        if (!config.isWorldEnabled(player.getWorld().getName())) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.PLAYER_DEATH.name())) {
            return;
        }
        List<ItemStack> drops = new ArrayList<>(event.getDrops());
        InventorySnapshot before = InventorySnapshot.from(drops);
        InventorySnapshot after = InventorySnapshot.empty(before.size(), null);
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.PLAYER_DEATH,
                player,
                player.getLocation(),
                Map.of(
                        "cause",
                        player.getLastDamageCause() != null
                                ? player.getLastDamageCause().getCause().name()
                                : "UNKNOWN",
                        "drops",
                        String.valueOf(drops.size())));
        InventoryChangeRecord change =
                InventoryChangeRecord.of(auditEvent.id(), player.getUniqueId().toString(), before, after);
        auditService.recordInventory(auditEvent, change);
    }
}
