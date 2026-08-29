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

import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import org.bukkit.inventory.ItemStack;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable snapshot of an inventory's contents at a point in time.
 *
 * <p>Captures the serialized contents of an inventory, including
 * slot mappings and any additional inventory properties.</p>
 *
 * @param contents the serialized inventory contents keyed by slot index
 * @param size the inventory size
 * @param title the inventory title, if any
 * @param properties additional inventory properties
 */
public record InventorySnapshot(
        @NotNull Map<Integer, String> contents,
        int size,
        String title,
        @NotNull Map<String, String> properties) {

    /**
     * Creates an inventory snapshot from a list of item stacks.
     *
     * @param items the item stacks to snapshot
     * @return a new inventory snapshot
     */
    public static InventorySnapshot from(@NotNull List<ItemStack> items) {
        Map<Integer, String> contents = new java.util.HashMap<>();
        for (int i = 0; i < items.size(); i++) {
            ItemStack item = items.get(i);
            if (item != null && !item.isEmpty()) {
                contents.put(i, encode(item));
            }
        }
        return new InventorySnapshot(Map.copyOf(contents), items.size(), null, Map.of());
    }

    /**
     * Creates an inventory snapshot with a title.
     *
     * @param items the item stacks to snapshot
     * @param title the inventory title
     * @return a new inventory snapshot
     */
    public static InventorySnapshot withTitle(@NotNull List<ItemStack> items, @NotNull String title) {
        Map<Integer, String> contents = new java.util.HashMap<>();
        for (int i = 0; i < items.size(); i++) {
            ItemStack item = items.get(i);
            if (item != null && !item.isEmpty()) {
                contents.put(i, encode(item));
            }
        }
        return new InventorySnapshot(Map.copyOf(contents), items.size(), title, Map.of());
    }

    /**
     * Creates an empty inventory snapshot.
     *
     * @param size the inventory size
     * @param title the inventory title, if any
     * @return a new empty inventory snapshot
     */
    public static InventorySnapshot empty(int size, String title) {
        return new InventorySnapshot(Map.of(), size, title, Map.of());
    }

    /**
     * Deserializes this snapshot into a list of item stacks.
     *
     * @return the deserialized item stacks
     */
    public @NotNull List<ItemStack> toItems() {
        List<ItemStack> items = new ArrayList<>();
        for (String encoded : contents.values()) {
            items.add(ItemStack.deserializeBytes(Base64.getDecoder().decode(encoded)));
        }
        return items;
    }

    /**
     * Serializes the contents map into a single stable string for storage.
     *
     * <p>The format is {@code slot:b64;slot:b64;...}, using delimiters that
     * cannot appear inside the Base64 values so the string round-trips losslessly.</p>
     *
     * @param contents the contents to serialize
     * @return the serialized contents string
     */
    public static @NotNull String serializeContents(@NotNull Map<Integer, String> contents) {
        StringBuilder builder = new StringBuilder();
        for (Map.Entry<Integer, String> entry : contents.entrySet()) {
            if (builder.length() > 0) {
                builder.append(';');
            }
            builder.append(entry.getKey()).append(':').append(entry.getValue());
        }
        return builder.toString();
    }

    /**
     * Deserializes a stored contents string back into a slot-keyed map.
     *
     * @param stored the serialized contents string
     * @return the deserialized contents map, or an empty map if malformed
     */
    public static @NotNull Map<Integer, String> deserializeContents(@NotNull String stored) {
        if (stored == null || stored.isEmpty()) {
            return Map.of();
        }
        Map<Integer, String> contents = new java.util.HashMap<>();
        for (String part : stored.split(";")) {
            int separator = part.indexOf(':');
            if (separator <= 0) {
                continue;
            }
            try {
                contents.put(Integer.parseInt(part.substring(0, separator)), part.substring(separator + 1));
            } catch (NumberFormatException ignored) {
                // Skip malformed entries rather than failing the whole batch.
            }
        }
        return Map.copyOf(contents);
    }

    /**
     * Encodes an item stack as a Base64 string.
     *
     * @param item the item stack
     * @return the Base64 encoded item
     */
    private static String encode(@NotNull ItemStack item) {
        return Base64.getEncoder().encodeToString(item.serializeAsBytes());
    }
}
