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
import dev.sentinel.audit.api.InspectionService;
import dev.sentinel.audit.inspector.InspectionMode;
import dev.sentinel.audit.util.MessageUtil;
import java.util.List;
import org.bukkit.Bukkit;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.plugin.Plugin;
import org.jetbrains.annotations.NotNull;

/**
 * Listens for block inspections while inspection mode is active.
 *
 * <p>When a player has inspection mode enabled, right-clicking a block
 * shows that block's audit history instead of interacting with it.</p>
 */
public final class InspectListener implements Listener {

    private static final org.slf4j.Logger LOGGER = org.slf4j.LoggerFactory.getLogger(InspectListener.class);

    private final InspectionMode inspectionMode;
    private final InspectionService inspectionService;
    private final Plugin plugin;

    /**
     * Constructs a new inspect listener.
     *
     * @param inspectionMode the inspection mode tracker
     * @param inspectionService the inspection service
     * @param plugin the owning plugin, used to schedule main thread messages
     */
    public InspectListener(
            @NotNull InspectionMode inspectionMode,
            @NotNull InspectionService inspectionService,
            @NotNull Plugin plugin) {
        this.inspectionMode = inspectionMode;
        this.inspectionService = inspectionService;
        this.plugin = plugin;
    }

    /**
     * Handles player right-clicks on blocks while inspection mode is active.
     *
     * <p>If the click is not on a block (e.g. an air click), a ray trace is
     * used to find the first solid block the player is looking at.</p>
     *
     * @param event the player interact event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onPlayerInteract(@NotNull PlayerInteractEvent event) {
        Player player = event.getPlayer();
        if (!inspectionMode.isActive(player.getUniqueId())) {
            return;
        }
        if (event.getAction() != Action.RIGHT_CLICK_BLOCK
                && event.getAction() != Action.RIGHT_CLICK_AIR
                && event.getAction() != Action.LEFT_CLICK_BLOCK
                && event.getAction() != Action.LEFT_CLICK_AIR) {
            return;
        }
        event.setCancelled(true);
        Block block = event.getClickedBlock();
        if (block == null || block.getType().isAir()) {
            inspectAim(player);
        } else {
            inspectBlock(player, block);
        }
    }

    /**
     * Inspects the cell the player is aiming at through an air click. Broken
     * blocks leave an air cell, so the block directly in front of the ray hit
     * is checked first before falling back to the solid target.
     *
     * @param player the inspecting player
     */
    private void inspectAim(@NotNull Player player) {
        var ray = player.rayTraceBlocks(player.getServer().getViewDistance() * 16.0, FluidCollisionMode.NEVER);
        if (ray == null || ray.getHitBlock() == null) {
            MessageUtil.send(player, "<gray>No block in sight.");
            return;
        }
        Location eye = player.getEyeLocation();
        var direction = eye.getDirection();
        Location hit = ray.getHitPosition().toLocation(player.getWorld());
        Block airCell = hit.clone()
                .subtract(direction.getX() * 0.5, direction.getY() * 0.5, direction.getZ() * 0.5)
                .getBlock();
        Block solid = ray.getHitBlock();
        LOGGER.info(
                "Inspecting air cell at {},{},{} (solid {}) for {}",
                airCell.getX(),
                airCell.getY(),
                airCell.getZ(),
                solid.getType(),
                player.getName());
        inspectionService.inspectBlock(airCell.getLocation(), 10).whenComplete((events, error) -> {
            if (error != null) {
                reportFailure(player, error);
                return;
            }
            if (!events.isEmpty()) {
                LOGGER.info(
                        "Inspection of air cell at {},{},{} returned {} events for {}",
                        airCell.getX(),
                        airCell.getY(),
                        airCell.getZ(),
                        events.size(),
                        player.getName());
                sendInspection(
                        player,
                        airCell.getType().name() + " (removed) @ " + airCell.getX() + ", " + airCell.getY() + ", "
                                + airCell.getZ(),
                        airCell.getLocation(),
                        events);
                return;
            }
            inspectBlock(player, solid);
        });
    }

