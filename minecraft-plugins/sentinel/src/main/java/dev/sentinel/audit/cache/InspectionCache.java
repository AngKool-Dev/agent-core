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

import dev.sentinel.audit.api.dto.InspectionResult;
import dev.sentinel.audit.models.LocationKey;
import java.util.concurrent.ConcurrentHashMap;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/**
 * In-memory cache for block inspection results.
 *
 * <p>Caches recent inspection results keyed by block location to
 * provide fast responses for repeat inspections.</p>
 */
public final class InspectionCache {

    private final ConcurrentHashMap<LocationKey, InspectionResult> cache;
    private final int maxEntries;

    /**
     * Constructs a new inspection cache.
     *
     * @param maxEntries the maximum number of cached entries
     */
    public InspectionCache(int maxEntries) {
        this.cache = new ConcurrentHashMap<>();
        this.maxEntries = maxEntries;
    }

    /**
     * Caches an inspection result for a location.
     *
     * @param location the block location
     * @param result the inspection result
     */
    public void put(@NotNull LocationKey location, @NotNull InspectionResult result) {
        if (cache.size() >= maxEntries) {
            evictOldest();
        }
        cache.put(location, result);
    }

    /**
     * Gets a cached inspection result for a location.
     *
     * @param location the block location
     * @return the cached result, or null if not present
     */
    @Nullable
    public InspectionResult get(@NotNull LocationKey location) {
        return cache.get(location);
    }

    /**
     * Invalidates a cached entry for a location.
     *
     * @param location the block location
     */
    public void invalidate(@NotNull LocationKey location) {
        cache.remove(location);
    }

    /**
     * Clears the entire inspection cache.
     */
    public void clear() {
        cache.clear();
    }

    /**
     * Gets the current cache size.
     *
     * @return the number of cached results
     */
    public int size() {
        return cache.size();
    }

    /**
     * Evicts the oldest entries when the cache is full.
     */
    private void evictOldest() {
        if (cache.isEmpty()) {
            return;
        }
        java.util.Map.Entry<LocationKey, InspectionResult> oldest =
                cache.entrySet().iterator().next();
        cache.remove(oldest.getKey());
    }
}
