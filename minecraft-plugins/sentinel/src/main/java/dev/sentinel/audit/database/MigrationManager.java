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

import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Manages Flyway database migrations.
 *
 * <p>Encapsulates Flyway configuration and provides methods to
 * run and validate database migrations.</p>
 */
public final class MigrationManager {

    private static final Logger LOGGER = LoggerFactory.getLogger(MigrationManager.class);

    private static final String MIGRATION_LOCATION = "classpath:db/migration";

    private final Flyway flyway;

    /**
     * Constructs a new migration manager.
     *
     * @param dataSource the data source
     */
    public MigrationManager(@NotNull DataSource dataSource) {
        this.flyway = Flyway.configure()
                .dataSource(dataSource)
                .locations(MIGRATION_LOCATION)
                .baselineOnMigrate(true)
                .validateOnMigrate(true)
                .load();
    }

    /**
     * Runs all pending migrations.
     */
    public void migrate() {
        var result = flyway.migrate();
        LOGGER.info("Applied {} database migration(s)", result.migrationsExecuted);
    }

    /**
     * Validates the current database state against the migrations.
     */
    public void validate() {
        flyway.validate();
    }

    /**
     * Gets the current migration version.
     *
     * @return the current schema version
     */
    public String currentVersion() {
        var info = flyway.info().current();
        return info != null ? info.getVersion().toString() : "none";
    }
}
