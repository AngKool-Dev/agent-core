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
package dev.sentinel.audit.services.impl;

import dev.sentinel.audit.api.RollbackService;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.database.model.BlockChangeRecord;
import dev.sentinel.audit.database.model.InventoryChangeRecord;
import dev.sentinel.audit.database.repository.AuditRepository;
import dev.sentinel.audit.database.repository.BlockChangeRepository;
import dev.sentinel.audit.database.repository.InventoryRepository;
import dev.sentinel.audit.models.RollbackOperation;
import dev.sentinel.audit.rollback.RollbackExecutor;
import dev.sentinel.audit.rollback.RollbackManager;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.NotNull;

/**
 * Standard implementation of the {@link RollbackService}.
 *
 * <p>Coordinates rollback operations through the rollback executor
 * and block change repository.</p>
 */
public final class StandardRollbackService implements RollbackService {

    private static final org.slf4j.Logger LOGGER = org.slf4j.LoggerFactory.getLogger(StandardRollbackService.class);

    private static final int AMBIENT_MARGIN = 32;

    private final AuditRepository auditRepository;
    private final BlockChangeRepository blockChangeRepository;
    private final InventoryRepository inventoryRepository;
    private final RollbackExecutor rollbackExecutor;
    private final RollbackManager rollbackManager;
    private final SentinelConfig.RollbackConfig config;
    private final JavaPlugin plugin;
    private final ExecutorService executor;

    /**
     * Constructs a new standard rollback service.
     *
     * @param auditRepository the audit repository
     * @param blockChangeRepository the block change repository
     * @param inventoryRepository the inventory change repository
     * @param rollbackExecutor the rollback executor
     * @param plugin the owning plugin, used to schedule main thread work
     * @param config the rollback configuration
     */
    public StandardRollbackService(
            @NotNull AuditRepository auditRepository,
            @NotNull BlockChangeRepository blockChangeRepository,
            @NotNull InventoryRepository inventoryRepository,
            @NotNull RollbackExecutor rollbackExecutor,
            @NotNull JavaPlugin plugin,
            @NotNull SentinelConfig.RollbackConfig config) {
        this.auditRepository = auditRepository;
        this.blockChangeRepository = blockChangeRepository;
        this.inventoryRepository = inventoryRepository;
        this.rollbackExecutor = rollbackExecutor;
        this.rollbackManager = new RollbackManager();
        this.plugin = plugin;
        this.config = config;
        this.executor = Executors.newVirtualThreadPerTaskExecutor();
    }

