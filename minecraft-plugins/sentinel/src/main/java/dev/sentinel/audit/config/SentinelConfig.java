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
package dev.sentinel.audit.config;

import dev.sentinel.audit.models.DatabaseType;
import java.util.List;
import java.util.Set;
import org.bukkit.configuration.file.FileConfiguration;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable configuration holder for the Sentinel plugin.
 *
 * <p>Provides typed access to all plugin configuration values loaded
 * from the config.yml file.</p>
 */
public final class SentinelConfig {

    private final DatabaseConfig database;
    private final AuditConfig audit;
    private final CacheConfig cache;
    private final SchedulerConfig scheduler;
    private final RollbackConfig rollback;
    private final LicenseConfig license;
    private final List<String> disabledWorlds;
    private final Set<String> disabledActions;
    private final boolean debug;

    /**
     * Constructs a new configuration from a Bukkit configuration.
     *
     * @param config the Bukkit file configuration
     */
    public SentinelConfig(@NotNull FileConfiguration config) {
        this.database = new DatabaseConfig(config.getConfigurationSection("database"));
        this.audit = new AuditConfig(config.getConfigurationSection("audit"));
        this.cache = new CacheConfig(config.getConfigurationSection("cache"));
        this.scheduler = new SchedulerConfig(config.getConfigurationSection("scheduler"));
        this.rollback = new RollbackConfig(config.getConfigurationSection("rollback"));
        this.license = new LicenseConfig(config.getConfigurationSection("license"));
        this.disabledWorlds = config.getStringList("disabled-worlds");
        this.disabledActions = Set.copyOf(config.getStringList("disabled-actions"));
        this.debug = config.getBoolean("debug", false);
    }

    /**
     * Gets the database configuration.
     *
     * @return the database config
     */
    public DatabaseConfig getDatabase() {
        return database;
    }

    /**
     * Gets the audit configuration.
     *
     * @return the audit config
     */
    public AuditConfig getAudit() {
        return audit;
    }

    /**
     * Gets the cache configuration.
     *
     * @return the cache config
     */
    public CacheConfig getCache() {
        return cache;
    }

    /**
     * Gets the scheduler configuration.
     *
     * @return the scheduler config
     */
    public SchedulerConfig getScheduler() {
        return scheduler;
    }

    /**
     * Gets the rollback configuration.
     *
     * @return the rollback config
     */
    public RollbackConfig getRollback() {
        return rollback;
    }

    /**
     * Gets the license configuration.
     *
     * @return the license config
     */
    public LicenseConfig getLicense() {
        return license;
    }

    /**
     * Gets the list of worlds where auditing is disabled.
     *
     * @return the disabled worlds
     */
    public List<String> getDisabledWorlds() {
        return disabledWorlds;
    }

    /**
     * Gets the set of disabled audit actions.
     *
     * @return the disabled actions
     */
    public Set<String> getDisabledActions() {
        return disabledActions;
    }

    /**
     * Checks if debug mode is enabled.
     *
     * @return true if debug mode is enabled
     */
    public boolean isDebug() {
        return debug;
    }

    /**
     * Checks if auditing is enabled for the given world.
     *
     * @param worldName the world name
     * @return true if auditing is enabled
     */
    public boolean isWorldEnabled(@NotNull String worldName) {
        return !disabledWorlds.contains(worldName);
    }

    /**
     * Checks if the given action is enabled.
     *
     * @param actionName the action name
     * @return true if the action is enabled
     */
    public boolean isActionEnabled(@NotNull String actionName) {
        return !disabledActions.contains(actionName);
    }

    /**
     * Configuration for the database connection.
     */
    public static final class DatabaseConfig {

        private final DatabaseType type;
        private final String host;
        private final int port;
        private final String database;
        private final String username;
        private final String password;
        private final int poolSize;
        private final long connectionTimeoutMs;
        private final long maxLifetimeMs;

        /**
         * Constructs database config from a configuration section.
         *
         * @param section the configuration section
         */
        public DatabaseConfig(org.bukkit.configuration.ConfigurationSection section) {
            this.type = DatabaseType.valueOf(section.getString("type", "SQLITE").toUpperCase());
            this.host = section.getString("host", "localhost");
            this.port = section.getInt("port", 5432);
            this.database = section.getString("database", "sentinel");
            this.username = section.getString("username", "sentinel");
            this.password = section.getString("password", "");
            this.poolSize = section.getInt("pool-size", 10);
            this.connectionTimeoutMs = section.getLong("connection-timeout-ms", 30_000L);
            this.maxLifetimeMs = section.getLong("max-lifetime-ms", 1_800_000L);
        }

