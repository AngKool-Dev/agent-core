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

import dev.sentinel.audit.models.AuditAction;
import dev.sentinel.audit.models.AuditSource;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/**
 * Represents an audit event that occurred in the game world.
 *
 * <p>This is an immutable value object describing a single auditable action,
 * including the actor, target, location, and associated metadata.</p>
 *
 * @param id the unique identifier of the audit event
 * @param action the type of action performed
 * @param source the source of the audit event
 * @param actorId the UUID of the actor (player or entity)
 * @param actorName the display name of the actor
 * @param targetId the UUID of the target entity, if applicable
 * @param targetName the display name of the target, if applicable
 * @param location the location where the event occurred
 * @param worldName the name of the world where the event occurred
 * @param timestamp the time the event occurred
 * @param metadata additional contextual data about the event
 */
public record AuditEvent(
        @NotNull UUID id,
        @NotNull AuditAction action,
        @NotNull AuditSource source,
        @NotNull UUID actorId,
        @NotNull String actorName,
        @Nullable UUID targetId,
        @Nullable String targetName,
        @NotNull Location location,
        @NotNull String worldName,
        @NotNull Instant timestamp,
        @NotNull Map<String, String> metadata) {

    /**
     * Creates a new audit event for a player action.
     *
     * @param action the action performed
     * @param player the player who performed the action
     * @param location the location of the event
     * @param metadata additional metadata
     * @return a new audit event
     */
    public static AuditEvent ofPlayer(
            @NotNull AuditAction action,
            @NotNull Player player,
            @NotNull Location location,
            @NotNull Map<String, String> metadata) {
        return new AuditEvent(
                UUID.randomUUID(),
                action,
                AuditSource.PLAYER,
                player.getUniqueId(),
                player.getName(),
                null,
                null,
                location,
                location.getWorld() != null ? location.getWorld().getName() : "unknown",
                Instant.now(),
                metadata);
    }

    /**
     * Creates a new audit event for a console action.
     *
     * @param action the action performed
     * @param location the location of the event
     * @param metadata additional metadata
     * @return a new audit event
     */
    public static AuditEvent ofConsole(
            @NotNull AuditAction action, @NotNull Location location, @NotNull Map<String, String> metadata) {
        return new AuditEvent(
                UUID.randomUUID(),
                action,
                AuditSource.CONSOLE,
                UUID.fromString("00000000-0000-0000-0000-000000000000"),
                "CONSOLE",
                null,
                null,
                location,
                location.getWorld() != null ? location.getWorld().getName() : "unknown",
                Instant.now(),
                metadata);
    }
}
