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
package dev.sentinel.audit.services.impl;

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.api.AuditQuery;
import dev.sentinel.audit.api.AuditService;
import dev.sentinel.audit.cache.AuditCache;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.database.model.AuditRecord;
import dev.sentinel.audit.database.model.BlockChangeRecord;
import dev.sentinel.audit.database.model.InventoryChangeRecord;
import dev.sentinel.audit.database.repository.AuditRepository;
import dev.sentinel.audit.database.repository.BlockChangeRepository;
import dev.sentinel.audit.database.repository.InventoryRepository;
import java.time.Instant;
import java.util.List;
import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Standard implementation of the {@link AuditService}.
 *
 * <p>Records audit events through the cache with asynchronous
 * persistence to the database using batched writes.</p>
 */
public final class StandardAuditService implements AuditService {

    private static final Logger LOGGER = LoggerFactory.getLogger(StandardAuditService.class);

    private final AuditRepository repository;
    private final BlockChangeRepository blockChangeRepository;
    private final InventoryRepository inventoryRepository;
    private final AuditCache cache;
    private final SentinelConfig.AuditConfig config;
    private final ExecutorService executor;
    private final Queue<AuditRecord> writeQueue;
    private final Object writeLock = new Object();
    private boolean flushing = false;

    /**
     * Constructs a new standard audit service.
     *
     * @param repository the audit repository
     * @param blockChangeRepository the block change repository
     * @param inventoryRepository the inventory change repository
     * @param cache the audit cache
     * @param config the audit configuration
     */
    public StandardAuditService(
            @NotNull AuditRepository repository,
            @NotNull BlockChangeRepository blockChangeRepository,
            @NotNull InventoryRepository inventoryRepository,
            @NotNull AuditCache cache,
            @NotNull SentinelConfig.AuditConfig config) {
        this.repository = repository;
        this.blockChangeRepository = blockChangeRepository;
        this.inventoryRepository = inventoryRepository;
        this.cache = cache;
        this.config = config;
        this.executor = Executors.newVirtualThreadPerTaskExecutor();
        this.writeQueue = new ConcurrentLinkedQueue<>();
    }

    /**
     * Records an audit event asynchronously.
     *
     * @param event the audit event to record
     * @return a future that completes when the event is persisted
     */
    @Override
    public @NotNull CompletableFuture<Void> record(@NotNull AuditEvent event) {
        return CompletableFuture.runAsync(
                () -> {
                    AuditRecord record = AuditRecord.from(event);
                    if (writeQueue.size() >= config.getMaxQueueSize()) {
                        LOGGER.warn("Audit queue full ({}); dropping event {}", config.getMaxQueueSize(), event.id());
                        return;
                    }
                    cache.put(event);
                    writeQueue.offer(record);
                    if (writeQueue.size() >= config.getBatchSize()) {
                        flushQueue();
                    }
                },
                executor);
    }

    /**
     * Records an audit event together with its block changes.
     *
     * <p>Persists the audit record first so the block changes can safely
     * reference it as a foreign key, then inserts the block changes.</p>
     *
     * @param event the audit event to record
     * @param changes the associated block change records
     * @return a future that completes when both are persisted
     */
    @Override
    public @NotNull CompletableFuture<Void> recordBlock(
            @NotNull AuditEvent event, @NotNull List<BlockChangeRecord> changes) {
        return CompletableFuture.runAsync(
                () -> {
                    cache.put(event);
                    repository.insertBatch(List.of(AuditRecord.from(event)));
                    blockChangeRepository.insertBatch(changes);
                },
                executor);
    }

    /**
     * Records an audit event together with an inventory change.
     *
     * <p>Persists the audit record first so the inventory change can safely
     * reference it as a foreign key, then inserts the inventory change.</p>
     *
     * @param event the audit event to record
     * @param change the associated inventory change record
     * @return a future that completes when both are persisted
     */
    @Override
    public @NotNull CompletableFuture<Void> recordInventory(
            @NotNull AuditEvent event, @NotNull InventoryChangeRecord change) {
        return CompletableFuture.runAsync(
                () -> {
                    cache.put(event);
                    repository.insertBatch(List.of(AuditRecord.from(event)));
                    inventoryRepository.insertBatch(List.of(change));
                },
                executor);
    }

    /**
     * Flushes any queued audit events to the database.
     */
    @Override
    public void flush() {
        flushQueue();
    }

    /**
     * Flushes the write queue to the database.
     */
    private void flushQueue() {
        synchronized (writeLock) {
            if (flushing) {
                return;
            }
            flushing = true;
            try {
                List<AuditRecord> batch = new java.util.ArrayList<>(Math.min(config.getBatchSize(), writeQueue.size()));
                AuditRecord record;
                int count = 0;
                while ((record = writeQueue.poll()) != null && count < config.getBatchSize()) {
                    batch.add(record);
                    count++;
                }
                if (!batch.isEmpty()) {
                    repository.insertBatch(batch);
                }
            } catch (Exception exception) {
                LOGGER.error("Failed to flush audit queue", exception);
            } finally {
                flushing = false;
            }
        }
    }

    /**
     * Queries audit events matching the given criteria.
     *
     * @param query the query parameters
     * @return a future containing the matching audit events
     */
    @Override
    public @NotNull CompletableFuture<List<AuditEvent>> query(@NotNull AuditQuery query) {
        return CompletableFuture.supplyAsync(
                () -> {
                    List<AuditEvent> cached = cache.get(query);
                    if (!cached.isEmpty()) {
                        return cached;
                    }
                    return repository.query(query).stream()
                            .map(AuditRecord::toEvent)
                            .toList();
                },
                executor);
    }

    /**
     * Gets a single audit event by its ID.
     *
     * @param eventId the event ID
     * @return a future containing the event, or empty if not found
     */
    @Override
    public @NotNull CompletableFuture<AuditEvent> getById(@NotNull UUID eventId) {
        return CompletableFuture.supplyAsync(
                () -> {
                    AuditEvent cached = cache.get(eventId);
                    if (cached != null) {
                        return cached;
                    }
                    return repository
                            .findById(eventId)
                            .map(AuditRecord::toEvent)
                            .orElseThrow(
                                    () -> new dev.sentinel.audit.api.exception.AuditRecordNotFoundException(eventId));
                },
                executor);
    }

    /**
     * Counts audit events matching the given criteria.
     *
     * @param query the query parameters
     * @return a future containing the count
     */
    @Override
    public @NotNull CompletableFuture<Long> count(@NotNull AuditQuery query) {
        return CompletableFuture.supplyAsync(() -> repository.count(query), executor);
    }

    /**
     * Purges audit events older than the specified timestamp.
     *
     * @param before the cutoff timestamp
     * @return a future containing the number of purged events
     */
    @Override
    public @NotNull CompletableFuture<Integer> purgeBefore(@NotNull Instant before) {
        return CompletableFuture.supplyAsync(() -> repository.deleteBefore(before), executor);
    }

    /**
     * Shuts down the virtual thread executor.
     */
    public void shutdown() {
        flushQueue();
        executor.shutdown();
    }
}
