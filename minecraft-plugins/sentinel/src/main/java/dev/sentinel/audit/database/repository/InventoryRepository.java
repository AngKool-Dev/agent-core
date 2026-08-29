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
package dev.sentinel.audit.database.repository;

import dev.sentinel.audit.database.model.InventoryChangeRecord;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Repository interface for inventory change record persistence.
 *
 * <p>Defines the data access operations for storing and querying
 * inventory change records for inspection and rollback.</p>
 */
public interface InventoryRepository {

    /**
     * Inserts a batch of inventory change records.
     *
     * @param records the records to insert
     */
    void insertBatch(@NotNull List<InventoryChangeRecord> records);

    /**
     * Gets all inventory changes for a specific inventory.
     *
     * @param inventoryId the inventory identifier
     * @param limit the maximum number of records
     * @return the inventory change records, most recent first
     */
    @NotNull
    List<InventoryChangeRecord> findByInventoryId(@NotNull String inventoryId, int limit);

    /**
     * Gets all item-loss inventory changes captured for a world within a time range.
     *
     * @param worldName the world name
     * @param from the start of the time range
     * @param to the end of the time range
     * @return the inventory change records, most recent first
     */
    @NotNull
    List<InventoryChangeRecord> findWorldLosses(@NotNull String worldName, @NotNull Instant from, @NotNull Instant to);

    /**
     * Gets all inventory changes associated with an audit event.
     *
     * @param auditEventId the audit event ID
     * @return the inventory change records
     */
    @NotNull
    List<InventoryChangeRecord> findByAuditEvent(@NotNull UUID auditEventId);
}
