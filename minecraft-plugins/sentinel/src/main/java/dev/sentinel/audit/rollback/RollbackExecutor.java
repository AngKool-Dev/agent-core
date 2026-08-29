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
package dev.sentinel.audit.rollback;

import dev.sentinel.audit.database.model.BlockChangeRecord;
import dev.sentinel.audit.models.RollbackOperation;
import dev.sentinel.audit.models.RollbackStatus;
import dev.sentinel.audit.util.TileEntityUtil;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Executes rollback operations on the game world.
 *
 * <p>Restores block states from block change records, applying all
 * block modifications on the main server thread for safety.</p>
 */
public final class RollbackExecutor {

    private static final Logger LOGGER = LoggerFactory.getLogger(RollbackExecutor.class);

    private static final int APPLY_SLICE = 2000;

    private final JavaPlugin plugin;
    private final ExecutorService executor;

    /**
     * Constructs a new rollback executor.
     *
     * @param plugin the owning plugin, used to schedule main thread work
     */
    public RollbackExecutor(@NotNull JavaPlugin plugin) {
        this.plugin = plugin;
        this.executor = Executors.newVirtualThreadPerTaskExecutor();
    }

    /**
     * Executes a rollback operation for the given block changes.
     *
     * <p>Changes are de-duplicated per block cell, keeping the oldest recorded
     * state for each cell so that a block is restored exactly once to the
     * state it had before the audited activity began.</p>
     *
     * @param operation the rollback operation
     * @param changes the block changes to apply
     * @return a future that completes when the rollback is done
     */
    public CompletableFuture<RollbackOperation> execute(
            @NotNull RollbackOperation operation, @NotNull List<BlockChangeRecord> changes) {
        return CompletableFuture.supplyAsync(
                () -> {
                    RollbackOperation running = operation.withStatus(RollbackStatus.RUNNING);
                    Map<Cell, BlockChangeRecord> oldestByCell = deduplicate(changes);
                    if (oldestByCell.isEmpty()) {
                        return running.withProgress(0).completed();
                    }
                    if (Bukkit.isPrimaryThread()) {
                        return applyAll(running, oldestByCell);
                    }
                    List<Map.Entry<Cell, BlockChangeRecord>> entries = new java.util.ArrayList<>(oldestByCell.entrySet());
                    CountDownLatch latch = new CountDownLatch(1);
                    AtomicInteger restored = new AtomicInteger();
                    AtomicReference<RollbackOperation> result = new AtomicReference<>();
                    scheduleSlice(running, entries, 0, restored, result, latch);
                    try {
                        latch.await();
                    } catch (InterruptedException exception) {
                        Thread.currentThread().interrupt();
                        return running.withProgress(restored.get()).failed();
                    }
                    return result.get();
                },
                executor);
    }

    /**
     * Schedules a slice of the restoration on the main thread, chaining the
     * next slice so a large rollback spreads its work over several ticks
     * instead of freezing the server.
     *
     * @param running the running operation
     * @param entries the restorations left to apply
     * @param start the index of the first entry in this slice
     * @param restored a counter of successfully restored blocks
     * @param result the completion holder
     * @param latch the latch released when the last slice finishes
     */
    private void scheduleSlice(
            @NotNull RollbackOperation running,
            @NotNull List<Map.Entry<Cell, BlockChangeRecord>> entries,
            int start,
            @NotNull AtomicInteger restored,
            @NotNull AtomicReference<RollbackOperation> result,
            @NotNull CountDownLatch latch) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            int end = Math.min(start + APPLY_SLICE, entries.size());
            for (int i = start; i < end; i++) {
                if (applyRestore(entries.get(i).getValue())) {
                    restored.incrementAndGet();
                }
            }
            if (end < entries.size()) {
                scheduleSlice(running, entries, end, restored, result, latch);
            } else {
                result.set(running.withProgress(restored.get()).completed());
                latch.countDown();
            }
        });
    }

    /**
     * Keeps only the earliest recorded state for each block cell.
     *
     * @param changes the raw block changes
     * @return a map from cell to earliest change
     */
    private @NotNull Map<Cell, BlockChangeRecord> deduplicate(@NotNull List<BlockChangeRecord> changes) {
        Map<Cell, BlockChangeRecord> oldest = new LinkedHashMap<>();
        for (BlockChangeRecord change : changes) {
            Cell cell = new Cell(change.worldName(), change.x(), change.y(), change.z());
            BlockChangeRecord existing = oldest.get(cell);
            if (existing == null || change.timestamp().isBefore(existing.timestamp())) {
                oldest.put(cell, change);
            }
        }
        return oldest;
    }

    /**
     * Applies the de-duplicated restorations on the current thread.
     *
     * @param operation the running operation
     * @param restorations the cell-to-change mapping to apply
     * @return the updated operation
     */
    private @NotNull RollbackOperation applyAll(
            @NotNull RollbackOperation operation, @NotNull Map<Cell, BlockChangeRecord> restorations) {
        int restored = 0;
        for (Map.Entry<Cell, BlockChangeRecord> entry : restorations.entrySet()) {
            if (applyRestore(entry.getValue())) {
                restored++;
            }
        }
        return operation.withProgress(restored).completed();
    }

    /**
     * Applies a block restoration to its before state.
     *
     * @param change the block change record
     * @return true if the block was restored
     */
    private boolean applyRestore(@NotNull BlockChangeRecord change) {
        try {
            World world = Bukkit.getWorld(change.worldName());
            if (world == null) {
                LOGGER.warn("Cannot restore block in unloaded world: {}", change.worldName());
                return false;
            }
            Block block = world.getBlockAt(change.x(), change.y(), change.z());
            BlockData beforeData = Bukkit.createBlockData(change.before().blockData());
            block.setBlockData(beforeData, false);
            TileEntityUtil.restore(block, change.before().tileEntityData());
            return true;
        } catch (RuntimeException exception) {
            LOGGER.warn(
                    "Failed to restore block at {} {} {}: {}", change.x(), change.y(), change.z(), exception.getMessage());
            return false;
        }
    }

    /**
     * Shuts down the executor.
     */
    public void shutdown() {
        executor.shutdown();
    }

    /**
     * Identifies a block cell by world and coordinates.
     */
    private record Cell(String worldName, int x, int y, int z) {}
}
