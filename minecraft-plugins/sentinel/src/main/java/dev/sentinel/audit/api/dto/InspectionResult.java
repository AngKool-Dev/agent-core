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
package dev.sentinel.audit.api.dto;

import dev.sentinel.audit.api.AuditEvent;
import java.util.List;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable result of a block inspection.
 *
 * <p>Contains the audit history for an inspected block along with
 * summary statistics.</p>
 *
 * @param locationKey the string representation of the inspected location
 * @param events the audit events for the block, most recent first
 * @param totalEvents the total number of events for the block
 * @param firstSeen the timestamp of the first recorded event
 * @param lastSeen the timestamp of the most recent event
 */
public record InspectionResult(
        @NotNull String locationKey, @NotNull List<AuditEvent> events, int totalEvents, long firstSeen, long lastSeen) {

    /**
     * Creates an inspection result with the given data.
     *
     * @param locationKey the location key
     * @param events the audit events
     * @return a new inspection result
     */
    public static InspectionResult of(@NotNull String locationKey, @NotNull List<AuditEvent> events) {
        long firstSeen = events.isEmpty()
                ? 0L
                : events.get(events.size() - 1).timestamp().toEpochMilli();
        long lastSeen = events.isEmpty() ? 0L : events.get(0).timestamp().toEpochMilli();
        return new InspectionResult(locationKey, List.copyOf(events), events.size(), firstSeen, lastSeen);
    }
}
