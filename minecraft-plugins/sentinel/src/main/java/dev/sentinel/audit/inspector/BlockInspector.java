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
package dev.sentinel.audit.inspector;

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.api.InspectionService;
import dev.sentinel.audit.api.dto.InspectionResult;
import dev.sentinel.audit.models.LocationKey;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.bukkit.Location;
import org.jetbrains.annotations.NotNull;

/**
 * Inspects block history in the game world.
 *
 * <p>Provides block inspection capabilities backed by the
 * inspection service, with caching support.</p>
 */
public final class BlockInspector {

    private final InspectionService inspectionService;

    /**
     * Constructs a new block inspector.
     *
     * @param inspectionService the inspection service
     */
    public BlockInspector(@NotNull InspectionService inspectionService) {
        this.inspectionService = inspectionService;
    }

    /**
     * Inspects a block at the given location.
     *
     * @param location the block location
     * @param limit the maximum number of history events
     * @return a future containing the inspection result
     */
    public CompletableFuture<InspectionResult> inspect(@NotNull Location location, int limit) {
        return inspectionService
                .inspectBlock(location, limit)
                .thenApply(
                        events -> InspectionResult.of(LocationKey.from(location).toString(), events));
    }

    /**
     * Gets the full audit history for a block.
     *
     * @param location the block location
     * @param limit the maximum number of events
     * @return a future containing the audit events
     */
    public CompletableFuture<List<AuditEvent>> getHistory(@NotNull Location location, int limit) {
        return inspectionService.inspectBlock(location, limit);
    }

    /**
     * Gets the most recent event for a block.
     *
     * @param location the block location
     * @return a future containing the most recent event
     */
    public CompletableFuture<AuditEvent> getLatest(@NotNull Location location) {
        return inspectionService.getLatestEvent(location);
    }
}
