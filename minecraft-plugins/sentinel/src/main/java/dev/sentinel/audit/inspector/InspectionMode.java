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
package dev.sentinel.audit.inspector;

import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.jetbrains.annotations.NotNull;

/**
 * Tracks which players currently have inspection mode enabled.
 *
 * <p>While inspection mode is active, right-clicking a block shows the
 * block's audit history instead of interacting with the block.</p>
 */
public final class InspectionMode {

    private final Set<UUID> activeInspectors = ConcurrentHashMap.newKeySet();

    /**
     * Checks whether inspection mode is active for a player.
     *
     * @param playerId the player UUID
     * @return true if inspection mode is active
     */
    public boolean isActive(@NotNull UUID playerId) {
        return activeInspectors.contains(playerId);
    }

    /**
     * Enables or disables inspection mode for a player.
     *
     * @param playerId the player UUID
     * @param enabled whether inspection mode should be active
     * @return true if the state changed
     */
    public boolean set(@NotNull UUID playerId, boolean enabled) {
        if (enabled) {
            return activeInspectors.add(playerId);
        }
        return activeInspectors.remove(playerId);
    }

    /**
     * Toggles inspection mode for a player.
     *
     * @param playerId the player UUID
     * @return true if inspection mode is now active
     */
    public boolean toggle(@NotNull UUID playerId) {
        if (activeInspectors.add(playerId)) {
            return true;
        }
        activeInspectors.remove(playerId);
        return false;
    }

    /**
     * Removes all active inspectors.
     */
    public void clear() {
        activeInspectors.clear();
    }
}
