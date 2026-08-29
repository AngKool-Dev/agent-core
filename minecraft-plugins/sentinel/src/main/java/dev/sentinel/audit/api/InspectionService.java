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

import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.bukkit.Location;
import org.jetbrains.annotations.NotNull;

/**
 * Service interface for inspecting block history.
 *
 * <p>Provides methods to query the audit history of specific blocks
 * and locations in the game world.</p>
 */
public interface InspectionService {

    /**
     * Gets the audit history for a specific block location.
     *
     * @param location the block location to inspect
     * @param limit the maximum number of events to return
     * @return a future containing the block's audit history
     */
    @NotNull
    CompletableFuture<List<AuditEvent>> inspectBlock(@NotNull Location location, int limit);

    /**
     * Gets the audit history for a region defined by two corners.
     *
     * @param firstCorner the first corner of the region
     * @param secondCorner the second corner of the region
     * @param limit the maximum number of events to return
     * @return a future containing the region's audit history
     */
    @NotNull
    CompletableFuture<List<AuditEvent>> inspectRegion(
            @NotNull Location firstCorner, @NotNull Location secondCorner, int limit);

    /**
     * Gets the most recent event for a specific block.
     *
     * @param location the block location
     * @return a future containing the most recent event, or empty if none
     */
    @NotNull
    CompletableFuture<AuditEvent> getLatestEvent(@NotNull Location location);
}
