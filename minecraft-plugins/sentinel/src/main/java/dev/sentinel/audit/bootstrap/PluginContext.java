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
package dev.sentinel.audit.bootstrap;

import dev.sentinel.audit.api.AuditService;
import dev.sentinel.audit.api.InspectionService;
import dev.sentinel.audit.api.RollbackService;
import dev.sentinel.audit.cache.AuditCache;
import dev.sentinel.audit.cache.InspectionCache;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.database.DatabaseManager;
import dev.sentinel.audit.inspector.InspectionMode;
import dev.sentinel.audit.scheduler.PurgeScheduler;
import dev.sentinel.audit.scheduler.SnapshotScheduler;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * Central dependency container for the Sentinel plugin.
 *
 * <p>Provides access to all plugin services and components, ensuring
 * a single source of truth for dependency wiring.</p>
 */
public final class PluginContext {

    private final JavaPlugin plugin;
    private final SentinelConfig config;
    private final DatabaseManager databaseManager;
    private final AuditCache auditCache;
    private final InspectionCache inspectionCache;
    private final InspectionMode inspectionMode;
    private final AuditService auditService;
    private final InspectionService inspectionService;
    private final RollbackService rollbackService;
    private final PurgeScheduler purgeScheduler;
    private final SnapshotScheduler snapshotScheduler;

    /**
     * Constructs a new plugin context with all dependencies.
     *
     * @param plugin the owning plugin instance
     * @param config the plugin configuration
     * @param databaseManager the database manager
     * @param auditCache the audit cache
     * @param inspectionCache the inspection cache
     * @param inspectionMode the inspection mode tracker
     * @param auditService the audit service
     * @param inspectionService the inspection service
     * @param rollbackService the rollback service
     * @param purgeScheduler the purge scheduler
     * @param snapshotScheduler the snapshot scheduler
     */
    public PluginContext(
            JavaPlugin plugin,
            SentinelConfig config,
            DatabaseManager databaseManager,
            AuditCache auditCache,
            InspectionCache inspectionCache,
            InspectionMode inspectionMode,
            AuditService auditService,
            InspectionService inspectionService,
            RollbackService rollbackService,
            PurgeScheduler purgeScheduler,
            SnapshotScheduler snapshotScheduler) {
        this.plugin = plugin;
        this.config = config;
        this.databaseManager = databaseManager;
        this.auditCache = auditCache;
        this.inspectionCache = inspectionCache;
        this.inspectionMode = inspectionMode;
        this.auditService = auditService;
        this.inspectionService = inspectionService;
        this.rollbackService = rollbackService;
        this.purgeScheduler = purgeScheduler;
        this.snapshotScheduler = snapshotScheduler;
    }

    /**
     * Gets the owning plugin instance.
     *
     * @return the plugin
     */
    public JavaPlugin getPlugin() {
        return plugin;
    }

    /**
     * Gets the plugin configuration.
     *
     * @return the configuration
     */
    public SentinelConfig getConfig() {
        return config;
    }

    /**
     * Gets the database manager.
     *
     * @return the database manager
     */
    public DatabaseManager getDatabaseManager() {
        return databaseManager;
    }

    /**
     * Gets the audit cache.
     *
     * @return the audit cache
     */
    public AuditCache getAuditCache() {
        return auditCache;
    }

    /**
     * Gets the inspection cache.
     *
     * @return the inspection cache
     */
    public InspectionCache getInspectionCache() {
        return inspectionCache;
    }

    /**
     * Gets the inspection mode tracker.
     *
     * @return the inspection mode tracker
     */
    public InspectionMode getInspectionMode() {
        return inspectionMode;
    }

    /**
     * Gets the audit service.
     *
     * @return the audit service
     */
    public AuditService getAuditService() {
        return auditService;
    }

    /**
     * Gets the inspection service.
     *
     * @return the inspection service
     */
    public InspectionService getInspectionService() {
        return inspectionService;
    }

    /**
     * Gets the rollback service.
     *
     * @return the rollback service
     */
    public RollbackService getRollbackService() {
        return rollbackService;
    }

    /**
     * Gets the purge scheduler.
     *
     * @return the purge scheduler
     */
    public PurgeScheduler getPurgeScheduler() {
        return purgeScheduler;
    }

    /**
     * Gets the snapshot scheduler.
     *
     * @return the snapshot scheduler
     */
    public SnapshotScheduler getSnapshotScheduler() {
        return snapshotScheduler;
    }
}
