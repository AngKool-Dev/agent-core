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

import dev.sentinel.audit.util.TileEntityUtil;
import java.util.Map;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.BlockData;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable snapshot of a block's state at a point in time.
 *
 * <p>Captures the material, block data, and any tile entity data
 * needed to restore a block to a previous state.</p>
 *
 * @param material the block material
 * @param blockData the serialized block data
 * @param tileEntityData the serialized tile entity data, if any
 * @param properties additional block properties
 */
public record BlockSnapshot(
        @NotNull Material material,
        @NotNull String blockData,
        String tileEntityData,
        @NotNull Map<String, String> properties) {

    /**
     * Creates a block snapshot from a Bukkit block data object.
     *
     * @param data the block data to snapshot
     * @return a new block snapshot
     */
    public static BlockSnapshot from(@NotNull BlockData data) {
        return new BlockSnapshot(data.getMaterial(), data.getAsString(), null, Map.of());
    }

    /**
     * Creates a block snapshot with tile entity data.
     *
     * @param data the block data to snapshot
     * @param tileEntityData the serialized tile entity data
     * @return a new block snapshot
     */
    public static BlockSnapshot withTileEntity(@NotNull BlockData data, @NotNull String tileEntityData) {
        return new BlockSnapshot(data.getMaterial(), data.getAsString(), tileEntityData, Map.of());
    }

    /**
     * Creates a block snapshot with additional properties.
     *
     * @param data the block data to snapshot
     * @param properties additional properties
     * @return a new block snapshot
     */
    public static BlockSnapshot withProperties(@NotNull BlockData data, @NotNull Map<String, String> properties) {
        return new BlockSnapshot(data.getMaterial(), data.getAsString(), null, Map.copyOf(properties));
    }

    /**
     * Captures the current state of a block, including tile entity data.
     *
     * @param block the block to snapshot
     * @return a new block snapshot
     */
    public static BlockSnapshot capture(@NotNull Block block) {
        return capture(block.getState());
    }

    /**
     * Captures a block state, including tile entity data.
     *
     * @param state the block state to snapshot
     * @return a new block snapshot
     */
    public static BlockSnapshot capture(@NotNull BlockState state) {
        BlockData data = state.getBlockData();
        String tileData = TileEntityUtil.capture(state);
        return tileData == null ? BlockSnapshot.from(data) : BlockSnapshot.withTileEntity(data, tileData);
    }
}
