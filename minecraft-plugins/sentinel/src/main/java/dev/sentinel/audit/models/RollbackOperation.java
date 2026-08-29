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
package dev.sentinel.audit.models;

import java.time.Instant;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable model representing a rollback operation.
 *
 * <p>Tracks the state and progress of a rollback operation from
 * initiation through completion.</p>
 *
 * @param id the unique operation ID
 * @param actorId the UUID of the actor who initiated the rollback
 * @param actorName the name of the actor who initiated the rollback
 * @param status the current status of the operation
 * @param blocksRestored the number of blocks restored so far
 * @param totalBlocks the total number of blocks to restore
 * @param startedAt the time the operation started
 * @param completedAt the time the operation completed, if finished
 */
public record RollbackOperation(
        @NotNull UUID id,
        @NotNull UUID actorId,
        @NotNull String actorName,
        @NotNull RollbackStatus status,
        int blocksRestored,
        int totalBlocks,
        @NotNull Instant startedAt,
        Instant completedAt) {

    /**
     * Creates a new rollback operation in the PENDING state.
     *
     * @param actorId the actor UUID
     * @param actorName the actor name
     * @param totalBlocks the total blocks to restore
     * @return a new pending rollback operation
     */
    public static RollbackOperation pending(@NotNull UUID actorId, @NotNull String actorName, int totalBlocks) {
        return new RollbackOperation(
                UUID.randomUUID(), actorId, actorName, RollbackStatus.PENDING, 0, totalBlocks, Instant.now(), null);
    }

    /**
     * Returns a copy of this operation with the given status.
     *
     * @param newStatus the new status
     * @return an updated operation
     */
    public RollbackOperation withStatus(@NotNull RollbackStatus newStatus) {
        return new RollbackOperation(
                id, actorId, actorName, newStatus, blocksRestored, totalBlocks, startedAt, completedAt);
    }

    /**
     * Returns a copy of this operation with updated progress.
     *
     * @param restored the number of blocks restored
     * @return an updated operation
     */
    public RollbackOperation withProgress(int restored) {
        return new RollbackOperation(id, actorId, actorName, status, restored, totalBlocks, startedAt, completedAt);
    }

    /**
     * Returns a copy of this operation marked as completed.
     *
     * @return a completed operation
     */
    public RollbackOperation completed() {
        return new RollbackOperation(
                id,
                actorId,
                actorName,
                RollbackStatus.COMPLETED,
                blocksRestored,
                totalBlocks,
                startedAt,
                Instant.now());
    }

    /**
     * Returns a copy of this operation marked as failed.
     *
     * @return a failed operation
     */
    public RollbackOperation failed() {
        return new RollbackOperation(
                id, actorId, actorName, RollbackStatus.FAILED, blocksRestored, totalBlocks, startedAt, Instant.now());
    }
}
