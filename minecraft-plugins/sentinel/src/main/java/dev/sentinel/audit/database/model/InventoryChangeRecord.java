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
package dev.sentinel.audit.database.model;

import dev.sentinel.audit.models.InventorySnapshot;
import java.time.Instant;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Database entity representing an inventory change record.
 *
 * <p>Stores the before and after states of an inventory change for
 * inspection and rollback purposes.</p>
 *
 * @param id the unique record ID
 * @param auditEventId the associated audit event ID
 * @param inventoryId the inventory identifier
 * @param before the inventory state before the change
 * @param after the inventory state after the change
 * @param timestamp the time of the change
 */
public record InventoryChangeRecord(
        @NotNull UUID id,
        @NotNull UUID auditEventId,
        @NotNull String inventoryId,
        @NotNull InventorySnapshot before,
        @NotNull InventorySnapshot after,
        @NotNull Instant timestamp) {

    /**
     * Creates a new inventory change record.
     *
     * @param auditEventId the associated audit event ID
     * @param inventoryId the inventory identifier
     * @param before the before state
     * @param after the after state
     * @return a new inventory change record
     */
    public static InventoryChangeRecord of(
            @NotNull UUID auditEventId,
            @NotNull String inventoryId,
            @NotNull InventorySnapshot before,
            @NotNull InventorySnapshot after) {
        return new InventoryChangeRecord(UUID.randomUUID(), auditEventId, inventoryId, before, after, Instant.now());
    }
}
