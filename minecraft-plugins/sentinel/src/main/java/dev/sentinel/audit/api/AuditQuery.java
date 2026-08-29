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
import java.time.Instant;
import java.util.UUID;
import org.bukkit.Location;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/**
 * Immutable query parameters for filtering audit records.
 *
 * <p>All fields are optional; null values mean "no filter" for that criterion.</p>
 *
 * @param actorId the UUID of the actor to filter by
 * @param action the action type to filter by
 * @param worldName the world name to filter by
 * @param location the location to filter by (exact match)
 * @param from the earliest timestamp (inclusive)
 * @param to the latest timestamp (inclusive)
 * @param limit the maximum number of results
 * @param offset the pagination offset
 */
public record AuditQuery(
        @Nullable UUID actorId,
        @Nullable AuditAction action,
        @Nullable String worldName,
        @Nullable Location location,
        @Nullable Instant from,
        @Nullable Instant to,
        int limit,
        int offset) {

    /**
     * Creates a new query builder.
     *
     * @return a new builder instance
     */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Builder for {@link AuditQuery}.
     */
    public static final class Builder {

        private UUID actorId;
        private AuditAction action;
        private String worldName;
        private Location location;
        private Instant from;
        private Instant to;
        private int limit = 100;
        private int offset = 0;

        private Builder() {}

        /**
         * Sets the actor ID filter.
         *
         * @param actorId the actor UUID
         * @return this builder
         */
        public Builder actorId(@NotNull UUID actorId) {
            this.actorId = actorId;
            return this;
        }

        /**
         * Sets the action filter.
         *
         * @param action the action type
         * @return this builder
         */
        public Builder action(@NotNull AuditAction action) {
            this.action = action;
            return this;
        }

        /**
         * Sets the world name filter.
         *
         * @param worldName the world name
         * @return this builder
         */
        public Builder worldName(@NotNull String worldName) {
            this.worldName = worldName;
            return this;
        }

        /**
         * Sets the location filter.
         *
         * @param location the location
         * @return this builder
         */
        public Builder location(@NotNull Location location) {
            this.location = location;
            return this;
        }

        /**
         * Sets the earliest timestamp filter.
         *
         * @param from the earliest timestamp
         * @return this builder
         */
        public Builder from(@NotNull Instant from) {
            this.from = from;
            return this;
        }

        /**
         * Sets the latest timestamp filter.
         *
         * @param to the latest timestamp
         * @return this builder
         */
        public Builder to(@NotNull Instant to) {
            this.to = to;
            return this;
        }

        /**
         * Sets the result limit.
         *
         * @param limit the maximum results
         * @return this builder
         */
        public Builder limit(int limit) {
            this.limit = limit;
            return this;
        }

        /**
         * Sets the pagination offset.
         *
         * @param offset the offset
         * @return this builder
         */
        public Builder offset(int offset) {
            this.offset = offset;
            return this;
        }

        /**
         * Builds the query.
         *
         * @return the immutable query
         */
        public AuditQuery build() {
            return new AuditQuery(actorId, action, worldName, location, from, to, limit, offset);
        }
    }
}
