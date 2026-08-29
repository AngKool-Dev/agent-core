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

import java.time.Instant;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable result of a rollback operation.
 *
 * <p>Contains statistics about the rollback including the number of
 * blocks restored and the time taken.</p>
 *
 * @param operationId the unique ID of the rollback operation
 * @param blocksRestored the number of blocks restored
 * @param eventsProcessed the number of audit events processed
 * @param startedAt the time the rollback started
 * @param completedAt the time the rollback completed
 * @param durationMs the duration of the rollback in milliseconds
 */
public record RollbackResult(
        @NotNull UUID operationId,
        int blocksRestored,
        int eventsProcessed,
        @NotNull Instant startedAt,
        @NotNull Instant completedAt,
        long durationMs) {

    /**
     * Creates a rollback result with the given data.
     *
     * @param blocksRestored the number of blocks restored
     * @param eventsProcessed the number of events processed
     * @param startedAt the start time
     * @param completedAt the completion time
     * @return a new rollback result
     */
    public static RollbackResult of(
            int blocksRestored, int eventsProcessed, @NotNull Instant startedAt, @NotNull Instant completedAt) {
        return new RollbackResult(
                UUID.randomUUID(),
                blocksRestored,
                eventsProcessed,
                startedAt,
                completedAt,
                java.time.Duration.between(startedAt, completedAt).toMillis());
    }
}
