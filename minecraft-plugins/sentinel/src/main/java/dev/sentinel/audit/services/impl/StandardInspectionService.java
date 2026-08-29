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
import dev.sentinel.audit.api.InspectionService;
import dev.sentinel.audit.api.dto.InspectionResult;
import dev.sentinel.audit.cache.AuditCache;
import dev.sentinel.audit.cache.InspectionCache;
import dev.sentinel.audit.database.model.AuditRecord;
import dev.sentinel.audit.database.repository.AuditRepository;
import dev.sentinel.audit.database.repository.BlockChangeRepository;
import dev.sentinel.audit.models.LocationKey;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.bukkit.Location;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/**
 * Standard implementation of the {@link InspectionService}.
 *
 * <p>Queries block history from the database with caching support
 * for frequently inspected locations.</p>
 */
public final class StandardInspectionService implements InspectionService {

    private final AuditRepository auditRepository;
    private final BlockChangeRepository blockChangeRepository;
    private final InspectionCache cache;
    private final AuditCache auditCache;
    private final ExecutorService executor;

    /**
     * Constructs a new standard inspection service.
     *
     * @param auditRepository the audit repository
     * @param blockChangeRepository the block change repository
     * @param cache the inspection cache
     */
    public StandardInspectionService(
            @NotNull AuditRepository auditRepository,
            @NotNull BlockChangeRepository blockChangeRepository,
            @NotNull InspectionCache cache) {
        this(auditRepository, blockChangeRepository, cache, null);
    }

    /**
     * Constructs a new standard inspection service with a shared audit cache.
     *
     * @param auditRepository the audit repository
     * @param blockChangeRepository the block change repository
     * @param cache the inspection cache
     * @param auditCache the shared audit cache of recent un-flushed events
     */
    public StandardInspectionService(
            @NotNull AuditRepository auditRepository,
            @NotNull BlockChangeRepository blockChangeRepository,
            @NotNull InspectionCache cache,
            @Nullable AuditCache auditCache) {
        this.auditRepository = auditRepository;
        this.blockChangeRepository = blockChangeRepository;
        this.cache = cache;
        this.auditCache = auditCache;
        this.executor = Executors.newVirtualThreadPerTaskExecutor();
    }

    /**
     * Gets the audit history for a specific block location.
     *
     * @param location the block location to inspect
     * @param limit the maximum number of events to return
     * @return a future containing the block's audit history
     */
    @Override
    public @NotNull CompletableFuture<List<AuditEvent>> inspectBlock(@NotNull Location location, int limit) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    LocationKey key = LocationKey.from(location);
                    InspectionResult cached = cache.get(key);
                    if (cached != null && cached.events().size() >= limit) {
                        return cached.events().subList(0, limit);
                    }
                    List<AuditEvent> cachedEvents = auditCache != null
                            ? auditCache.get(dev.sentinel.audit.api.AuditQuery.builder()
                                    .location(location)
                                    .limit(limit)
                                    .build())
                            : List.of();
                    List<AuditEvent> stored =
                            auditRepository
                                    .findByLocation(location.getWorld().getName(), key.x(), key.y(), key.z(), limit)
                                    .stream()
                                    .map(AuditRecord::toEvent)
                                    .toList();
                    return merge(cachedEvents, stored, limit);
                },
                executor);
    }

    /**
     * Gets the audit history for a region defined by two corners.
     *
     * @param firstCorner the first corner of the region
     * @param secondCorner the second corner of the region
     * @param limit the maximum number of events to return
     * @return a future containing the region's audit history
     */
    @Override
    public @NotNull CompletableFuture<List<AuditEvent>> inspectRegion(
            @NotNull Location firstCorner, @NotNull Location secondCorner, int limit) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    int minX = Math.min(firstCorner.getBlockX(), secondCorner.getBlockX());
                    int maxX = Math.max(firstCorner.getBlockX(), secondCorner.getBlockX());
                    int minY = Math.min(firstCorner.getBlockY(), secondCorner.getBlockY());
                    int maxY = Math.max(firstCorner.getBlockY(), secondCorner.getBlockY());
                    int minZ = Math.min(firstCorner.getBlockZ(), secondCorner.getBlockZ());
                    int maxZ = Math.max(firstCorner.getBlockZ(), secondCorner.getBlockZ());

                    String worldName = firstCorner.getWorld().getName();
                    List<dev.sentinel.audit.database.model.BlockChangeRecord> changes = blockChangeRepository
                            .findByRegion(
                                    worldName,
                                    minX,
                                    minY,
                                    minZ,
                                    maxX,
                                    maxY,
                                    maxZ,
                                    java.time.Instant.now().minus(java.time.Duration.ofDays(30)),
                                    java.time.Instant.now())
                            .stream()
                            .limit(limit)
                            .toList();
                    if (changes.isEmpty()) {
                        return List.of();
                    }
                    List<dev.sentinel.audit.database.model.AuditRecord> records =
                            auditRepository.findByIds(changes.stream()
                                    .map(dev.sentinel.audit.database.model.BlockChangeRecord::auditEventId)
                                    .toList());
                    java.util.Map<java.util.UUID, AuditEvent> byId = records.stream()
                            .map(dev.sentinel.audit.database.model.AuditRecord::toEvent)
                            .collect(java.util.stream.Collectors.toMap(AuditEvent::id, event -> event));
                    return changes.stream()
                            .map(change -> byId.get(change.auditEventId()))
                            .filter(java.util.Objects::nonNull)
                            .toList();
                },
                executor);
    }

    /**
     * Gets the most recent event for a specific block.
     *
     * @param location the block location
     * @return a future containing the most recent event, or empty if none
     */
    @Override
    public @NotNull CompletableFuture<AuditEvent> getLatestEvent(@NotNull Location location) {
        requirePremium();
        return CompletableFuture.supplyAsync(
                () -> {
                    LocationKey key = LocationKey.from(location);
                    return auditRepository
                            .findLatestAt(location.getWorld().getName(), key.x(), key.y(), key.z())
                            .map(record -> record.toEvent())
                            .orElse(null);
                },
                executor);
    }

    /**
     * Shuts down the virtual thread executor.
     */
    public void shutdown() {
        executor.shutdown();
    }

    /**
     * Rejects any use of this premium service when running the free Lite edition,
     * closing the gap where the public API could be invoked directly (bypassing the
     * command-level edition check).
     */
    private void requirePremium() {
        if (dev.sentinel.audit.Edition.load().isLite()) {
            throw new UnsupportedOperationException("Inspection is not available in Sentinel Lite");
        }
    }

    /**
     * Merges cached (un-flushed) and stored events, most recent first, without
     * duplicating events by ID.
     *
     * @param cachedEvents events still pending persistence
     * @param storedEvents events persisted to the database
     * @param limit the maximum number of events to return
     * @return the merged, deduplicated event list
     */
    @NotNull
    private List<AuditEvent> merge(
            @NotNull List<AuditEvent> cachedEvents, @NotNull List<AuditEvent> storedEvents, int limit) {
        List<AuditEvent> merged = new ArrayList<>(cachedEvents);
        java.util.Set<java.util.UUID> seen = cachedEvents.stream()
                .map(dev.sentinel.audit.api.AuditEvent::id)
                .collect(java.util.stream.Collectors.toSet());
        for (AuditEvent event : storedEvents) {
            if (seen.add(event.id())) {
                merged.add(event);
            }
        }
        merged.sort(java.util.Comparator.comparing(dev.sentinel.audit.api.AuditEvent::timestamp)
                .reversed());
        return merged.size() > limit ? List.copyOf(merged).subList(0, limit) : List.copyOf(merged);
    }
}
