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

import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.bukkit.Location;
import org.jetbrains.annotations.NotNull;

/**
 * Service interface for rolling back audited changes.
 *
 * <p>Provides methods to restore block states and inventory contents
 * to previous states based on audit history.</p>
 */
public interface RollbackService {

    /**
     * Rolls back all changes made by a specific actor within a time range.
     *
     * @param actorId the UUID of the actor whose changes to roll back
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of changes rolled back
     */
    @NotNull
    CompletableFuture<Integer> rollbackActor(@NotNull UUID actorId, @NotNull Instant from, @NotNull Instant to);

    /**
     * Rolls back all changes within a region and time range.
     *
     * @param firstCorner the first corner of the region
     * @param secondCorner the second corner of the region
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of changes rolled back
     */
    @NotNull
    CompletableFuture<Integer> rollbackRegion(
            @NotNull Location firstCorner, @NotNull Location secondCorner, @NotNull Instant from, @NotNull Instant to);

    /**
     * Rolls back all changes within a world and time range.
     *
     * @param worldName the name of the world to roll back
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of changes rolled back
     */
    @NotNull
    CompletableFuture<Integer> rollbackWorld(@NotNull String worldName, @NotNull Instant from, @NotNull Instant to);

    /**
     * Rolls back a single audit event by its ID.
     *
     * @param eventId the ID of the event to roll back
     * @return a future that completes when the rollback is done
     */
    @NotNull
    CompletableFuture<Void> rollbackEvent(@NotNull UUID eventId);

    /**
     * Restores a single block to its state before the given event.
     *
     * @param location the block location
     * @param eventId the event ID to restore before
     * @return a future that completes when the restore is done
     */
    @NotNull
    CompletableFuture<Void> restoreBlock(@NotNull Location location, @NotNull UUID eventId);

    /**
     * Restores captured inventory items back to a player.
     *
     * @param playerId the UUID of the player to restore items to
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of items restored
     */
    @NotNull
    CompletableFuture<Integer> rollbackInventory(@NotNull UUID playerId, @NotNull Instant from, @NotNull Instant to);

    /**
     * Restores environment-lost item entities (despawned, voided, or destroyed)
     * captured for a world back to a recipient player.
     *
     * @param worldName the world whose item losses to restore
     * @param recipientId the UUID of the online player to give the items to
     * @param from the start of the time range
     * @param to the end of the time range
     * @return a future containing the number of items restored
     */
    @NotNull
    CompletableFuture<Integer> rollbackWorldInventory(
            @NotNull String worldName, @NotNull UUID recipientId, @NotNull Instant from, @NotNull Instant to);
}
