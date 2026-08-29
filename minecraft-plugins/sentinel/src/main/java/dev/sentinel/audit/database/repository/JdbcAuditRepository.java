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

import dev.sentinel.audit.api.AuditQuery;
import dev.sentinel.audit.api.exception.DatabaseException;
import dev.sentinel.audit.database.model.AuditRecord;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import javax.sql.DataSource;
import org.jetbrains.annotations.NotNull;

/**
 * JDBC-based implementation of the {@link AuditRepository}.
 *
 * <p>Uses plain JDBC with a connection pool for maximum performance
 * and database compatibility across supported backends.</p>
 */
public final class JdbcAuditRepository implements AuditRepository {

    private static final String INSERT_SQL = """
            INSERT INTO audit_records (
                id, action, source, actor_id, actor_name, target_id, target_name,
                world_name, x, y, z, timestamp, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """;

    private static final String SELECT_BY_ID_SQL = """
            SELECT * FROM audit_records WHERE id = ?
            """;

    private static final String DELETE_BEFORE_SQL = """
            DELETE FROM audit_records WHERE timestamp < ?
            """;

    private final DataSource dataSource;

    /**
     * Constructs a new JDBC audit repository.
     *
     * @param dataSource the data source
     */
    public JdbcAuditRepository(@NotNull DataSource dataSource) {
        this.dataSource = dataSource;
    }

