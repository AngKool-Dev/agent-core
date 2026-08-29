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
import dev.sentinel.audit.database.model.BlockChangeRecord;
import dev.sentinel.audit.models.BlockSnapshot;
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
 * JDBC-based implementation of the {@link BlockChangeRepository}.
 *
 * <p>Uses plain JDBC with a connection pool for block change persistence
 * across supported database backends.</p>
 */
public final class JdbcBlockChangeRepository implements BlockChangeRepository {

    private static final String INSERT_SQL = """
            INSERT INTO block_changes (
                id, audit_event_id, world_name, x, y, z,
                before_material, before_data, before_tile_data,
                after_material, after_data, after_tile_data,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """;

    private static final String DELETE_BEFORE_SQL = """
            DELETE FROM block_changes WHERE timestamp < ?
            """;

    private final DataSource dataSource;

    /**
     * Constructs a new JDBC block change repository.
     *
     * @param dataSource the data source
     */
    public JdbcBlockChangeRepository(@NotNull DataSource dataSource) {
        this.dataSource = dataSource;
    }

    /**
     * Inserts a batch of block change records.
     *
     * @param records the records to insert
     */
    @Override
    public void insertBatch(@NotNull List<BlockChangeRecord> records) {
        if (records.isEmpty()) {
            return;
        }
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(INSERT_SQL)) {
            for (BlockChangeRecord record : records) {
                statement.setString(1, record.id().toString());
                statement.setString(2, record.auditEventId().toString());
                statement.setString(3, record.worldName());
                statement.setInt(4, record.x());
                statement.setInt(5, record.y());
                statement.setInt(6, record.z());
                statement.setString(7, record.before().material().name());
                statement.setString(8, record.before().blockData());
                statement.setString(9, record.before().tileEntityData());
                statement.setString(10, record.after().material().name());
                statement.setString(11, record.after().blockData());
                statement.setString(12, record.after().tileEntityData());
                statement.setTimestamp(13, java.sql.Timestamp.from(record.timestamp()));
                statement.addBatch();
            }
            statement.executeBatch();
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to insert block change records", exception);
        }
    }

    /**
     * Gets all block changes at a specific location.
     *
     * @param worldName the world name
     * @param x the X coordinate
     * @param y the Y coordinate
     * @param z the Z coordinate
     * @param limit the maximum number of records
     * @return the block change records, most recent first
     */
    @Override
    public @NotNull List<BlockChangeRecord> findByLocation(@NotNull String worldName, int x, int y, int z, int limit) {
        String sql =
                "SELECT * FROM block_changes WHERE world_name = ? AND x = ? AND y = ? AND z = ? ORDER BY timestamp DESC LIMIT ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setInt(2, x);
            statement.setInt(3, y);
            statement.setInt(4, z);
            statement.setInt(5, limit);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes at location", exception);
        }
    }

    /**
     * Gets all block changes within a region and time range.
     *
     * @param worldName the world name
     * @param minX the minimum X coordinate
     * @param minY the minimum Y coordinate
     * @param minZ the minimum Z coordinate
     * @param maxX the maximum X coordinate
     * @param maxY the maximum Y coordinate
     * @param maxZ the maximum Z coordinate
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the block change records
     */
    @Override
    public @NotNull List<BlockChangeRecord> findByRegion(
            @NotNull String worldName,
            int minX,
            int minY,
            int minZ,
            int maxX,
            int maxY,
            int maxZ,
            @NotNull Instant from,
            @NotNull Instant to) {
        String sql = "SELECT * FROM block_changes WHERE world_name = ? AND x BETWEEN ? AND ? "
                + "AND y BETWEEN ? AND ? AND z BETWEEN ? AND ? AND timestamp BETWEEN ? AND ? "
                + "ORDER BY timestamp DESC";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setInt(2, minX);
            statement.setInt(3, maxX);
            statement.setInt(4, minY);
            statement.setInt(5, maxY);
            statement.setInt(6, minZ);
            statement.setInt(7, maxZ);
            statement.setTimestamp(8, java.sql.Timestamp.from(from));
            statement.setTimestamp(9, java.sql.Timestamp.from(to));
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes in region", exception);
        }
    }

    /**
     * Gets all non-player block changes within a region and time range, used to
     * sweep environmental effects (liquid flow, fire spread) adjacent to an
     * actor's own edits during a player rollback.
     *
     * @param worldName the world name
     * @param minX the minimum X coordinate
     * @param minY the minimum Y coordinate
     * @param minZ the minimum Z coordinate
     * @param maxX the maximum X coordinate
     * @param maxY the maximum Y coordinate
     * @param maxZ the maximum Z coordinate
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the ambient block changes
     */
    @Override
    public @NotNull List<BlockChangeRecord> findAmbientByRegion(
            @NotNull String worldName,
            int minX,
            int minY,
            int minZ,
            int maxX,
            int maxY,
            int maxZ,
            @NotNull Instant from,
            @NotNull Instant to) {
        String sql = "SELECT c.* FROM block_changes c JOIN audit_records a ON a.id = c.audit_event_id "
                + "WHERE c.world_name = ? AND c.x BETWEEN ? AND ? AND c.y BETWEEN ? AND ? AND c.z BETWEEN ? AND ? "
                + "AND c.timestamp BETWEEN ? AND ? AND a.source NOT IN ('PLAYER', 'CONSOLE', 'SENTINEL') "
                + "ORDER BY c.timestamp DESC";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setInt(2, minX);
            statement.setInt(3, maxX);
            statement.setInt(4, minY);
            statement.setInt(5, maxY);
            statement.setInt(6, minZ);
            statement.setInt(7, maxZ);
            statement.setTimestamp(8, java.sql.Timestamp.from(from));
            statement.setTimestamp(9, java.sql.Timestamp.from(to));
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find ambient block changes in region", exception);
        }
    }

    /**
     * Gets all block changes associated with an audit event.
     *
     * @param auditEventId the audit event ID
     * @return the block change records
     */
    @Override
    public @NotNull List<BlockChangeRecord> findByAuditEvent(@NotNull UUID auditEventId) {
        String sql = "SELECT * FROM block_changes WHERE audit_event_id = ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, auditEventId.toString());
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes for audit event", exception);
        }
    }

    /**
     * Gets all block changes made by a specific actor within a time range.
     *
     * @param actorId the UUID of the actor
     * @param from the start of the time range
     * @param to the end of the time range
     * @param limit the maximum number of records
     * @return the block change records, most recent first
     */
    @Override
    public @NotNull List<BlockChangeRecord> findByActor(
            @NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to, int limit) {
        String sql = "SELECT c.* FROM block_changes c JOIN audit_records a ON a.id = c.audit_event_id "
                + "WHERE a.actor_id = ? AND c.timestamp BETWEEN ? AND ? "
                + "ORDER BY c.timestamp DESC LIMIT ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, actorId.toString());
            statement.setTimestamp(2, java.sql.Timestamp.from(from));
            statement.setTimestamp(3, java.sql.Timestamp.from(to));
            statement.setInt(4, limit);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes for actor", exception);
        }
    }

    @Override
    public @NotNull List<BlockChangeRecord> findByActor(
            @NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to, int limit, int offset) {
        String sql = "SELECT c.* FROM block_changes c JOIN audit_records a ON a.id = c.audit_event_id "
                + "WHERE a.actor_id = ? AND c.timestamp BETWEEN ? AND ? "
                + "ORDER BY c.timestamp DESC LIMIT ? OFFSET ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, actorId.toString());
            statement.setTimestamp(2, java.sql.Timestamp.from(from));
            statement.setTimestamp(3, java.sql.Timestamp.from(to));
            statement.setInt(4, limit);
            statement.setInt(5, offset);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes for actor", exception);
        }
    }

    /**
     * Gets all block changes within a world and time range.
     *
     * @param worldName the world name
     * @param from the start of the time range
     * @param to the end of the time range
     * @param limit the maximum number of records
     * @return the block change records, most recent first
     */
    @Override
    public @NotNull List<BlockChangeRecord> findByWorld(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to, int limit) {
        String sql = "SELECT * FROM block_changes WHERE world_name = ? AND timestamp BETWEEN ? AND ? "
                + "ORDER BY timestamp DESC LIMIT ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setTimestamp(2, java.sql.Timestamp.from(from));
            statement.setTimestamp(3, java.sql.Timestamp.from(to));
            statement.setInt(4, limit);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes in world", exception);
        }
    }

    @Override
    public @NotNull List<BlockChangeRecord> findByWorld(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to, int limit, int offset) {
        String sql = "SELECT * FROM block_changes WHERE world_name = ? AND timestamp BETWEEN ? AND ? "
                + "ORDER BY timestamp DESC LIMIT ? OFFSET ?";
        try (Connection connection = dataSource.getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, worldName);
            statement.setTimestamp(2, java.sql.Timestamp.from(from));
            statement.setTimestamp(3, java.sql.Timestamp.from(to));
            statement.setInt(4, limit);
            statement.setInt(5, offset);
            try (ResultSet resultSet = statement.executeQuery()) {
                java.util.List<BlockChangeRecord> results = new java.util.ArrayList<>();
                while (resultSet.next()) {
                    results.add(mapRow(resultSet));
                }
                return results;
            }
        } catch (SQLException exception) {
            throw new DatabaseException("Failed to find block changes in world", exception);
        }
    }

    /**
     * Deletes block change records older than the given timestamp.
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
            String message = "Failed to delete block change records before " + before;
            throw new DatabaseException(message, exception);
        }
    }

    /**
     * Maps a result set row to a block change record.
     *
     * @param resultSet the result set
     * @return the mapped record
     * @throws SQLException if a mapping error occurs
     */
    private BlockChangeRecord mapRow(@NotNull ResultSet resultSet) throws SQLException {
        String beforeMaterial = resultSet.getString("before_material");
        String afterMaterial = resultSet.getString("after_material");
        BlockSnapshot before = new BlockSnapshot(
                org.bukkit.Material.valueOf(beforeMaterial),
                resultSet.getString("before_data"),
                resultSet.getString("before_tile_data"),
                java.util.Map.of());
        BlockSnapshot after = new BlockSnapshot(
                org.bukkit.Material.valueOf(afterMaterial),
                resultSet.getString("after_data"),
                resultSet.getString("after_tile_data"),
                java.util.Map.of());
        return new BlockChangeRecord(
                UUID.fromString(resultSet.getString("id")),
                UUID.fromString(resultSet.getString("audit_event_id")),
                resultSet.getString("world_name"),
                resultSet.getInt("x"),
                resultSet.getInt("y"),
                resultSet.getInt("z"),
                before,
                after,
                resultSet.getTimestamp("timestamp").toInstant());
    }
}
