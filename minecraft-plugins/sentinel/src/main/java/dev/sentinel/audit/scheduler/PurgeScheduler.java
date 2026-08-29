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

import dev.sentinel.audit.api.AuditService;
import dev.sentinel.audit.config.SentinelConfig;
import java.time.Instant;
import java.util.concurrent.TimeUnit;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Scheduled task that purges old audit records.
 *
 * <p>Periodically deletes audit records older than the configured
 * retention period to keep the database size manageable.</p>
 */
public final class PurgeScheduler {

    private static final Logger LOGGER = LoggerFactory.getLogger(PurgeScheduler.class);

    private final JavaPlugin plugin;
    private final AuditService auditService;
    private final SentinelConfig.SchedulerConfig config;
    private int taskId = -1;

    /**
     * Constructs a new purge scheduler.
     *
     * @param plugin the owning plugin
     * @param auditService the audit service
     * @param config the scheduler configuration
     */
    public PurgeScheduler(
            @NotNull JavaPlugin plugin,
            @NotNull AuditService auditService,
            @NotNull SentinelConfig.SchedulerConfig config) {
        this.plugin = plugin;
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Starts the scheduled purge task.
     */
    public void start() {
        if (!config.isPurgeEnabled()) {
            LOGGER.info("Purge scheduler is disabled.");
            return;
        }
        long intervalTicks = TimeUnit.HOURS.toSeconds(config.getPurgeIntervalHours()) * 20;
        var task = plugin.getServer()
                .getScheduler()
                .runTaskTimerAsynchronously(plugin, this::runPurge, intervalTicks * 20, intervalTicks * 20);
        taskId = task.getTaskId();
        LOGGER.info(
                "Purge scheduler started: interval={}h, retention={}d",
                config.getPurgeIntervalHours(),
                config.getPurgeOlderThanDays());
    }

    /**
     * Stops the scheduled purge task.
     */
    public void stop() {
        if (taskId != -1) {
            plugin.getServer().getScheduler().cancelTask(taskId);
            taskId = -1;
        }
    }

    /**
     * Runs a single purge cycle.
     */
    private void runPurge() {
        Instant cutoff = Instant.now().minus(java.time.Duration.ofDays(config.getPurgeOlderThanDays()));
        auditService
                .purgeBefore(cutoff)
                .thenAccept(count -> LOGGER.info("Purged {} audit records older than {}", count, cutoff))
                .exceptionally(throwable -> {
                    LOGGER.error("Failed to purge audit records", throwable);
                    return null;
                });
    }
}