        /**
         * Gets the database type.
         *
         * @return the database type
         */
        public DatabaseType getType() {
            return type;
        }

        /**
         * Gets the database host.
         *
         * @return the host
         */
        public String getHost() {
            return host;
        }

        /**
         * Gets the database port.
         *
         * @return the port
         */
        public int getPort() {
            return port;
        }

        /**
         * Gets the database name.
         *
         * @return the database name
         */
        public String getDatabase() {
            return database;
        }

        /**
         * Gets the database username.
         *
         * @return the username
         */
        public String getUsername() {
            return username;
        }

        /**
         * Gets the database password.
         *
         * @return the password
         */
        public String getPassword() {
            return password;
        }

        /**
         * Gets the connection pool size.
         *
         * @return the pool size
         */
        public int getPoolSize() {
            return poolSize;
        }

        /**
         * Gets the connection timeout in milliseconds.
         *
         * @return the connection timeout
         */
        public long getConnectionTimeoutMs() {
            return connectionTimeoutMs;
        }

        /**
         * Gets the maximum connection lifetime in milliseconds.
         *
         * @return the max lifetime
         */
        public long getMaxLifetimeMs() {
            return maxLifetimeMs;
        }
    }

    /**
     * Configuration for audit logging behavior.
     */
    public static final class AuditConfig {

        private final boolean enabled;
        private final int batchSize;
        private final long flushIntervalMs;
        private final int maxQueueSize;
        private final boolean logInventory;
        private final boolean logChat;
        private final boolean logCommands;

        /**
         * Constructs audit config from a configuration section.
         *
         * @param section the configuration section
         */
        public AuditConfig(org.bukkit.configuration.ConfigurationSection section) {
            this.enabled = section.getBoolean("enabled", true);
            this.batchSize = section.getInt("batch-size", 100);
            this.flushIntervalMs = section.getLong("flush-interval-ms", 5_000L);
            this.maxQueueSize = section.getInt("max-queue-size", 10_000);
            this.logInventory = section.getBoolean("log-inventory", true);
            this.logChat = section.getBoolean("log-chat", true);
            this.logCommands = section.getBoolean("log-commands", true);
        }

        /**
         * Checks if auditing is enabled.
         *
         * @return true if enabled
         */
        public boolean isEnabled() {
            return enabled;
        }

        /**
         * Gets the batch size for database writes.
         *
         * @return the batch size
         */
        public int getBatchSize() {
            return batchSize;
        }

        /**
         * Gets the flush interval in milliseconds.
         *
         * @return the flush interval
         */
        public long getFlushIntervalMs() {
            return flushIntervalMs;
        }

        /**
         * Gets the maximum queue size.
         *
         * @return the max queue size
         */
        public int getMaxQueueSize() {
            return maxQueueSize;
        }

        /**
         * Checks if inventory events are logged.
         *
         * @return true if inventory logging is enabled
         */
        public boolean isLogInventory() {
            return logInventory;
        }

        /**
         * Checks if chat events are logged.
         *
         * @return true if chat logging is enabled
         */
        public boolean isLogChat() {
            return logChat;
        }

        /**
         * Checks if command events are logged.
         *
         * @return true if command logging is enabled
         */
        public boolean isLogCommands() {
            return logCommands;
        }
    }

    /**
     * Configuration for caching behavior.
     */
    public static final class CacheConfig {

        private final int maxEntries;
        private final long expireAfterWriteMinutes;
        private final long expireAfterAccessMinutes;
        private final boolean asyncPersistence;

        /**
         * Constructs cache config from a configuration section.
         *
         * @param section the configuration section
         */
        public CacheConfig(org.bukkit.configuration.ConfigurationSection section) {
            this.maxEntries = section.getInt("max-entries", 10_000);
            this.expireAfterWriteMinutes = section.getLong("expire-after-write-minutes", 30);
            this.expireAfterAccessMinutes = section.getLong("expire-after-access-minutes", 15);
            this.asyncPersistence = section.getBoolean("async-persistence", true);
        }

        /**
         * Gets the maximum number of cache entries.
         *
         * @return the max entries
         */
        public int getMaxEntries() {
            return maxEntries;
        }

        /**
         * Gets the expiration time after write in minutes.
         *
         * @return the expire after write
         */
        public long getExpireAfterWriteMinutes() {
            return expireAfterWriteMinutes;
        }

        /**
         * Gets the expiration time after access in minutes.
         *
         * @return the expire after access
         */
        public long getExpireAfterAccessMinutes() {
            return expireAfterAccessMinutes;
        }

        /**
         * Checks if async persistence is enabled.
         *
         * @return true if async persistence is enabled
         */
        public boolean isAsyncPersistence() {
            return asyncPersistence;
        }
    }

