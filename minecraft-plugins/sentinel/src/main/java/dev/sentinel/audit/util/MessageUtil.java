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

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.bukkit.command.CommandSender;
import org.jetbrains.annotations.NotNull;

/**
 * Utility for sending formatted messages to command senders.
 *
 * <p>Uses the Adventure MiniMessage format for rich text support
 * across chat and console messages.</p>
 */
public final class MessageUtil {

    private static final MiniMessage MINI_MESSAGE = MiniMessage.miniMessage();

    private MessageUtil() {}

    /**
     * Sends a mini message formatted component to a sender.
     *
     * @param sender the message recipient
     * @param message the mini message string
     */
    public static void send(@NotNull CommandSender sender, @NotNull String message) {
        sender.sendMessage(parse(message));
    }

    /**
     * Sends a mini message formatted component to a sender with prefix.
     *
     * @param sender the message recipient
     * @param prefix the message prefix
     * @param message the mini message string
     */
    public static void send(@NotNull CommandSender sender, @NotNull String prefix, @NotNull String message) {
        sender.sendMessage(parse(prefix + message));
    }

    /**
     * Parses a mini message string into an Adventure component.
     *
     * @param message the mini message string
     * @return the parsed component
     */
    public static Component parse(@NotNull String message) {
        return MINI_MESSAGE.deserialize(message);
    }

    /**
     * Serializes a component back to a mini message string.
     *
     * @param component the component
     * @return the mini message string
     */
    public static String serialize(@NotNull Component component) {
        return MINI_MESSAGE.serialize(component);
    }

    /**
     * Formats a message with legacy color codes.
     *
     * @param message the legacy message
     * @return the formatted component
     */
    public static Component legacy(@NotNull String message) {
        return net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer.legacyAmpersand()
                .deserialize(message);
    }
}
