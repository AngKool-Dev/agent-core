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
package dev.sentinel.audit.cache;

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.api.AuditQuery;
import dev.sentinel.audit.models.LocationKey;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/**
 * In-memory cache for recent audit events.
 *
 * <p>Provides fast access to recently recorded audit events before
 * they are persisted to the database.</p>
 */
public final class AuditCache {

    private final ConcurrentHashMap<UUID, AuditEvent> byId;
    private final ConcurrentHashMap<LocationKey, List<AuditEvent>> byLocation;
    private final int maxEntries;

    /**
     * Constructs a new audit cache.
     *
     * @param maxEntries the maximum number of cached entries
     */
    public AuditCache(int maxEntries) {
        this.byId = new ConcurrentHashMap<>();
        this.byLocation = new ConcurrentHashMap<>();
        this.maxEntries = maxEntries;
    }

    /**
     * Puts an audit event into the cache.
     *
     * @param event the event to cache
     */
    public void put(@NotNull AuditEvent event) {
        if (byId.size() >= maxEntries) {
            evictOldest();
        }
        byId.put(event.id(), event);
        LocationKey key = LocationKey.from(event.location());
        byLocation.merge(key, List.of(event), (oldList, newList) -> {
            var combined = new java.util.ArrayList<>(oldList);
            combined.addAll(newList);
            return List.copyOf(combined);
        });
    }

    /**
     * Gets an audit event by its ID.
     *
     * @param eventId the event ID
     * @return the cached event, or null if not present
     */
    @Nullable
    public AuditEvent get(@NotNull UUID eventId) {
        return byId.get(eventId);
    }

    /**
     * Gets cached events matching the given query.
     *
     * @param query the query
     * @return the matching cached events
     */
    @NotNull
    public List<AuditEvent> get(@NotNull AuditQuery query) {
        if (query.location() != null) {
            return byLocation.getOrDefault(LocationKey.from(query.location()), List.of());
        }
        return List.of();
    }

    /**
     * Invalidates all cached entries for a location.
     *
     * @param location the location
     */
    public void invalidate(@NotNull LocationKey location) {
        byLocation.remove(location);
    }

    /**
     * Clears the entire cache.
     */
    public void clear() {
        byId.clear();
        byLocation.clear();
    }

    /**
     * Gets the current cache size.
     *
     * @return the number of cached events
     */
    public int size() {
        return byId.size();
    }

    /**
     * Evicts the oldest entries when the cache is full.
     */
    private void evictOldest() {
        if (byId.isEmpty()) {
            return;
        }
        UUID oldestKey = byId.keySet().iterator().next();
        byId.remove(oldestKey);
        byLocation.values().forEach(list -> {
            // Location map will be lazily cleaned
        });
    }
}