    /**
     * Inspects a single block for the given player, expanding to a small
     * neighborhood when the exact cell has no records.
     *
     * @param player the inspecting player
     * @param block the block to inspect
     */
    private void inspectBlock(@NotNull Player player, @NotNull Block block) {
        Location location = block.getLocation();
        inspectionService.inspectBlock(location, 10).whenComplete((events, error) -> {
            if (error != null) {
                LOGGER.info(
                        "Inspection query failed for {} at {},{},{}: {}",
                        player.getName(),
                        location.getBlockX(),
                        location.getBlockY(),
                        location.getBlockZ(),
                        error.getMessage());
                reportFailure(player, error);
                return;
            }
            LOGGER.info(
                    "Inspection of {},{},{} returned {} events for {}",
                    location.getBlockX(),
                    location.getBlockY(),
                    location.getBlockZ(),
                    events.size(),
                    player.getName());
            String title = block.getType().name() + " @ " + location.getBlockX() + ", " + location.getBlockY() + ", "
                    + location.getBlockZ();
            if (!events.isEmpty()) {
                Bukkit.getScheduler().runTask(plugin, () -> sendInspection(player, title, location, events));
                return;
            }
            expandInspection(player, block);
        });
    }

    /**
     * When the clicked cell has no records, expands the search to the 3x3x3
     * region around it. Right-clicking where a broken block used to be often
     * targets a neighboring cell, so the surroundings can still hold the
     * player's edits.
     *
     * @param player the inspecting player
     * @param block the block that had no records
     */
    private void expandInspection(@NotNull Player player, @NotNull Block block) {
        Location bottom = block.getLocation().clone().add(-1, -1, -1);
        Location top = block.getLocation().clone().add(1, 1, 1);
        inspectionService.inspectRegion(bottom, top, 30).whenComplete((events, error) -> {
            if (error != null) {
                reportFailure(player, error);
                return;
            }
            LOGGER.info(
                    "Neighborhood expansion of {},{},{} returned {} events for {}",
                    block.getX(),
                    block.getY(),
                    block.getZ(),
                    events.size(),
                    player.getName());
            String title =
                    "~ " + block.getType().name() + " @ " + block.getX() + ", " + block.getY() + ", " + block.getZ();
            Bukkit.getScheduler().runTask(plugin, () -> sendInspection(player, title, block.getLocation(), events));
        });
    }

    /**
     * Handles player right-clicks on entities while inspection mode is active.
     *
     * @param event the player interact entity event
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onPlayerInteractEntity(@NotNull PlayerInteractEntityEvent event) {
        Player player = event.getPlayer();
        if (!inspectionMode.isActive(player.getUniqueId())) {
            return;
        }
        Entity entity = event.getRightClicked();
        event.setCancelled(true);
        Location location = entity.getLocation();
        inspectionService.inspectBlock(location, 10).whenComplete((events, error) -> {
            if (error != null) {
                Bukkit.getScheduler()
                        .runTask(
                                plugin,
                                () -> MessageUtil.send(player, "<red>Inspection failed: " + error.getMessage()));
                return;
            }
            String title = entity.getType().name() + " @ " + location.getBlockX() + ", " + location.getBlockY() + ", "
                    + location.getBlockZ();
            Bukkit.getScheduler().runTask(plugin, () -> sendInspection(player, title, location, events));
        });
    }

    /**
     * Reports an inspection failure to the player.
     *
     * @param player the inspecting player
     * @param error the failure cause
     */
    private void reportFailure(@NotNull Player player, @NotNull Throwable error) {
        Bukkit.getScheduler()
                .runTask(plugin, () -> MessageUtil.send(player, "<red>Inspection failed: " + error.getMessage()));
    }

    /**
     * Sends the audit results of a click to the player.
     *
     * @param player the inspecting player
     * @param title the header describing what was inspected
     * @param location the inspected location
     * @param events the audit history
     */
    private void sendInspection(
            @NotNull Player player,
            @NotNull String title,
            @NotNull Location location,
            @NotNull List<AuditEvent> events) {
        MessageUtil.send(player, "<yellow>=== " + title + " ===");
        if (events.isEmpty()) {
            MessageUtil.send(player, "<gray>No player records in this area");
            return;
        }
        boolean shown = false;
        for (AuditEvent event : events) {
            String summary = dev.sentinel.audit.util.AuditFormatter.playerBlockSummary(event);
            if (summary != null) {
                MessageUtil.send(
                        player,
                        "<dark_gray>" + dev.sentinel.audit.util.AuditFormatter.time(event) + " <white>-</white> "
                                + summary);
                shown = true;
            }
        }
        if (!shown) {
            MessageUtil.send(player, "<gray>No player records in this area");
        }
    }
}
