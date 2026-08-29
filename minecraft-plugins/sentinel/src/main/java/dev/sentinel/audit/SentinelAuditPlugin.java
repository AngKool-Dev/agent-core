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
package dev.sentinel.audit;

import dev.sentinel.audit.api.AuditService;
import dev.sentinel.audit.api.InspectionService;
import dev.sentinel.audit.api.RollbackService;
import dev.sentinel.audit.bootstrap.PluginContext;
import dev.sentinel.audit.cache.AuditCache;
import dev.sentinel.audit.cache.InspectionCache;
import dev.sentinel.audit.commands.SentinelCommand;
import dev.sentinel.audit.config.ConfigLoader;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.database.DatabaseManager;
import dev.sentinel.audit.database.repository.AuditRepository;
import dev.sentinel.audit.database.repository.BlockChangeRepository;
import dev.sentinel.audit.database.repository.InventoryRepository;
import dev.sentinel.audit.database.repository.JdbcAuditRepository;
import dev.sentinel.audit.database.repository.JdbcBlockChangeRepository;
import dev.sentinel.audit.database.repository.JdbcInventoryRepository;
import dev.sentinel.audit.inspector.InspectionMode;
import dev.sentinel.audit.license.LicenseManager;
import dev.sentinel.audit.license.LicenseProperties;
import dev.sentinel.audit.listeners.BlockListener;
import dev.sentinel.audit.listeners.EntityListener;
import dev.sentinel.audit.listeners.EnvironmentListener;
import dev.sentinel.audit.listeners.InspectListener;
import dev.sentinel.audit.listeners.InventoryListener;
import dev.sentinel.audit.listeners.ItemLossListener;
import dev.sentinel.audit.listeners.PlayerListener;
import dev.sentinel.audit.rollback.RollbackExecutor;
import dev.sentinel.audit.scheduler.PurgeScheduler;
import dev.sentinel.audit.scheduler.SnapshotScheduler;
import dev.sentinel.audit.services.impl.StandardAuditService;
import dev.sentinel.audit.services.impl.StandardInspectionService;
import dev.sentinel.audit.services.impl.StandardRollbackService;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.PluginManager;
import org.bukkit.plugin.java.JavaPlugin;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Main plugin bootstrap for Sentinel Audit.
 *
 * <p>Responsible for loading configuration, wiring all dependencies,
 * registering listeners and commands, and managing graceful shutdown.</p>
 */
public final class SentinelAuditPlugin extends JavaPlugin {

    private static final Logger LOGGER = LoggerFactory.getLogger(SentinelAuditPlugin.class);

    private ConfigLoader configLoader;
    private SentinelConfig config;
    private LicenseManager licenseManager;
    private DatabaseManager databaseManager;
    private AuditRepository auditRepository;
    private BlockChangeRepository blockChangeRepository;
    private InventoryRepository inventoryRepository;
    private AuditCache auditCache;
    private InspectionCache inspectionCache;
    private InspectionMode inspectionMode;
    private RollbackExecutor rollbackExecutor;
    private AuditService auditService;
    private InspectionService inspectionService;
    private RollbackService rollbackService;
    private PurgeScheduler purgeScheduler;
    private SnapshotScheduler snapshotScheduler;

    /**
     * Invoked when the plugin is loaded.
     *
     * <p>Initializes the configuration loader so that configuration is
     * available before listeners are registered.</p>
     */
    @Override
    public void onLoad() {
        this.configLoader = new ConfigLoader(this);
        configLoader.load();
        this.config = configLoader.getConfig();
        LOGGER.info("Sentinel Audit configuration loaded.");
    }

    /**
     * Invoked when the plugin is enabled.
     *
     * <p>Initializes the database, repositories, caches, services, and
     * schedulers, then registers listeners and commands.</p>
     */
    @Override
    public void onEnable() {
        long startTime = System.nanoTime();
        LOGGER.info("Sentinel Audit is initializing...");

        try {
            LicenseManager manager = new LicenseManager(this, LicenseProperties.load(), config.getLicense());
            this.licenseManager = manager;
            if (!manager.start()) {
                getServer().getPluginManager().disablePlugin(this);
                return;
            }

            initializeDatabase();
            initializeServices();
            startSchedulers();
            registerListeners();
            registerCommands();
            LOGGER.info("Sentinel Audit enabled in {} ms", (System.nanoTime() - startTime) / 1_000_000);
        } catch (Exception exception) {
            LOGGER.error("Failed to enable Sentinel Audit", exception);
            getServer().getPluginManager().disablePlugin(this);
        }
    }

    /**
     * Invoked when the plugin is disabled.
     *
     * <p>Stops schedulers, flushes pending writes, clears caches, shuts
     * down executors and closes the database connection pool.</p>
     */
    @Override
    public void onDisable() {
        LOGGER.info("Sentinel Audit is shutting down...");
        shutdownComponents();
        LOGGER.info("Sentinel Audit disabled.");
    }

