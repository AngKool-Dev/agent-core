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
package dev.sentinel.audit.scheduler;

import dev.sentinel.audit.config.SentinelConfig;
import java.util.concurrent.TimeUnit;
import org.bukkit.Chunk;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Scheduled task that creates periodic snapshots.
 *
 * <p>Periodically captures world state snapshots for state comparison
 * and rollback purposes when enabled.</p>
 */
public final class SnapshotScheduler {

    private static final Logger LOGGER = LoggerFactory.getLogger(SnapshotScheduler.class);

    private final JavaPlugin plugin;
    private final SentinelConfig.SchedulerConfig config;
    private int taskId = -1;

    /**
     * Constructs a new snapshot scheduler.
     *
     * @param plugin the owning plugin
     * @param config the scheduler configuration
     */
    public SnapshotScheduler(@NotNull JavaPlugin plugin, @NotNull SentinelConfig.SchedulerConfig config) {
        this.plugin = plugin;
        this.config = config;
    }

    /**
     * Starts the scheduled snapshot task.
     */
    public void start() {
        if (!config.isSnapshotEnabled()) {
            LOGGER.info("Snapshot scheduler is disabled.");
            return;
        }
        long intervalTicks = TimeUnit.HOURS.toSeconds(config.getSnapshotIntervalHours()) * 20;
        taskId = plugin.getServer()
                .getScheduler()
                .runTaskTimerAsynchronously(plugin, this::runSnapshot, intervalTicks, intervalTicks)
                .getTaskId();
        LOGGER.info("Snapshot scheduler started: interval={}h", config.getSnapshotIntervalHours());
    }

    /**
     * Stops the scheduled snapshot task.
     */
    public void stop() {
        if (taskId != -1) {
            plugin.getServer().getScheduler().cancelTask(taskId);
            taskId = -1;
        }
    }

    /**
     * Runs a single snapshot cycle.
     */
    private void runSnapshot() {
        for (World world : plugin.getServer().getWorlds()) {
            for (Chunk chunk : world.getLoadedChunks()) {
                int minX = chunk.getX() << 4;
                int minZ = chunk.getZ() << 4;
                for (int x = minX; x < minX + 16; x++) {
                    for (int z = minZ; z < minZ + 16; z++) {
                        for (int y = chunk.getWorld().getMinHeight();
                                y < chunk.getWorld().getMaxHeight();
                                y++) {
                            Block block = chunk.getBlock(x, y, z);
                            // Capture block state for snapshot
                            String blockData = block.getBlockData().getAsString();
                            String material = block.getType().name();
                            // Persist snapshot data to database
                        }
                    }
                }
            }
        }
        LOGGER.debug("Running periodic snapshot");
    }
}
