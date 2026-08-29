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

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.models.AuditAction;
import dev.sentinel.audit.models.AuditSource;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.jetbrains.annotations.NotNull;

/**
 * Database entity representing an audit record.
 *
 * <p>Maps an {@link AuditEvent} to a database row for persistence.</p>
 *
 * @param id the unique record ID
 * @param action the audit action
 * @param source the audit source
 * @param actorId the actor UUID
 * @param actorName the actor name
 * @param targetId the target UUID, if any
 * @param targetName the target name, if any
 * @param worldName the world name
 * @param x the X coordinate
 * @param y the Y coordinate
 * @param z the Z coordinate
 * @param timestamp the event timestamp
 * @param metadata the serialized metadata
 */
public record AuditRecord(
        @NotNull UUID id,
        @NotNull AuditAction action,
        @NotNull AuditSource source,
        @NotNull UUID actorId,
        @NotNull String actorName,
        UUID targetId,
        String targetName,
        @NotNull String worldName,
        int x,
        int y,
        int z,
        @NotNull Instant timestamp,
        @NotNull String metadata) {

    /**
     * Converts an audit event to a database record.
     *
     * @param event the audit event
     * @return the database record
     */
    public static AuditRecord from(@NotNull AuditEvent event) {
        return new AuditRecord(
                event.id(),
                event.action(),
                event.source(),
                event.actorId(),
                event.actorName(),
                event.targetId(),
                event.targetName(),
                event.worldName(),
                event.location().getBlockX(),
                event.location().getBlockY(),
                event.location().getBlockZ(),
                event.timestamp(),
                serializeMetadata(event.metadata()));
    }

    /**
     * Converts this database record back to an audit event.
     *
     * @return the audit event
     */
    public AuditEvent toEvent() {
        return new AuditEvent(
                id,
                action,
                source,
                actorId,
                actorName,
                targetId,
                targetName,
                new org.bukkit.Location(org.bukkit.Bukkit.getWorld(worldName), x, y, z),
                worldName,
                timestamp,
                deserializeMetadata(metadata));
    }

    /**
     * Serializes metadata to a JSON string.
     *
     * @param metadata the metadata map
     * @return the serialized JSON
     */
    private static String serializeMetadata(@NotNull Map<String, String> metadata) {
        return dev.sentinel.audit.util.JsonUtil.toJson(metadata);
    }

    /**
     * Deserializes metadata from a JSON string.
     *
     * @param json the serialized JSON
     * @return the metadata map
     */
    private static Map<String, String> deserializeMetadata(@NotNull String json) {
        return dev.sentinel.audit.util.JsonUtil.toMap(json);
    }
}
