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
import dev.sentinel.audit.models.AuditAction;
import dev.sentinel.audit.models.AuditSource;
import java.util.Map;
import java.util.UUID;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryPickupItemEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.jetbrains.annotations.NotNull;

/**
 * Listens to inventory-related events and records them to the audit log.
 *
 * <p>Tracks inventory clicks, item pickups, and item drops for audit
 * and rollback purposes.</p>
 */
public final class InventoryListener implements Listener {

    private final AuditService auditService;
    private final SentinelConfig config;

    /**
     * Constructs a new inventory listener.
     *
     * @param auditService the audit service
     * @param config the plugin configuration
     */
    public InventoryListener(@NotNull AuditService auditService, @NotNull SentinelConfig config) {
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Handles inventory open events.
     *
     * @param event the inventory open event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInventoryOpen(InventoryOpenEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!(event.getPlayer() instanceof Player player)) {
            return;
        }
        if (!config.isWorldEnabled(player.getWorld().getName())) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.CONTAINER_OPEN.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.CONTAINER_OPEN,
                player,
                player.getLocation(),
                Map.of(
                        "inventoryType", event.getInventory().getType().name(),
                        "title", event.getView().getTitle()));
        auditService.record(auditEvent);
    }

    /**
     * Handles inventory close events.
     *
     * @param event the inventory close event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInventoryClose(InventoryCloseEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!(event.getPlayer() instanceof Player player)) {
            return;
        }
        if (!config.isWorldEnabled(player.getWorld().getName())) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.CONTAINER_CLOSE.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.CONTAINER_CLOSE,
                player,
                player.getLocation(),
                Map.of(
                        "inventoryType", event.getInventory().getType().name(),
                        "title", event.getView().getTitle()));
        auditService.record(auditEvent);
    }

    /**
     * Handles inventory click events.
     *
     * @param event the inventory click event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInventoryClick(InventoryClickEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!(event.getWhoClicked() instanceof Player player)) {
            return;
        }
        if (!config.isWorldEnabled(player.getWorld().getName())) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.INVENTORY_MOVE.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.INVENTORY_MOVE,
                player,
                player.getLocation(),
                Map.of(
                        "clickType", event.getClick().name(),
                        "slotType", event.getSlotType().name(),
                        "inventoryType", event.getInventory().getType().name(),
                        "item",
                                event.getCurrentItem() != null
                                        ? event.getCurrentItem().getType().name()
                                        : "AIR",
                        "amount",
                                String.valueOf(
                                        event.getCurrentItem() != null
                                                ? event.getCurrentItem().getAmount()
                                                : 0)));
        auditService.record(auditEvent);
    }

    /**
     * Handles item pickup events.
     *
     * @param event the item pickup event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onItemPickup(InventoryPickupItemEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        AuditEvent auditEvent = new AuditEvent(
                UUID.randomUUID(),
                AuditAction.INVENTORY_PICKUP,
                AuditSource.PLAYER,
                UUID.fromString("00000000-0000-0000-0000-000000000000"),
                "HOPPER",
                null,
                null,
                event.getInventory().getLocation(),
                event.getInventory().getLocation().getWorld().getName(),
                java.time.Instant.now(),
                Map.of(
                        "item", event.getItem().getItemStack().getType().name(),
                        "amount", String.valueOf(event.getItem().getItemStack().getAmount()),
                        "inventoryType", event.getInventory().getType().name()));
        auditService.record(auditEvent);
    }

    /**
     * Handles player drop item events.
     *
     * @param event the player drop item event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlayerDropItem(PlayerDropItemEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!config.isWorldEnabled(event.getPlayer().getWorld().getName())) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.INVENTORY_DROP.name())) {
            return;
        }
        AuditEvent auditEvent = AuditEvent.ofPlayer(
                AuditAction.INVENTORY_DROP,
                event.getPlayer(),
                event.getPlayer().getLocation(),
                Map.of(
                        "item", event.getItemDrop().getItemStack().getType().name(),
                        "amount",
                                String.valueOf(
                                        event.getItemDrop().getItemStack().getAmount())));
        auditService.record(auditEvent);
    }
}
