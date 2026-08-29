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
import dev.sentinel.audit.database.model.AuditRecord;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Repository interface for audit record persistence.
 *
 * <p>Defines the data access operations for storing and querying
 * audit records in the database.</p>
 */
public interface AuditRepository {

    /**
     * Inserts a batch of audit records.
     *
     * @param records the records to insert
     */
    void insertBatch(@NotNull List<AuditRecord> records);

    /**
     * Queries audit records matching the given criteria.
     *
     * @param query the query parameters
     * @return the matching audit records
     */
    @NotNull
    List<AuditRecord> query(@NotNull AuditQuery query);

    /**
     * Gets an audit record by its ID.
     *
     * @param id the record ID
     * @return the record, or empty if not found
     */
    @NotNull
    Optional<AuditRecord> findById(@NotNull UUID id);

    /**
     * Counts audit records matching the given criteria.
     *
     * @param query the query parameters
     * @return the count
     */
    long count(@NotNull AuditQuery query);

    /**
     * Deletes audit records older than the given timestamp.
     *
     * @param before the cutoff timestamp
     * @return the number of deleted records
     */
    int deleteBefore(@NotNull Instant before);

    /**
     * Gets the most recent audit record for a block location.
     *
     * @param worldName the world name
     * @param x the X coordinate
     * @param y the Y coordinate
     * @param z the Z coordinate
     * @return the most recent record, or empty if none
     */
    @NotNull
    Optional<AuditRecord> findLatestAt(@NotNull String worldName, int x, int y, int z);

    /**
     * Gets all audit records for a specific block location, most recent first.
     *
     * <p>Includes both block edit events and entity events that occurred at the
     * given coordinates, so inspection can surface who modified a block or
     * killed an entity there.</p>
     *
     * @param worldName the world name
     * @param x the X coordinate
     * @param y the Y coordinate
     * @param z the Z coordinate
     * @param limit the maximum number of records
     * @return the audit records, most recent first
     */
    @NotNull
    List<AuditRecord> findByLocation(@NotNull String worldName, int x, int y, int z, int limit);

    /**
     * Gets all audit records matching the given IDs in a single query.
     *
     * <p>Used to resolve block change audit events in bulk instead of issuing
     * one query per change (N+1).</p>
     *
     * @param ids the record IDs
     * @return the matching records
     */
    @NotNull
    List<AuditRecord> findByIds(@NotNull java.util.Collection<java.util.UUID> ids);
}