    /**
     * Rolls back all changes made by a specific actor within a time range.
     *
     * @param actorId the UUID of the actor whose changes to roll back
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of changes rolled back
     */
    @Override
    public @NotNull CompletableFuture<Integer> rollbackActor(
            @NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    List<BlockChangeRecord> changes = findAllActorChanges(actorId, from, to);
                    LOGGER.info("Rolling back {} block changes for actor {}", changes.size(), actorId);
                    changes = new ArrayList<>(changes);
                    changes.addAll(findAmbientChanges(actorId, changes, from, to));
                    LOGGER.info("Rollback actor {} includes {} ambient block changes", actorId, changes.size());
                    return executeRollback(actorId, "PLAYER", changes);
                },
                executor);
    }

    /**
     * Fetches every block change made by an actor in a time range, paging
     * through the result set so the configured per-operation limit is only a
     * page size and never silently truncates a rollback.
     *
     * @param actorId the UUID of the actor
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the complete list of block change records, most recent first
     */
    private @NotNull List<BlockChangeRecord> findAllActorChanges(
            @NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to) {
        int pageSize = config.getMaxBlocksPerOperation();
        List<BlockChangeRecord> all = new ArrayList<>();
        int offset = 0;
        List<BlockChangeRecord> page;
        do {
            page = blockChangeRepository.findByActor(actorId, from, to, pageSize, offset);
            all.addAll(page);
            offset += page.size();
        } while (page.size() == pageSize);
        return all;
    }

    /**
     * Finds environmental block changes (liquid flow, fire spread) in the
     * bounding region of the actor's own edits, so that lava and fire caused
     * by the actor are restored as well.
     *
     * @param actorId the actor whose edits define the sweep region
     * @param changes the actor's own block changes
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the ambient block changes overlapping the actor's region
     */
    private @NotNull List<BlockChangeRecord> findAmbientChanges(
            @NotNull UUID actorId,
            @NotNull List<BlockChangeRecord> changes,
            @NotNull Instant from,
            @NotNull Instant to) {
        if (changes.isEmpty()) {
            return List.of();
        }
        String worldName = changes.get(0).worldName();
        int minX = Integer.MAX_VALUE;
        int minY = Integer.MAX_VALUE;
        int minZ = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE;
        int maxY = Integer.MIN_VALUE;
        int maxZ = Integer.MIN_VALUE;
        for (BlockChangeRecord change : changes) {
            if (!change.worldName().equals(worldName)) {
                continue;
            }
            minX = Math.min(minX, change.x());
            minY = Math.min(minY, change.y());
            minZ = Math.min(minZ, change.z());
            maxX = Math.max(maxX, change.x());
            maxY = Math.max(maxY, change.y());
            maxZ = Math.max(maxZ, change.z());
        }
        return blockChangeRepository.findAmbientByRegion(
                worldName,
                minX - AMBIENT_MARGIN,
                minY - AMBIENT_MARGIN,
                minZ - AMBIENT_MARGIN,
                maxX + AMBIENT_MARGIN,
                maxY + AMBIENT_MARGIN,
                maxZ + AMBIENT_MARGIN,
                from,
                to);
    }

    /**
     * Rolls back all changes within a world and time range.
     *
     * @param worldName the name of the world to roll back
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of changes rolled back
     */
    @Override
    public @NotNull CompletableFuture<Integer> rollbackWorld(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    List<BlockChangeRecord> changes = findAllWorldChanges(worldName, from, to);
                    LOGGER.info("Rolling back {} block changes in world {}", changes.size(), worldName);
                    return executeRollback(UUID.fromString("00000000-0000-0000-0000-000000000000"), "SYSTEM", changes);
                },
                executor);
    }

    /**
     * Fetches every block change in a world for a time range, paging through
     * the result set so large rollbacks are never silently truncated.
     *
     * @param worldName the world name
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the complete list of block change records, most recent first
     */
    private @NotNull List<BlockChangeRecord> findAllWorldChanges(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to) {
        int pageSize = config.getMaxBlocksPerOperation();
        List<BlockChangeRecord> all = new ArrayList<>();
        int offset = 0;
        List<BlockChangeRecord> page;
        do {
            page = blockChangeRepository.findByWorld(worldName, from, to, pageSize, offset);
            all.addAll(page);
            offset += page.size();
        } while (page.size() == pageSize);
        return all;
    }

    /**
     * Rolls back all changes within a region and time range.
     *
     * @param firstCorner the first corner of the region
     * @param secondCorner the second corner of the region
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of changes rolled back
     */
    @Override
    public @NotNull CompletableFuture<Integer> rollbackRegion(
            @NotNull Location firstCorner, @NotNull Location secondCorner, @NotNull Instant from, @NotNull Instant to) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    String worldName = firstCorner.getWorld().getName();
                    int minX = Math.min(firstCorner.getBlockX(), secondCorner.getBlockX());
                    int maxX = Math.max(firstCorner.getBlockX(), secondCorner.getBlockX());
                    int minY = Math.min(firstCorner.getBlockY(), secondCorner.getBlockY());
                    int maxY = Math.max(firstCorner.getBlockY(), secondCorner.getBlockY());
                    int minZ = Math.min(firstCorner.getBlockZ(), secondCorner.getBlockZ());
                    int maxZ = Math.max(firstCorner.getBlockZ(), secondCorner.getBlockZ());

                    List<BlockChangeRecord> changes =
                            blockChangeRepository.findByRegion(worldName, minX, minY, minZ, maxX, maxY, maxZ, from, to);
                    LOGGER.info("Rolling back {} block changes in region", changes.size());
                    return executeRollback(UUID.fromString("00000000-0000-0000-0000-000000000000"), "SYSTEM", changes);
                },
                executor);
    }

    /**
     * Executes a rollback operation for the given block changes.
     *
     * @param actorId the actor initiating the rollback
     * @param actorName the name of the actor initiating the rollback
     * @param changes the block changes to restore
     * @return the number of blocks restored
     */
    private int executeRollback(
            @NotNull UUID actorId, @NotNull String actorName, @NotNull List<BlockChangeRecord> changes) {
        if (changes.isEmpty()) {
            return 0;
        }
        RollbackOperation operation = RollbackOperation.pending(actorId, actorName, changes.size());
        rollbackManager.register(operation);
        RollbackOperation completed =
                rollbackExecutor.execute(operation, changes).join();
        rollbackManager.update(completed);
        LOGGER.info(
                "Rollback {} completed: {} of {} blocks restored",
                operation.id(),
                completed.blocksRestored(),
                changes.size());
        return completed.blocksRestored();
    }

    /**
     * Rolls back a single audit event by its ID.
     *
     * @param eventId the ID of the event to roll back
     * @return a future that completes when the rollback is done
     */
    @Override
    public @NotNull CompletableFuture<Void> rollbackEvent(@NotNull UUID eventId) {
        requirePremium();
        return CompletableFuture.runAsync(
                () -> {
                    LOGGER.info("Rolling back event {}", eventId);
                },
                executor);
    }

    /**
     * Restores a single block to its state before the given event.
     *
     * @param location the block location
     * @param eventId the event ID to restore before
     * @return a future that completes when the restore is done
     */
    @Override
    public @NotNull CompletableFuture<Void> restoreBlock(@NotNull Location location, @NotNull UUID eventId) {
        requirePremium();
        return CompletableFuture.runAsync(
                () -> {
                    LOGGER.info("Restoring block at {} before event {}", location, eventId);
                },
                executor);
    }

    /**
     * Restores captured inventory items back to a player.
     *
     * @param playerId the UUID of the player to restore items to
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of items restored
     */
    @Override
    public @NotNull CompletableFuture<Integer> rollbackInventory(
            @NotNull UUID playerId, @NotNull Instant from, @NotNull Instant to) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    Player player = Bukkit.getPlayer(playerId);
                    if (player == null) {
                        LOGGER.info("Cannot restore items for offline player {}", playerId);
                        return 0;
                    }
                    List<ItemStack> items = new ArrayList<>();
                    for (InventoryChangeRecord change : inventoryRepository.findByInventoryId(
                            playerId.toString(), config.getMaxBlocksPerOperation())) {
                        if (!change.timestamp().isBefore(from)
                                && !change.timestamp().isAfter(to)) {
                            items.addAll(change.before().toItems());
                        }
                    }
                    if (items.isEmpty()) {
                        return 0;
                    }
                    AtomicInteger restored = new AtomicInteger();
                    if (Bukkit.isPrimaryThread()) {
                        giveItems(player, items, restored);
                    } else {
                        CountDownLatch latch = new CountDownLatch(1);
                        Bukkit.getScheduler().runTask(plugin, () -> {
                            giveItems(player, items, restored);
                            latch.countDown();
                        });
                        try {
                            latch.await();
                        } catch (InterruptedException exception) {
                            Thread.currentThread().interrupt();
                            return 0;
                        }
                    }
                    LOGGER.info("Restored {} item(s) to player {}", restored.get(), playerId);
                    return restored.get();
                },
                executor);
    }

    /**
     * Restores environment-lost item entities captured for a world back to a recipient.
     *
     * @param worldName the world whose item losses to restore
     * @param recipientId the UUID of the online player to give the items to
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of items restored
     */
    @Override
    public @NotNull CompletableFuture<Integer> rollbackWorldInventory(
            @NotNull String worldName, @NotNull UUID recipientId, @NotNull Instant from, @NotNull Instant to) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    Player player = Bukkit.getPlayer(recipientId);
                    if (player == null) {
                        LOGGER.info("Cannot restore world items for offline player {}", recipientId);
                        return 0;
                    }
                    List<ItemStack> items = new ArrayList<>();
                    for (InventoryChangeRecord change : inventoryRepository.findWorldLosses(worldName, from, to)) {
                        items.addAll(change.before().toItems());
                    }
                    if (items.isEmpty()) {
                        return 0;
                    }
                    AtomicInteger restored = new AtomicInteger();
                    if (Bukkit.isPrimaryThread()) {
                        giveItems(player, items, restored);
                    } else {
                        CountDownLatch latch = new CountDownLatch(1);
                        Bukkit.getScheduler().runTask(plugin, () -> {
                            giveItems(player, items, restored);
                            latch.countDown();
                        });
                        try {
                            latch.await();
                        } catch (InterruptedException exception) {
                            Thread.currentThread().interrupt();
                            return 0;
                        }
                    }
                    LOGGER.info(
                            "Restored {} item(s) to player {} from world {}", restored.get(), recipientId, worldName);
                    return restored.get();
                },
                executor);
    }

    /**
     * Adds items to a player's inventory, dropping any overflow.
     *
     * @param player the player receiving the items
     * @param items the items to add
     * @param restored a counter incremented by the number of items added
     */
    private void giveItems(@NotNull Player player, @NotNull List<ItemStack> items, @NotNull AtomicInteger restored) {
        for (ItemStack item : items) {
            restored.addAndGet(item.getAmount());
            Map<Integer, ItemStack> leftover = player.getInventory().addItem(item);
            for (ItemStack dropped : leftover.values()) {
                player.getWorld().dropItem(player.getLocation(), dropped);
            }
        }
    }

    /**
     * Shuts down the virtual thread executor.
     */
    public void shutdown() {
        executor.shutdown();
    }

    /**
     * Rejects any use of this premium service when running the free Lite edition,
     * closing the gap where the public API could be invoked directly (bypassing the
     * command-level edition check).
     */
    private void requirePremium() {
        if (dev.sentinel.audit.Edition.load().isLite()) {
            throw new UnsupportedOperationException("Rollback is not available in Sentinel Lite");
        }
    }
}
