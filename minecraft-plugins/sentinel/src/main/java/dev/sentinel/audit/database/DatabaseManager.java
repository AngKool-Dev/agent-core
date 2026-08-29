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
package dev.sentinel.audit.database;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dev.sentinel.audit.api.exception.DatabaseException;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.models.DatabaseType;
import java.io.File;
import java.nio.file.Path;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Manages the database connection pool and migrations.
 *
 * <p>Creates and configures the HikariCP connection pool based on the
 * configured database type, and runs Flyway migrations on startup.</p>
 */
public final class DatabaseManager implements AutoCloseable {

    private static final Logger LOGGER = LoggerFactory.getLogger(DatabaseManager.class);

    private final SentinelConfig.DatabaseConfig config;
    private final Path dataFolder;
    private HikariDataSource dataSource;

    /**
     * Constructs a new database manager.
     *
     * @param config the database configuration
     * @param dataFolder the plugin data folder
     */
    public DatabaseManager(@NotNull SentinelConfig.DatabaseConfig config, @NotNull Path dataFolder) {
        this.config = config;
        this.dataFolder = dataFolder;
    }

    /**
     * Initializes the database connection pool and runs migrations.
     *
     * @throws DatabaseException if initialization fails
     */
    public void initialize() {
        try {
            this.dataSource = createDataSource();
            runMigrations();
            LOGGER.info("Database initialized: {}", config.getType());
        } catch (Exception exception) {
            throw new DatabaseException("Failed to initialize database", exception);
        }
    }

    /**
     * Creates the HikariCP data source.
     *
     * @return the configured data source
     */
    private HikariDataSource createDataSource() {
        HikariConfig hikariConfig = new HikariConfig();
        hikariConfig.setDriverClassName(config.getType().getDriverClass());
        hikariConfig.setJdbcUrl(buildJdbcUrl());
        hikariConfig.setUsername(config.getUsername());
        hikariConfig.setPassword(config.getPassword());
        hikariConfig.setMaximumPoolSize(config.getPoolSize());
        hikariConfig.setConnectionTimeout(config.getConnectionTimeoutMs());
        hikariConfig.setMaxLifetime(config.getMaxLifetimeMs());
        hikariConfig.setPoolName("Sentinel-Pool");
        hikariConfig.setMaximumPoolSize(config.getPoolSize());
        hikariConfig.setConnectionTimeout(config.getConnectionTimeoutMs());
        hikariConfig.setMaxLifetime(config.getMaxLifetimeMs());
        hikariConfig.setPoolName("Sentinel-Pool");
        hikariConfig.setAutoCommit(true);
        if (config.getType() == DatabaseType.SQLITE) {
            hikariConfig.setConnectionInitSql("PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL;");
            hikariConfig.setMaximumPoolSize(Math.min(2, config.getPoolSize()));
        }
        return new HikariDataSource(hikariConfig);
    }

    /**
     * Builds the JDBC URL based on the database type.
     *
     * @return the JDBC URL
     */
    private String buildJdbcUrl() {
        if (config.getType() == DatabaseType.SQLITE) {
            File dbFile = dataFolder.resolve("sentinel.db").toFile();
            return String.format(config.getType().getUrlTemplate(), dbFile.getAbsolutePath());
        }
        return String.format(
                config.getType().getUrlTemplate(), config.getHost(), config.getPort(), config.getDatabase());
    }

    /**
     * Runs database migrations.
     *
     * <p>Flyway is used for databases it supports. SQLite is not supported by
     * Flyway 10 community, so its (idempotent) migration script is executed
     * directly instead.</p>
     *
     * <p>Flyway locates migrations via {@code Thread.currentThread().getContextClassLoader()}.
     * On server threads that context class loader does not see the shaded plugin jar, so it
     * is temporarily swapped to the plugin's class loader to ensure {@code db/migration}
     * resources are found.</p>
     */
    private void runMigrations() {
        if (config.getType() == DatabaseType.SQLITE) {
            runSqlMigrations();
            return;
        }
        Thread thread = Thread.currentThread();
        ClassLoader original = thread.getContextClassLoader();
        thread.setContextClassLoader(getClass().getClassLoader());
        try {
            Flyway flyway = Flyway.configure()
                    .dataSource(dataSource)
                    .locations("classpath:db/migration")
                    .baselineOnMigrate(true)
                    .load();
            flyway.migrate();
        } finally {
            thread.setContextClassLoader(original);
        }
    }

    /**
     * Executes the SQLite migration script directly.
     *
     * <p>The script uses {@code CREATE TABLE IF NOT EXISTS} and {@code CREATE INDEX IF NOT EXISTS}
     * so it is safe to run on every startup.</p>
     */
    private void runSqlMigrations() {
        try (java.io.InputStream input = DatabaseManager.class
                        .getClassLoader()
                        .getResourceAsStream("db/migration/V1__create_schema.sql");
                java.sql.Connection connection = dataSource.getConnection();
                java.sql.Statement statement = connection.createStatement()) {
            if (input == null) {
                throw new DatabaseException("Migration script 'db/migration/V1__create_schema.sql' not found");
            }
            String sql = new String(input.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
            for (String statementSql : sql.split(";")) {
                String trimmed = statementSql.trim();
                if (!trimmed.isEmpty()) {
                    statement.execute(trimmed);
                }
            }
            LOGGER.info("SQLite schema up to date.");
        } catch (java.io.IOException | java.sql.SQLException exception) {
            throw new DatabaseException("Failed to run SQLite migrations", exception);
        }
    }

    /**
     * Gets the active data source.
     *
     * @return the data source
     */
    public DataSource getDataSource() {
        return dataSource;
    }

    /**
     * Closes the database connection pool.
     */
    @Override
    public void close() {
        if (dataSource != null && !dataSource.isClosed()) {
            dataSource.close();
            LOGGER.info("Database connection pool closed.");
        }
    }
}
