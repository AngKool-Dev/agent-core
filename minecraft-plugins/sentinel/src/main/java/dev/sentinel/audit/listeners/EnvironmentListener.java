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
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockFadeEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockSpreadEvent;
import org.jetbrains.annotations.NotNull;

/**
 * Records environmental changes to blocks so they can be rolled back.
 *
 * <p>Fire spread, fire fade, block ignition, and liquid flow all modify the
 * world without a player action. Recording them as block changes lets
 * rollback remove fire, water, and lava that covered a restored area.</p>
 */
public final class EnvironmentListener implements Listener {

    private static final UUID WORLD_UUID = UUID.fromString("00000000-0000-0000-0000-000000000000");

    private final AuditService auditService;
    private final SentinelConfig config;

    /**
     * Constructs a new environment listener.
     *
     * @param auditService the audit service
     * @param config the plugin configuration
     */
    public EnvironmentListener(@NotNull AuditService auditService, @NotNull SentinelConfig config) {
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Handles fire spreading to a neighbouring block.
     *
     * @param event the block spread event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onFireSpread(BlockSpreadEvent event) {
        if (!isFire(event.getSource())) {
            return;
        }
        Block block = event.getBlock();
        recordAmbientChange(
                block,
                AuditAction.FIRE_SPREAD,
                BlockSnapshot.capture(block),
                BlockSnapshot.from(event.getNewState().getBlockData()));
    }

    /**
     * Handles fire fading out.
     *
     * @param event the block fade event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onFireFade(BlockFadeEvent event) {
        Block block = event.getBlock();
        if (!isFire(block)) {
            return;
        }
        recordAmbientChange(
                block,
                AuditAction.FIRE_FADE,
                BlockSnapshot.capture(block),
                BlockSnapshot.from(Material.AIR.createBlockData()));
    }

    /**
     * Handles blocks being ignited by fire or other sources.
     *
     * @param event the block ignite event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBlockIgnite(BlockIgniteEvent event) {
        Block block = event.getBlock();
        if (block.getType() == Material.AIR) {
            return;
        }
        recordAmbientChange(
                block,
                AuditAction.FIRE_CATCH,
                BlockSnapshot.capture(block),
                BlockSnapshot.from(org.bukkit.Bukkit.createBlockData("minecraft:fire")));
    }

    /**
     * Handles liquid flowing from one block to another.
     *
     * <p>Records the destination cell so that rolled-back areas are no longer
     * flooded. Only cells that are not already the same liquid are recorded to
     * avoid flooding the database with steady-state flow events.</p>
     *
     * @param event the block from-to event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onLiquidFlow(BlockFromToEvent event) {
        Block fromBlock = event.getBlock();
        Material liquid = fromBlock.getType();
        if (liquid != Material.WATER && liquid != Material.LAVA) {
            return;
        }
        Block toBlock = event.getToBlock();
        if (toBlock.getType() == liquid) {
            return;
        }
        recordAmbientChange(
                toBlock,
                AuditAction.LIQUID_FLOW,
                BlockSnapshot.capture(toBlock),
                BlockSnapshot.from(liquid.createBlockData()));
    }

    /**
     * Records a single ambient block change.
     *
     * @param block the affected block
     * @param action the audit action
     * @param before the block state before the change
     * @param after the block state after the change
     */
    private void recordAmbientChange(
            @NotNull Block block,
            @NotNull AuditAction action,
            @NotNull BlockSnapshot before,
            @NotNull BlockSnapshot after) {
        if (auditService == null || config == null) {
            return;
        }
        if (!config.isWorldEnabled(block.getWorld().getName())) {
            return;
        }
        if (!config.isActionEnabled(action.name())) {
            return;
        }
        Map<String, String> metadata = Map.of(
                "material", block.getType().name(),
                "blockData", block.getBlockData().getAsString(),
                "cause", action.name());

        AuditEvent auditEvent = new AuditEvent(
                UUID.randomUUID(),
                action,
                AuditSource.NATURAL,
                WORLD_UUID,
                "WORLD",
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
     * Checks whether a block is fire.
     *
     * @param block the block
     * @return true if the block is fire
     */
    private boolean isFire(@NotNull Block block) {
        return block.getType() == Material.FIRE;
    }
}
