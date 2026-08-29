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
package dev.sentinel.audit.util;

import dev.sentinel.audit.models.LocationKey;
import java.util.Objects;
import org.bukkit.Location;
import org.bukkit.World;
import org.jetbrains.annotations.NotNull;

/**
 * Utility for location conversions and calculations.
 *
 * <p>Provides helpers for converting between Bukkit locations and
 * location keys, and calculating regions.</p>
 */
public final class LocationUtil {

    private LocationUtil() {}

    /**
     * Converts a location to a location key.
     *
     * @param location the location
     * @return the location key
     */
    public static LocationKey toKey(@NotNull Location location) {
        return LocationKey.from(location);
    }

    /**
     * Serializes a location to a string key.
     *
     * @param location the location
     * @return the serialized key
     */
    public static String serialize(@NotNull Location location) {
        return LocationKey.from(location).toString();
    }

    /**
     * Checks if two locations are at the same block position.
     *
     * @param first the first location
     * @param second the second location
     * @return true if they are at the same block position
     */
    public static boolean sameBlock(@NotNull Location first, @NotNull Location second) {
        if (!Objects.equals(first.getWorld(), second.getWorld())) {
            return false;
        }
        return first.getBlockX() == second.getBlockX()
                && first.getBlockY() == second.getBlockY()
                && first.getBlockZ() == second.getBlockZ();
    }

    /**
     * Gets the minimum corner of a region defined by two points.
     *
     * @param first the first corner
     * @param second the second corner
     * @return the minimum corner
     */
    public static Location min(@NotNull Location first, @NotNull Location second) {
        World world = first.getWorld() != null ? first.getWorld() : second.getWorld();
        return new Location(
                world,
                Math.min(first.getBlockX(), second.getBlockX()),
                Math.min(first.getBlockY(), second.getBlockY()),
                Math.min(first.getBlockZ(), second.getBlockZ()));
    }

    /**
     * Gets the maximum corner of a region defined by two points.
     *
     * @param first the first corner
     * @param second the second corner
     * @return the maximum corner
     */
    public static Location max(@NotNull Location first, @NotNull Location second) {
        World world = first.getWorld() != null ? first.getWorld() : second.getWorld();
        return new Location(
                world,
                Math.max(first.getBlockX(), second.getBlockX()),
                Math.max(first.getBlockY(), second.getBlockY()),
                Math.max(first.getBlockZ(), second.getBlockZ()));
    }
}
