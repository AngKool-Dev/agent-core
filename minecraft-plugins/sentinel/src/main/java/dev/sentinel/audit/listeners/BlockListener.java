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
import dev.sentinel.audit.database.model.BlockChangeRecord;
import dev.sentinel.audit.models.AuditAction;
import dev.sentinel.audit.models.AuditSource;
import dev.sentinel.audit.models.BlockSnapshot;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.BlockRedstoneEvent;
import org.bukkit.event.block.SignChangeEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.jetbrains.annotations.NotNull;

/**
 * Listens to block-related events and records them to the audit log.
 *
 * <p>Tracks block placement, breaking, and modification events, storing before and
 * after states for inspection and rollback.</p>
 */
public final class BlockListener implements Listener {

    private final AuditService auditService;
    private final SentinelConfig config;

    /**
     * Constructs a new block listener.
     *
     * @param auditService the audit service
     * @param config the plugin configuration
     */
    public BlockListener(@NotNull AuditService auditService, @NotNull SentinelConfig config) {
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Handles block break events.
     *
     * @param event the block break event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onBlockBreak(BlockBreakEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!shouldAudit(event.getBlock())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.BLOCK_BREAK.name())) {
            return;
        }
        Block block = event.getBlock();
        Map<String, String> metadata = Map.of(
                "material", block.getType().name(),
                "blockData", block.getBlockData().getAsString(),
                "tool",
                        event.getPlayer()
                                .getInventory()
                                .getItemInMainHand()
                                .getType()
                                .name(),
                "gamemode", event.getPlayer().getGameMode().name());

