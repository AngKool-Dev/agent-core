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
package dev.sentinel.audit.api;

import dev.sentinel.audit.database.model.BlockChangeRecord;
import dev.sentinel.audit.database.model.InventoryChangeRecord;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.jetbrains.annotations.NotNull;

/**
 * Service interface for recording and querying audit events.
 *
 * <p>Provides asynchronous methods for recording audit events and
 * querying historical audit data with filtering and pagination.</p>
 */
public interface AuditService {

    /**
     * Records an audit event asynchronously.
     *
     * @param event the audit event to record
     * @return a future that completes when the event is persisted
     */
    @NotNull
    CompletableFuture<Void> record(@NotNull AuditEvent event);

    /**
     * Records an audit event together with its associated block changes.
     *
     * <p>Persists the audit record and its block changes atomically so that
     * block rollback and inspection have complete data.</p>
     *
     * @param event the audit event to record
     * @param changes the associated block change records
     * @return a future that completes when the event and changes are persisted
     */
    @NotNull
    CompletableFuture<Void> recordBlock(@NotNull AuditEvent event, @NotNull List<BlockChangeRecord> changes);

    /**
     * Records an audit event together with an associated inventory change.
     *
     * <p>Persists the audit record and its inventory change atomically so
     * inventory restoration has the captured item data.</p>
     *
     * @param event the audit event to record
     * @param change the associated inventory change record
     * @return a future that completes when the event and change are persisted
     */
    @NotNull
    CompletableFuture<Void> recordInventory(@NotNull AuditEvent event, @NotNull InventoryChangeRecord change);

    /**
     * Flushes any queued audit events to the database.
     *
     * <p>Safe to call on a scheduled interval; no-op when the queue is empty.
     * Ensures events are persisted during runtime rather than only at
     * batch-size or shutdown.</p>
     */
    void flush();

    /**
     * Queries audit events matching the given criteria.
     *
     * @param query the query parameters
     * @return a future containing the matching audit events
     */
    @NotNull
    CompletableFuture<List<AuditEvent>> query(@NotNull AuditQuery query);

    /**
     * Gets a single audit event by its ID.
     *
     * @param eventId the event ID
     * @return a future containing the event, or empty if not found
     */
    @NotNull
    CompletableFuture<AuditEvent> getById(@NotNull UUID eventId);

    /**
     * Counts audit events matching the given criteria.
     *
     * @param query the query parameters
     * @return a future containing the count
     */
    @NotNull
    CompletableFuture<Long> count(@NotNull AuditQuery query);

    /**
     * Purges audit events older than the specified timestamp.
     *
     * @param before the cutoff timestamp
     * @return a future containing the number of purged events
     */
    @NotNull
    CompletableFuture<Integer> purgeBefore(@NotNull java.time.Instant before);
}
