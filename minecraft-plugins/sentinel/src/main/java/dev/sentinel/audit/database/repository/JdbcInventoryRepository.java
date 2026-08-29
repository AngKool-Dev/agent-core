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
package dev.sentinel.audit.database.repository;

import dev.sentinel.audit.api.exception.DatabaseException;
import dev.sentinel.audit.database.model.InventoryChangeRecord;
import dev.sentinel.audit.models.InventorySnapshot;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import javax.sql.DataSource;
import org.jetbrains.annotations.NotNull;

/**
 * JDBC-based implementation of the {@link InventoryRepository}.
 *
 * <p>Uses plain JDBC with a connection pool for inventory change
 * persistence across supported database backends.</p>
 */
public final class JdbcInventoryRepository implements InventoryRepository {

    private static final String INSERT_SQL = """
            INSERT INTO inventory_changes (
                id, audit_event_id, inventory_id,
                before_contents, before_size, before_title,
                after_contents, after_size, after_title,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """;

    private final DataSource dataSource;

    /**
     * Constructs a new JDBC inventory repository.
     *
     * @param dataSource the data source
     */
    public JdbcInventoryRepository(@NotNull DataSource dataSource) {
        this.dataSource = dataSource;
    }

    /**
     * Inserts a batch of inventory change records.
     *
     * @param records the records to insert
     */
    @Override
    public void insertBatch(@NotNull List<InventoryChangeRecord> records) {
        if (records.isEmpty()) {
            return;
        }
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(INSERT_SQL)) {
            for (InventoryChangeRecord record : records) {
                statement.setString(1, record.id().toString());
                statement.setString(2, record.auditEventId().toString());
                statement.setString(3, record.inventoryId());
                statement.setString(
                        4, InventorySnapshot.serializeContents(record.before().contents()));
                statement.setInt(5, record.before().size());
                statement.setString(6, record.before().title());
                statement.setString(
                        7, InventorySnapshot.serializeContents(record.after().contents()));
                statement.setInt(8, record.after().size());
                statement.setString(9, record.after().title());
                statement.setTimestamp(10, java.sql.Timestamp.from(record.timestamp()));
                statement.addBatch();
            }
            statement.executeBatch();
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to insert inventory change records", exception);
        }
    }

    /**
     * Gets all inventory changes for a specific inventory.
     *
     * @param inventoryId the inventory identifier
     * @param limit the maximum number of records
     * @return the inventory change records, most recent first
     */
    @Override
    public @NotNull List<InventoryChangeRecord> findByInventoryId(@NotNull String inventoryId, int limit) {
        String sql = "SELECT * FROM inventory_changes WHERE inventory_id = ? ORDER BY timestamp DESC LIMIT ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, inventoryId);
            statement.setInt(2, limit);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<InventoryChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find inventory changes", exception);
        }
    }

    /**
     * Gets all inventory changes captured for a world (despawned, voided,
     * or environment-destroyed items) within a time range.
     *
     * @param worldName the world name
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the inventory change records, most recent first
     */
    @Override
    public @NotNull List<InventoryChangeRecord> findWorldLosses(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to) {
        String sql = "SELECT * FROM inventory_changes WHERE inventory_id = ? AND timestamp >= ? AND timestamp <= ? "
                + "ORDER BY timestamp DESC";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, "world:" + worldName);
            statement.setTimestamp(2, java.sql.Timestamp.from(from));
            statement.setTimestamp(3, java.sql.Timestamp.from(to));
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<InventoryChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find world inventory losses", exception);
        }
    }

    /**
     * Gets all inventory changes associated with an audit event.
     *
     * @param auditEventId the audit event ID
     * @return the inventory change records
     */
    @Override
    public @NotNull List<InventoryChangeRecord> findByAuditEvent(@NotNull UUID auditEventId) {
        String sql = "SELECT * FROM inventory_changes WHERE audit_event_id = ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, auditEventId.toString());
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<InventoryChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find inventory changes for audit event", exception);
        }
    }

    /**
     * Maps a result set row to an inventory change record.
     *
     * @param resultSet the result set
     * @return the mapped record
     * @throws SQLException if a mapping error occurs
     */
    private InventoryChangeRecord mapRow(@NotNull ResultSet resultSet) throws SQLException {
        InventorySnapshot before = new InventorySnapshot(
                InventorySnapshot.deserializeContents(resultSet.getString("before_contents")),
                resultSet.getInt("before_size"),
                resultSet.getString("before_title"),
                java.util.Map.of());
        InventorySnapshot after = new InventorySnapshot(
                InventorySnapshot.deserializeContents(resultSet.getString("after_contents")),
                resultSet.getInt("after_size"),
                resultSet.getString("after_title"),
                java.util.Map.of());
        return new InventoryChangeRecord(
                UUID.fromString(resultSet.getString("id")),
                UUID.fromString(resultSet.getString("audit_event_id")),
                resultSet.getString("inventory_id"),
                before,
                after,
                resultSet.getTimestamp("timestamp").toInstant());
    }
}
