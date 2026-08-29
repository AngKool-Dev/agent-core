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
package dev.sentinel.audit.rollback;

import dev.sentinel.audit.models.RollbackOperation;
import dev.sentinel.audit.models.RollbackStatus;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.jetbrains.annotations.NotNull;

/**
 * Manages rollback operation lifecycle and state.
 *
 * <p>Tracks active and completed rollback operations, providing
 * lookup and progress monitoring capabilities.</p>
 */
public final class RollbackManager {

    private final Map<UUID, RollbackOperation> operations;

    /**
     * Constructs a new rollback manager.
     */
    public RollbackManager() {
        this.operations = new ConcurrentHashMap<>();
    }

    /**
     * Registers a new rollback operation.
     *
     * @param operation the operation to register
     */
    public void register(@NotNull RollbackOperation operation) {
        operations.put(operation.id(), operation);
    }

    /**
     * Updates the state of a rollback operation.
     *
     * @param operation the updated operation
     */
    public void update(@NotNull RollbackOperation operation) {
        operations.put(operation.id(), operation);
    }

    /**
     * Gets a rollback operation by its ID.
     *
     * @param operationId the operation ID
     * @return the operation, or null if not found
     */
    public RollbackOperation get(@NotNull UUID operationId) {
        return operations.get(operationId);
    }

    /**
     * Gets all operations with the given status.
     *
     * @param status the status to filter by
     * @return the matching operations
     */
    public java.util.List<RollbackOperation> getByStatus(@NotNull RollbackStatus status) {
        return operations.values().stream().filter(op -> op.status() == status).toList();
    }

    /**
     * Removes an operation from tracking.
     *
     * @param operationId the operation ID
     */
    public void remove(@NotNull UUID operationId) {
        operations.remove(operationId);
    }

    /**
     * Clears all tracked operations.
     */
    public void clear() {
        operations.clear();
    }

    /**
     * Gets the number of tracked operations.
     *
     * @return the operation count
     */
    public int size() {
        return operations.size();
    }
}