    /**
     * Configuration for scheduled tasks.
     */
    public static final class SchedulerConfig {

        private final boolean purgeEnabled;
        private final long purgeIntervalHours;
        private final long purgeOlderThanDays;
        private final boolean snapshotEnabled;
        private final long snapshotIntervalHours;

        /**
         * Constructs scheduler config from a configuration section.
         *
         * @param section the configuration section
         */
        public SchedulerConfig(org.bukkit.configuration.ConfigurationSection section) {
            this.purgeEnabled = section.getBoolean("purge.enabled", true);
            this.purgeIntervalHours = section.getLong("purge.interval-hours", 24);
            this.purgeOlderThanDays = section.getLong("purge.older-than-days", 30);
            this.snapshotEnabled = section.getBoolean("snapshot.enabled", false);
            this.snapshotIntervalHours = section.getLong("snapshot.interval-hours", 24);
        }

        /**
         * Checks if the purge scheduler is enabled.
         *
         * @return true if enabled
         */
        public boolean isPurgeEnabled() {
            return purgeEnabled;
        }

        /**
         * Gets the purge interval in hours.
         *
         * @return the purge interval
         */
        public long getPurgeIntervalHours() {
            return purgeIntervalHours;
        }

        /**
         * Gets how old records must be before purging, in days.
         *
         * @return the purge age threshold
         */
        public long getPurgeOlderThanDays() {
            return purgeOlderThanDays;
        }

        /**
         * Checks if the snapshot scheduler is enabled.
         *
         * @return true if enabled
         */
        public boolean isSnapshotEnabled() {
            return snapshotEnabled;
        }

        /**
         * Gets the snapshot interval in hours.
         *
         * @return the snapshot interval
         */
        public long getSnapshotIntervalHours() {
            return snapshotIntervalHours;
        }
    }

    /**
     * Configuration for rollback behavior.
     */
    public static final class RollbackConfig {

        private final boolean enabled;
        private final int maxBlocksPerOperation;
        private final boolean restoreInventories;
        private final boolean restoreTileEntities;
        private final boolean notifyPlayers;

        /**
         * Constructs rollback config from a configuration section.
         *
         * @param section the configuration section
         */
        public RollbackConfig(org.bukkit.configuration.ConfigurationSection section) {
            this.enabled = section.getBoolean("enabled", true);
            this.maxBlocksPerOperation = section.getInt("max-blocks-per-operation", 50_000);
            this.restoreInventories = section.getBoolean("restore-inventories", true);
            this.restoreTileEntities = section.getBoolean("restore-tile-entities", true);
            this.notifyPlayers = section.getBoolean("notify-players", true);
        }

        /**
         * Checks if rollback is enabled.
         *
         * @return true if enabled
         */
        public boolean isEnabled() {
            return enabled;
        }

        /**
         * Gets the maximum blocks per rollback operation.
         *
         * @return the max blocks
         */
        public int getMaxBlocksPerOperation() {
            return maxBlocksPerOperation;
        }

        /**
         * Checks if inventories should be restored during rollback.
         *
         * @return true if inventories are restored
         */
        public boolean isRestoreInventories() {
            return restoreInventories;
        }

        /**
         * Checks if tile entities should be restored during rollback.
         *
         * @return true if tile entities are restored
         */
        public boolean isRestoreTileEntities() {
            return restoreTileEntities;
        }

        /**
         * Checks if players should be notified of rollbacks.
         *
         * @return true if players are notified
         */
        public boolean isNotifyPlayers() {
            return notifyPlayers;
        }
    }

    /**
     * Configuration for the license system.
     *
     * <p>The server URL and public key are baked into the jar at build time;
     * only the purchased license key lives in config.yml. Enforcement is
     * compiled in via the {@code release} Maven profile, so editing the
     * config cannot disable the license check.</p>
     */
    public static final class LicenseConfig {

        private final String key;
        private final long checkIntervalMinutes;

        /**
         * Constructs license config from a configuration section.
         *
         * @param section the configuration section
         */
        public LicenseConfig(org.bukkit.configuration.ConfigurationSection section) {
            String key = "";
            long interval = 60L;
            if (section != null) {
                key = section.getString("key", "");
                interval = section.getLong("check-interval-minutes", 60L);
            }
            this.key = key;
            this.checkIntervalMinutes = interval;
        }

        /**
         * Gets the configured license key.
         *
         * @return the license key
         */
        public String getKey() {
            return key;
        }

        /**
         * Gets how often the license is re-verified.
         *
         * @return the interval in minutes
         */
        public long getCheckIntervalMinutes() {
            return checkIntervalMinutes;
        }
    }
}