    /**
     * Inserts a batch of audit records.
     *
     * @param records the records to insert
     */
    @Override
    public void insertBatch(@NotNull List<AuditRecord> records) {
        if (records.isEmpty()) {
            return;
        }
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(INSERT_SQL)) {
            for (AuditRecord record : records) {
                statement.setString(1, record.id().toString());
                statement.setString(2, record.action().name());
                statement.setString(3, record.source().name());
                statement.setString(4, record.actorId().toString());
                statement.setString(5, record.actorName());
                statement.setString(
                        6, record.targetId() != null ? record.targetId().toString() : null);
                statement.setString(7, record.targetName());
                statement.setString(8, record.worldName());
                statement.setInt(9, record.x());
                statement.setInt(10, record.y());
                statement.setInt(11, record.z());
                statement.setTimestamp(12, java.sql.Timestamp.from(record.timestamp()));
                statement.setString(13, record.metadata());
                statement.addBatch();
            }
            statement.executeBatch();
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to insert audit records", exception);
        }
    }

    /**
     * Queries audit records matching the given criteria.
     *
     * @param query the query parameters
     * @return the matching audit records
     */
    @Override
    public @NotNull List<AuditRecord> query(@NotNull AuditQuery query) {
        StringBuilder sql = new StringBuilder("SELECT * FROM audit_records WHERE 1=1");
        java.util.List<Object> params = new java.util.ArrayList<>();

        if (query.actorId() != null) {
            sql.append(" AND actor_id = ?");
            params.add(query.actorId().toString());
        }
        if (query.action() != null) {
            sql.append(" AND action = ?");
            params.add(query.action().name());
        }
        if (query.from() != null) {
            sql.append(" AND timestamp >= ?");
            params.add(java.sql.Timestamp.from(query.from()));
        }
        if (query.to() != null) {
            sql.append(" AND timestamp <= ?");
            params.add(java.sql.Timestamp.from(query.to()));
        }
        if (query.worldName() != null) {
            sql.append(" AND world_name = ?");
            params.add(query.worldName());
        }
        if (query.location() != null) {
            sql.append(" AND x = ? AND y = ? AND z = ?");
            var loc = query.location();
            params.add(loc.getBlockX());
            params.add(loc.getBlockY());
            params.add(loc.getBlockZ());
        }
        sql.append(" ORDER BY timestamp DESC");
        if (query.limit() > 0) {
            sql.append(" LIMIT ?");
            params.add(query.limit());
        }

        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql.toString())) {
            for (int i = 0; i < params.size(); i++) {
                statement.setObject(i + 1, params.get(i));
            }
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<AuditRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to query audit records", exception);
        }
    }

    /**
     * Gets an audit record by its ID.
     *
     * @param id the record ID
     * @return the record, or empty if not found
     */
    @Override
    public @NotNull Optional<AuditRecord> findById(@NotNull UUID id) {
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(SELECT_BY_ID_SQL)) {
            statement.setString(1, id.toString());
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return Optional.of(mapRow(resultSet));
                }
            }
            return Optional.empty();
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find audit record: " + id, exception);
        }
    }

    /**
     * Gets all audit records matching the given IDs in a single query.
     *
     * @param ids the record IDs
     * @return the matching records
     */
    @Override
    public @NotNull List<AuditRecord> findByIds(@NotNull java.util.Collection<java.util.UUID> ids) {
        if (ids.isEmpty()) {
            return List.of();
        }
        String placeholders = String.join(",", java.util.Collections.nCopies(ids.size(), "?"));
        String sql = "SELECT * FROM audit_records WHERE id IN (" + placeholders + ")";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            int index = 1;
            for (java.util.UUID id : ids) {
                statement.setString(index++, id.toString());
            }
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<AuditRecord> results = new java.util.ArrayList<>(ids.size());
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find audit records by ids", exception);
        }
    }

    /**
     * Counts audit records matching the given criteria.
     *
     * @param query the query parameters
     * @return the count
     */
    @Override
    public long count(@NotNull AuditQuery query) {
        StringBuilder sql = new StringBuilder("SELECT COUNT(*) FROM audit_records WHERE 1=1");
        java.util.List<Object> params = new java.util.ArrayList<>();

        if (query.actorId() != null) {
            sql.append(" AND actor_id = ?");
            params.add(query.actorId().toString());
        }
        if (query.action() != null) {
            sql.append(" AND action = ?");
            params.add(query.action().name());
        }
        if (query.from() != null) {
            sql.append(" AND timestamp >= ?");
            params.add(java.sql.Timestamp.from(query.from()));
        }
        if (query.to() != null) {
            sql.append(" AND timestamp <= ?");
            params.add(java.sql.Timestamp.from(query.to()));
        }
        if (query.worldName() != null) {
            sql.append(" AND world_name = ?");
            params.add(query.worldName());
        }

        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql.toString())) {
            for (int i = 0; i < params.size(); i++) {
                statement.setObject(i + 1, params.get(i));
            }
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return resultSet.getLong(1);
                }
                return 0L;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to count audit records", exception);
        }
    }

    /**
     * Deletes audit records older than the given timestamp.
     *
     * @param before the cutoff timestamp
     * @return the number of deleted records
     */
    @Override
    public int deleteBefore(@NotNull Instant before) {
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(DELETE_BEFORE_SQL)) {
            statement.setTimestamp(1, java.sql.Timestamp.from(before));
            return statement.executeUpdate();
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to delete audit records before " + before, exception);
        }
    }

    /**
     * Gets the most recent audit record for a block location.
     *
     * @param worldName the world name
     * @param x the X coordinate
     * @param y the Y coordinate
     * @param z the Z coordinate
     * @return the most recent record, or empty if none
     */
    @Override
    public @NotNull Optional<AuditRecord> findLatestAt(@NotNull String worldName, int x, int y, int z) {
        String sql =
                "SELECT * FROM audit_records WHERE world_name = ? AND x = ? AND y = ? AND z = ? ORDER BY timestamp DESC LIMIT 1";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setInt(2, x);
            statement.setInt(3, y);
            statement.setInt(4, z);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return Optional.of(mapRow(resultSet));
                }
            }
            return Optional.empty();
        } catch (SQLException exception) {
            throw new DatabaseException(
                    "Failed to find latest audit record at " + worldName + " " + x + "," + y + "," + z, exception);
        }
    }

    /**
     * Gets all audit records for a specific block location, most recent first.
     *
     * @param worldName the world name
     * @param x the X coordinate
     * @param y the Y coordinate
     * @param z the Z coordinate
     * @param limit the maximum number of records
     * @return the audit records, most recent first
     */
    @Override
    public @NotNull List<AuditRecord> findByLocation(@NotNull String worldName, int x, int y, int z, int limit) {
        String sql = "SELECT * FROM audit_records WHERE world_name = ? AND x = ? AND y = ? AND z = ? "
                + "ORDER BY timestamp DESC LIMIT ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setInt(2, x);
            statement.setInt(3, y);
            statement.setInt(4, z);
            statement.setInt(5, limit);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<AuditRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find audit records at location", exception);
        }
    }

    /**
     * Maps a result set row to an audit record.
     *
     * @param resultSet the result set
     * @return the mapped audit record
     * @throws SQLException if a mapping error occurs
     */
    private AuditRecord mapRow(@NotNull ResultSet resultSet) throws SQLException {
        return new AuditRecord(
                UUID.fromString(resultSet.getString("id")),
                dev.sentinel.audit.models.AuditAction.valueOf(resultSet.getString("action")),
                dev.sentinel.audit.models.AuditSource.valueOf(resultSet.getString("source")),
                UUID.fromString(resultSet.getString("actor_id")),
                resultSet.getString("actor_name"),
                resultSet.getString("target_id") != null ? UUID.fromString(resultSet.getString("target_id")) : null,
                resultSet.getString("target_name"),
                resultSet.getString("world_name"),
                resultSet.getInt("x"),
                resultSet.getInt("y"),
                resultSet.getInt("z"),
                resultSet.getTimestamp("timestamp").toInstant(),
                resultSet.getString("metadata"));
    }
}