    /**
     * Initializes the database connection pool and migrations.
     *
     * @throws Exception if database initialization fails
     */
    private void initializeDatabase() throws Exception {
        this.databaseManager =
                new DatabaseManager(config.getDatabase(), getDataFolder().toPath());
        databaseManager.initialize();
        var dataSource = databaseManager.getDataSource();

        this.auditRepository = new JdbcAuditRepository(dataSource);
        this.blockChangeRepository = new JdbcBlockChangeRepository(dataSource);
        this.inventoryRepository = new JdbcInventoryRepository(dataSource);

        this.auditCache = new AuditCache(config.getCache().getMaxEntries());
        this.inspectionCache = new InspectionCache(config.getCache().getMaxEntries());
        this.inspectionMode = new InspectionMode();
    }

    /**
     * Initializes all services and wires their dependencies.
     */
    private void initializeServices() {
        this.rollbackExecutor = new RollbackExecutor(this);
        this.auditService = new StandardAuditService(
                auditRepository, blockChangeRepository, inventoryRepository, auditCache, config.getAudit());
        this.inspectionService =
                new StandardInspectionService(auditRepository, blockChangeRepository, inspectionCache, auditCache);
        this.rollbackService = new StandardRollbackService(
                auditRepository,
                blockChangeRepository,
                inventoryRepository,
                rollbackExecutor,
                this,
                config.getRollback());
    }

    /**
     * Starts all configured schedulers.
     */
    private void startSchedulers() {
        this.purgeScheduler = new PurgeScheduler(this, auditService, config.getScheduler());
        purgeScheduler.start();
        this.snapshotScheduler = new SnapshotScheduler(this, config.getScheduler());
        snapshotScheduler.start();
        startAuditFlush();
    }

    /**
     * Schedules the asynchronous flush of queued audit events so they are
     * persisted during runtime rather than only at batch-size or shutdown.
     */
    private void startAuditFlush() {
        long intervalMs = config.getAudit().getFlushIntervalMs();
        long intervalTicks = Math.max(1L, intervalMs / 50L);
        getServer()
                .getScheduler()
                .runTaskTimerAsynchronously(this, () -> auditService.flush(), intervalTicks, intervalTicks);
    }

    /**
     * Registers all event listeners with the plugin manager.
     */
    private void registerListeners() {
        PluginManager manager = getServer().getPluginManager();
        manager.registerEvents(new BlockListener(auditService, config), this);
        manager.registerEvents(new EnvironmentListener(auditService, config), this);
        manager.registerEvents(new EntityListener(auditService, config), this);
        manager.registerEvents(new InventoryListener(auditService, config), this);
        manager.registerEvents(new PlayerListener(auditService, config), this);
        if (!Edition.load().isLite()) {
            manager.registerEvents(new ItemLossListener(auditService, config), this);
            manager.registerEvents(new InspectListener(inspectionMode, inspectionService, this), this);
        }
    }

    /**
     * Registers the main plugin command.
     */
    private void registerCommands() {
        PluginContext context = new PluginContext(
                this,
                config,
                databaseManager,
                auditCache,
                inspectionCache,
                inspectionMode,
                auditService,
                inspectionService,
                rollbackService,
                purgeScheduler,
                snapshotScheduler);
        SentinelCommand sentinelCommand = new SentinelCommand(context);

        PluginCommand command = getCommand("sentinel");
        if (command == null) {
            throw new IllegalStateException("Command 'sentinel' missing from plugin.yml");
        }
        command.setExecutor(sentinelCommand);
        command.setTabCompleter(sentinelCommand);
    }

    /**
     * Shuts down all plugin components gracefully.
     */
    private void shutdownComponents() {
        if (licenseManager != null) {
            licenseManager.shutdown();
        }
        if (purgeScheduler != null) {
            purgeScheduler.stop();
        }
        if (snapshotScheduler != null) {
            snapshotScheduler.stop();
        }
        if (inspectionCache != null) {
            inspectionCache.clear();
        }
        if (inspectionMode != null) {
            inspectionMode.clear();
        }
        if (auditCache != null) {
            auditCache.clear();
        }
        if (rollbackService instanceof StandardRollbackService rollback) {
            rollback.shutdown();
        }
        if (rollbackExecutor != null) {
            rollbackExecutor.shutdown();
        }
        if (inspectionService instanceof StandardInspectionService inspection) {
            inspection.shutdown();
        }
        if (auditService instanceof StandardAuditService audit) {
            audit.shutdown();
        }
        if (databaseManager != null) {
            databaseManager.close();
        }
        LOGGER.info("All components shut down successfully.");
    }

    /**
     * Gets the loaded plugin configuration.
     *
     * @return the configuration
     */
    public SentinelConfig getSentinelConfig() {
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

    /**
     * Gets the license manager.
     *
     * @return the license manager
     */
    public LicenseManager getLicenseManager() {
        return licenseManager;
    }
}