        recordBlockChange(
                AuditAction.BLOCK_BREAK,
                AuditSource.PLAYER,
                event.getPlayer().getUniqueId(),
                event.getPlayer().getName(),
                block,
                metadata,
                BlockSnapshot.capture(block),
                BlockSnapshot.from(Material.AIR.createBlockData()));
    }

    /**
     * Handles block place events.
     *
     * @param event the block place event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onBlockPlace(BlockPlaceEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        if (!shouldAudit(event.getBlock())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.BLOCK_PLACE.name())) {
            return;
        }
        Block block = event.getBlock();
        BlockData placedData = block.getBlockData();
        Map<String, String> metadata = Map.of(
                "material", placedData.getMaterial().name(),
                "blockData", placedData.getAsString(),
                "against", event.getBlockAgainst().getType().name(),
                "hand", event.getHand().name());

        recordBlockChange(
                AuditAction.BLOCK_PLACE,
                AuditSource.PLAYER,
                event.getPlayer().getUniqueId(),
                event.getPlayer().getName(),
                block,
                metadata,
                BlockSnapshot.capture(event.getBlockReplacedState()),
                BlockSnapshot.capture(block));
    }

    /**
     * Handles block explode events (TNT, creeper, etc.).
     *
     * @param event the block explode event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        for (Block block : event.blockList()) {
            if (!shouldAudit(block)) {
                continue;
            }
            Map<String, String> metadata = Map.of(
                    "material", block.getType().name(),
                    "blockData", block.getBlockData().getAsString(),
                    "cause", "EXPLOSION");

            recordBlockChange(
                    AuditAction.BLOCK_BREAK,
                    AuditSource.NATURAL,
                    UUID.fromString("00000000-0000-0000-0000-000000000000"),
                    "EXPLOSION",
                    block,
                    metadata,
                    BlockSnapshot.capture(block),
                    BlockSnapshot.from(Material.AIR.createBlockData()));
        }
    }

    /**
     * Handles entity explode events (TNT, creeper, etc.).
     *
     * <p>Entity explosions control which blocks are destroyed via the event's
     * mutable block list, so those blocks must be captured here rather than in
     * a {@code BlockExplodeEvent} handler (which only covers blocks destroyed
     * by a block-level explosion such as a bed or respawn anchor).</p>
     *
     * @param event the entity explode event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        EntityType entityType = event.getEntity() != null ? event.getEntity().getType() : EntityType.UNKNOWN;
        UUID actorId = UUID.fromString("00000000-0000-0000-0000-000000000000");
        String actorName = entityType.name();
        AuditSource source = AuditSource.NATURAL;
        if (event.getEntity() instanceof TNTPrimed tnt && tnt.getSource() instanceof Player sourcePlayer) {
            actorId = sourcePlayer.getUniqueId();
            actorName = sourcePlayer.getName();
            source = AuditSource.PLAYER;
        }
        for (Block block : List.copyOf(event.blockList())) {
            if (!shouldAudit(block)) {
                continue;
            }
            Map<String, String> metadata = Map.of(
                    "material", block.getType().name(),
                    "blockData", block.getBlockData().getAsString(),
                    "cause", "EXPLOSION",
                    "entityType", entityType.name());

            recordBlockChange(
                    AuditAction.BLOCK_BREAK,
                    source,
                    actorId,
                    actorName,
                    block,
                    metadata,
                    BlockSnapshot.capture(block),
                    BlockSnapshot.from(Material.AIR.createBlockData()));
        }
    }

    /**
     * Handles entity change block events (falling blocks, pistons, etc.).
     *
     * @param event the entity change block event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onEntityChangeBlock(EntityChangeBlockEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Block block = event.getBlock();
        if (!shouldAudit(block)) {
            return;
        }
        Map<String, String> metadata = Map.of(
                "material", block.getType().name(),
                "blockData", block.getBlockData().getAsString(),
                "entityType", event.getEntityType().name(),
                "cause", "ENTITY_CHANGE");

        recordBlockChange(
                AuditAction.BLOCK_MODIFY,
                AuditSource.ENTITY,
                event.getEntity().getUniqueId(),
                event.getEntity().getType().name(),
                block,
                metadata,
                BlockSnapshot.capture(block),
                BlockSnapshot.from(event.getTo().createBlockData()));
    }

    /**
     * Handles block burn events (fire, lava).
     *
     * @param event the block burn event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onBlockBurn(BlockBurnEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Block block = event.getBlock();
        if (!shouldAudit(block)) {
            return;
        }
        Map<String, String> metadata = Map.of(
                "material", block.getType().name(),
                "blockData", block.getBlockData().getAsString(),
                "cause", "FIRE");

        recordBlockChange(
                AuditAction.BLOCK_BREAK,
                AuditSource.NATURAL,
                UUID.fromString("00000000-0000-0000-0000-000000000000"),
                "FIRE",
                block,
                metadata,
                BlockSnapshot.capture(block),
                BlockSnapshot.from(Material.AIR.createBlockData()));
    }

    /**
     * Handles block redstone events.
     *
     * @param event the redstone event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBlockRedstone(BlockRedstoneEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Block block = event.getBlock();
        if (!shouldAudit(block)) {
            return;
        }
        Map<String, String> metadata = Map.of(
                "material", block.getType().name(),
                "oldCurrent", String.valueOf(event.getOldCurrent()),
                "newCurrent", String.valueOf(event.getNewCurrent()));

        AuditEvent auditEvent = new AuditEvent(
                UUID.randomUUID(),
                AuditAction.BLOCK_MODIFY,
                AuditSource.NATURAL,
                UUID.fromString("00000000-0000-0000-0000-000000000000"),
                "WORLD",
                null,
                null,
                block.getLocation(),
                block.getWorld().getName(),
                java.time.Instant.now(),
                metadata);
        auditService.record(auditEvent);
    }

    /**
     * Handles sign change events.
     *
     * @param event the sign change event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSignChange(SignChangeEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Block block = event.getBlock();
        if (!shouldAudit(block)) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.SIGN_EDIT.name())) {
            return;
        }
        StringBuilder lines = new StringBuilder();
        for (net.kyori.adventure.text.Component line : event.lines()) {
            lines.append(net.kyori.adventure.text.minimessage.MiniMessage.miniMessage()
                            .serialize(line))
                    .append("|");
        }
        Map<String, String> metadata = Map.of(
                "material", block.getType().name(),
                "blockData", block.getBlockData().getAsString(),
                "lines", lines.toString());

        AuditEvent auditEvent =
                AuditEvent.ofPlayer(AuditAction.SIGN_EDIT, event.getPlayer(), block.getLocation(), metadata);
        auditService.record(auditEvent);
    }

    /**
     * Records an audit event and its associated block change.
     *
     * @param action the audit action
     * @param source the audit source
     * @param actorId the actor UUID
     * @param actorName the actor display name
     * @param block the affected block
     * @param metadata additional event metadata
     * @param before the block state before the change
     * @param after the block state after the change
     */
    private void recordBlockChange(
            @NotNull AuditAction action,
            @NotNull AuditSource source,
            @NotNull UUID actorId,
            @NotNull String actorName,
            @NotNull Block block,
            @NotNull Map<String, String> metadata,
            @NotNull BlockSnapshot before,
            @NotNull BlockSnapshot after) {
        AuditEvent auditEvent = new AuditEvent(
                UUID.randomUUID(),
                action,
                source,
                actorId,
                actorName,
                null,
                null,
                block.getLocation(),
                block.getWorld().getName(),
                java.time.Instant.now(),
                metadata);
        BlockChangeRecord change = BlockChangeRecord.of(
                auditEvent.id(), block.getWorld().getName(), block.getX(), block.getY(), block.getZ(), before, after);
        auditService.recordBlock(auditEvent, List.of(change));
    }

    /**
     * Checks if a block event should be audited.
     *
     * @param block the block involved in the event
     * @return true if the event should be audited
     */
    private boolean shouldAudit(@NotNull Block block) {
        if (!config.isWorldEnabled(block.getWorld().getName())) {
            return false;
        }
        if (block.getType() == Material.AIR) {
            return false;
        }
        return true;
    }
}
