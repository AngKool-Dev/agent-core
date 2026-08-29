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
import dev.sentinel.audit.models.AuditSource;
import dev.sentinel.audit.models.InventorySnapshot;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.bukkit.entity.Item;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityRemoveEvent;
import org.bukkit.event.entity.ItemDespawnEvent;
import org.bukkit.inventory.ItemStack;
import org.jetbrains.annotations.NotNull;

/**
 * Tracks ground item entities destroyed by the environment.
 *
 * <p>Captures items lost to natural despawn, falling out of the world (the
 * void), and destruction by fire, lava, or other environmental causes. These
 * are recorded as {@link InventoryChangeRecord}s keyed by world name so they
 * can be rolled back to a chosen recipient.</p>
 */
public final class ItemLossListener implements Listener {

    private final AuditService auditService;
    private final SentinelConfig config;

    /**
     * Constructs a new item loss listener.
     *
     * @param auditService the audit service
     * @param config the plugin configuration
     */
    public ItemLossListener(@NotNull AuditService auditService, @NotNull SentinelConfig config) {
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Handles item despawn events (items that expired on the ground).
     *
     * @param event the item despawn event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onItemDespawn(ItemDespawnEvent event) {
        recordLoss(event.getEntity(), AuditAction.ITEM_DESPAWN, "DESPAWN");
    }

    /**
     * Handles item entity removal caused by the environment.
     *
     * <p>Items that fall out of the world (the void) and items destroyed by
     * fire, lava, or damage do not raise an item-specific event, so they are
     * detected here via their removal cause.</p>
     *
     * @param event the entity remove event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onEntityRemove(EntityRemoveEvent event) {
        if (!(event.getEntity() instanceof Item item)) {
            return;
        }
        switch (event.getCause()) {
            case OUT_OF_WORLD -> recordLoss(item, AuditAction.ITEM_VOID, "VOID");
            case DISCARD, DEATH -> recordLoss(item, AuditAction.ITEM_BURN, "DESTROYED");
            default -> {
                // Pickups, mergers, plugin removal, and unloads are not item losses.
            }
        }
    }

    /**
     * Records a single dropped item as an inventory loss for its world.
     *
     * @param item the item entity being lost
     * @param action the audit action
     * @param cause the destruction cause label
     */
    private void recordLoss(@NotNull Item item, @NotNull AuditAction action, @NotNull String cause) {
        if (auditService == null || config == null) {
            return;
        }
        if (!config.isWorldEnabled(item.getWorld().getName())) {
            return;
        }
        if (!config.getAudit().isLogInventory()) {
            return;
        }
        if (!config.isActionEnabled(action.name())) {
            return;
        }
        ItemStack stack = item.getItemStack();
        if (stack == null || stack.isEmpty()) {
            return;
        }
        InventorySnapshot before = InventorySnapshot.from(List.of(stack));
        InventorySnapshot after = InventorySnapshot.empty(before.size(), null);
        String worldName = item.getWorld().getName();
        AuditEvent auditEvent = new AuditEvent(
                UUID.randomUUID(),
                action,
                AuditSource.NATURAL,
                UUID.fromString("00000000-0000-0000-0000-000000000000"),
                "WORLD",
                null,
                null,
                item.getLocation(),
                worldName,
                java.time.Instant.now(),
                Map.of(
                        "cause", cause,
                        "item", stack.getType().name(),
                        "amount", String.valueOf(stack.getAmount())));
        InventoryChangeRecord change = InventoryChangeRecord.of(auditEvent.id(), "world:" + worldName, before, after);
        auditService.recordInventory(auditEvent, change);
    }
}
