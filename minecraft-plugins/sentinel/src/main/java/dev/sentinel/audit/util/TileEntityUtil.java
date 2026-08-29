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

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Base64;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Container;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.io.BukkitObjectInputStream;
import org.bukkit.util.io.BukkitObjectOutputStream;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Utility for capturing and restoring block tile entity data.
 *
 * <p>Serializes the contents of container-like blocks so that their
 * state can be persisted and restored during rollback.</p>
 */
public final class TileEntityUtil {

    private static final Logger LOGGER = LoggerFactory.getLogger(TileEntityUtil.class);

    private TileEntityUtil() {}

    /**
     * Captures tile entity data from a block state.
     *
     * @param state the block state to capture
     * @return the serialized tile entity data, or null if the block has none
     */
    @Nullable
    public static String capture(@NotNull BlockState state) {
        if (state instanceof Container container) {
            return serializeInventory(container.getSnapshotInventory());
        }
        return null;
    }

    /**
     * Restores tile entity data onto a block.
     *
     * @param block the block to restore
     * @param data the serialized tile entity data
     */
    public static void restore(@NotNull Block block, @Nullable String data) {
        if (data == null) {
            return;
        }
        BlockState state = block.getState();
        if (state instanceof Container container) {
            deserializeInto(container.getInventory(), data);
            container.update(true);
        }
    }

    /**
     * Serializes an inventory's contents to a Base64 string.
     *
     * @param inventory the inventory to serialize
     * @return the Base64 encoded inventory, or null on failure
     */
    @Nullable
    private static String serializeInventory(@NotNull Inventory inventory) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            writeInventory(bytes, inventory);
            return Base64.getEncoder().encodeToString(bytes.toByteArray());
        } catch (IOException exception) {
            LOGGER.warn("Failed to serialize inventory", exception);
            return null;
        }
    }

    /**
     * Writes an inventory's contents to an output stream.
     *
     * @param output the output stream
     * @param inventory the inventory to write
     * @throws IOException if writing fails
     */
    private static void writeInventory(@NotNull OutputStream output, @NotNull Inventory inventory) throws IOException {
        try (BukkitObjectOutputStream stream = new BukkitObjectOutputStream(output)) {
            stream.writeInt(inventory.getSize());
            for (ItemStack item : inventory.getContents()) {
                stream.writeObject(item);
            }
        }
    }

    /**
     * Deserializes Base64 encoded inventory data into an inventory.
     *
     * @param inventory the inventory to fill
     * @param data the Base64 encoded contents
     */
    private static void deserializeInto(@NotNull Inventory inventory, @NotNull String data) {
        try {
            byte[] bytes = Base64.getDecoder().decode(data);
            inventory.setContents(readContents(bytes, inventory.getSize()));
        } catch (IOException | ClassNotFoundException exception) {
            LOGGER.warn("Failed to restore inventory", exception);
        }
    }

    /**
     * Reads item stacks from the given bytes.
     *
     * @param bytes the inventory bytes
     * @param size the number of slots to read
     * @return the deserialized item stacks
     * @throws IOException if reading fails
     * @throws ClassNotFoundException if a stored class cannot be found
     */
    private static ItemStack[] readContents(@NotNull byte[] bytes, int size)
            throws IOException, ClassNotFoundException {
        ItemStack[] contents = new ItemStack[size];
        InputStream input = new ByteArrayInputStream(bytes);
        try (BukkitObjectInputStream stream = new BukkitObjectInputStream(input)) {
            for (int i = 0; i < size; i++) {
                contents[i] = (ItemStack) stream.readObject();
            }
        }
        return contents;
    }
}
