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

import org.bukkit.Location;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable key representing a block location for indexing and lookup.
 *
 * <p>Provides a compact, hashable representation of a block position
 * within a specific world.</p>
 *
 * @param worldName the name of the world
 * @param x the X coordinate
 * @param y the Y coordinate
 * @param z the Z coordinate
 */
public record LocationKey(@NotNull String worldName, int x, int y, int z) {

    /**
     * Creates a location key from a Bukkit location.
     *
     * @param location the location to convert
     * @return a new location key
     */
    public static LocationKey from(@NotNull Location location) {
        String world = location.getWorld() != null ? location.getWorld().getName() : "unknown";
        return new LocationKey(world, location.getBlockX(), location.getBlockY(), location.getBlockZ());
    }

    /**
     * Creates a location key from raw coordinates.
     *
     * @param worldName the world name
     * @param x the X coordinate
     * @param y the Y coordinate
     * @param z the Z coordinate
     * @return a new location key
     */
    public static LocationKey of(@NotNull String worldName, int x, int y, int z) {
        return new LocationKey(worldName, x, y, z);
    }

    /**
     * Returns a string representation of this location key.
     *
     * @return the string representation
     */
    @Override
    public String toString() {
        return worldName + ":" + x + "," + y + "," + z;
    }
}
