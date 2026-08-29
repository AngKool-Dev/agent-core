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

import dev.sentinel.audit.database.model.BlockChangeRecord;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Repository interface for block change record persistence.
 *
 * <p>Defines the data access operations for storing and querying
 * block change records used for inspection and rollback.</p>
 */
public interface BlockChangeRepository {

    /**
     * Inserts a batch of block change records.
     *
     * @param records the records to insert
     */
    void insertBatch(@NotNull List<BlockChangeRecord> records);

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
    @NotNull
    List<BlockChangeRecord> findByLocation(@NotNull String worldName, int x, int y, int z, int limit);

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
    @NotNull
    List<BlockChangeRecord> findByRegion(
            @NotNull String worldName,
            int minX,
            int minY,
            int minZ,
            int maxX,
            int maxY,
            int maxZ,
            @NotNull Instant from,
            @NotNull Instant to);

    /**
     * Gets block changes within a region and time range whose source is not a
     * player action, joining the surrounding environmental effects.
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
    @NotNull
    List<BlockChangeRecord> findAmbientByRegion(
            @NotNull String worldName,
            int minX,
            int minY,
            int minZ,
            int maxX,
            int maxY,
            int maxZ,
            @NotNull Instant from,
            @NotNull Instant to);

    /**
     * Gets all block changes associated with an audit event.
     *
     * @param auditEventId the audit event ID
     * @return the block change records
     */
    @NotNull
    List<BlockChangeRecord> findByAuditEvent(@NotNull UUID auditEventId);

    /**
     * Gets all block changes made by a specific actor within a time range.
     *
     * @param actorId the UUID of the actor
     * @param from the start of the time range
     * @param to the end of the time range
     * @param limit the maximum number of records
     * @return the block change records, most recent first
     */
    @NotNull
    List<BlockChangeRecord> findByActor(@NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to, int limit);

    /**
     * Gets a page of block changes made by a specific actor within a time range.
     *
     * @param actorId the UUID of the actor
     * @param from the start of the time range
     * @param to the end of the time range
     * @param limit the maximum number of records per page
     * @param offset the number of records to skip
     * @return the block change records, most recent first
     */
    @NotNull
    List<BlockChangeRecord> findByActor(
            @NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to, int limit, int offset);

    /**
     * Gets all block changes within a world and time range.
     *
     * @param worldName the world name
     * @param from the start of the time range
     * @param to the end of the time range
     * @param limit the maximum number of records
     * @return the block change records, most recent first
     */
    @NotNull
    List<BlockChangeRecord> findByWorld(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to, int limit);

    /**
     * Gets a page of block changes within a world and time range.
     *
     * @param worldName the world name
     * @param from the start of the time range
     * @param to the end of the time range
     * @param limit the maximum number of records per page
     * @param offset the number of records to skip
     * @return the block change records, most recent first
     */
    @NotNull
    List<BlockChangeRecord> findByWorld(
            @NotNull String worldName, @NotNull Instant from, @NotNull Instant to, int limit, int offset);

    /**
     * Deletes block change records older than the given timestamp.
     *
     * @param before the cutoff timestamp
     * @return the number of deleted records
     */
    int deleteBefore(@NotNull Instant before);
}
