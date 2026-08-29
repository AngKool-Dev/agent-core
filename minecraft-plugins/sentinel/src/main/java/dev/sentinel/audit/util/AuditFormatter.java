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

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.models.AuditAction;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import org.jetbrains.annotations.NotNull;

/**
 * Formats audit events as human-readable text for chat and command output.
 *
 * <p>Turns a raw {@link AuditEvent} into a concise description that
 * identifies what happened, to which mob or block, and by whom, using
 * the action-specific metadata captured by the listeners.</p>
 */
public final class AuditFormatter {

    private static final DateTimeFormatter TIME_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneId.systemDefault());

    private AuditFormatter() {}

    /**
     * Formats an event timestamp as a readable local date and time.
     *
     * @param event the audit event
     * @return the formatted timestamp
     */
    public static String time(@NotNull AuditEvent event) {
        return TIME_FORMATTER.format(event.timestamp());
    }

    /**
     * Converts a material name to a friendly display name.
     *
     * @param material the material name (e.g., "GRASS_BLOCK", "WATER")
     * @return the friendly name (e.g., "grass block", "water")
     */
    public static String friendlyMaterial(@NotNull String material) {
        return switch (material) {
            case "WATER", "FLOWING_WATER" -> "water";
            case "LAVA", "FLOWING_LAVA" -> "lava";
            case "" -> "block";
            default -> material.toLowerCase(java.util.Locale.ROOT).replace('_', ' ');
        };
    }

    /**
     * Renders a short who-did-what summary for player block edits, such as
     * {@code Steve destroyed this grass block} or {@code Steve placed this lava}.
     *
     * <p>Only actions that a player directly caused on blocks (place/break/modify)
     * are summarized; anything else renders null so the caller can fall back to
     * the generic description.</p>
     *
     * @param event the audit event
     * @return the summary, or null if the event is not a player block edit
     */
    public static String playerBlockSummary(@NotNull AuditEvent event) {
        if (event.source() != dev.sentinel.audit.models.AuditSource.PLAYER) {
            return null;
        }
        String actor = event.actorName();
        String material = friendlyMaterial(event.metadata().getOrDefault("material", ""));
        return switch (event.action()) {
            case BLOCK_BREAK ->
                "<green>" + actor + "</green> <gray>destroyed this</gray> <white>" + material + "</white>";
            case BLOCK_PLACE -> "<green>" + actor + "</green> <gray>placed this</gray> <white>" + material + "</white>";
            case BLOCK_MODIFY ->
                "<green>" + actor + "</green> <gray>changed this</gray> <white>" + material + "</white>";
            default -> null;
        };
    }

    /**
     * Renders an event as a colored, human-readable description.
     *
     * @param event the audit event
     * @return the description text
     */
    public static String describe(@NotNull AuditEvent event) {
        AuditAction action = event.action();
        String actor = actorName(event);
        String material = event.metadata().getOrDefault("material", "");
        String target =
                event.metadata().getOrDefault("entityType", event.targetName() != null ? event.targetName() : "");
        switch (action) {
            case BLOCK_PLACE:
                return "<green>" + actor + "</green> <gray>placed</gray> <white>" + material + "</white>";
            case BLOCK_BREAK:
                return "<green>" + actor + "</green> <gray>broke</gray> <white>" + material + "</white>";
            case BLOCK_MODIFY:
                return "<green>" + actor + "</green> <gray>modified</gray> <white>" + material + "</white>";
            case SIGN_EDIT:
                return "<green>" + actor + "</green> <gray>edited a sign</gray>";
            case ENTITY_DEATH:
                if (!target.isEmpty()) {
                    String killer = event.metadata().getOrDefault("killerName", actor);
                    return "<color:#ff7f50>" + target + "</color> <gray>was killed by</gray> <green>" + killer
                            + "</green>";
                }
                return "<color:#ff7f50>" + actor + "</color> <gray>died</gray>";
            case ENTITY_DAMAGE:
                return "<green>" + actor + "</green> <gray>took</gray> <white>"
                        + event.metadata().getOrDefault("damage", "?") + "</white> <gray>damage</gray> "
                        + "<dark_gray>(" + event.metadata().getOrDefault("cause", "") + ")</dark_gray>";
            case LIQUID_FLOW:
                return "<aqua>Water/Lava</aqua> <gray>flowed into</gray> <white>" + material + "</white>";
            case FIRE_SPREAD:
                return "<color:#ff7f50>Fire</color> <gray>spread</gray>";
            case FIRE_FADE:
                return "<color:#ff7f50>Fire</color> <gray>faded out</gray>";
            case FIRE_CATCH:
                return "<gray>A block caught fire</gray>";
            case ITEM_BURN:
                return "<gray>Item burned in fire/lava</gray>";
            case ITEM_VOID:
                return "<gray>Item fell into the void</gray>";
            case ITEM_DESPAWN:
                return "<gray>Item despawned</gray>";
            case INVENTORY_DROP:
            case INVENTORY_PICKUP:
                return "<green>" + actor + "</green> <gray>"
                        + (action == AuditAction.INVENTORY_PICKUP ? "picked up" : "dropped") + "</gray> <white>"
                        + event.metadata().getOrDefault("item", "item") + "</white> "
                        + event.metadata().getOrDefault("amount", "");
            case INVENTORY_MOVE:
                return "<green>" + actor + "</green> <gray>moved</gray> <white>"
                        + event.metadata().getOrDefault("item", "item") + "</white> x"
                        + event.metadata().getOrDefault("amount", "");
            case CONTAINER_OPEN:
                return "<green>" + actor + "</green> <gray>opened</gray> <white>"
                        + event.metadata().getOrDefault("inventoryType", "container") + "</white>";
            case CONTAINER_CLOSE:
                return "<green>" + actor + "</green> <gray>closed</gray> <white>"
                        + event.metadata().getOrDefault("inventoryType", "container") + "</white>";
            case CONTAINER_CHANGE:
                return "<green>" + actor + "</green> <gray>changed items in</gray> <white>"
                        + event.metadata().getOrDefault("inventoryType", "container") + "</white>";
            case PLAYER_COMMAND:
                return "<green>" + actor + "</green> <gray>ran</gray> <aqua>"
                        + event.metadata().getOrDefault("command", "") + "</aqua>";
            case PLAYER_CHAT:
                return "<green>" + actor + "</green> <gray>said:</gray> <white>"
                        + event.metadata().getOrDefault("message", "") + "</white>";
            case PLAYER_JOIN:
                return "<green>" + actor + "</green> <gray>joined the game</gray>";
            case PLAYER_QUIT:
                return "<green>" + actor + "</green> <gray>left the game</gray>";
            case PLAYER_DEATH:
                return "<green>" + actor + "</green> <gray>died</gray> " + "(<dark_gray>"
                        + event.metadata().getOrDefault("cause", "unknown") + "</dark_gray>)";
            case ENTITY_TAME:
                return "<green>" + actor + "</green> <gray>tamed</gray> <white>" + target + "</white>";
            default:
                return "<white>" + event.action().name() + "</white> <dark_gray>by</dark_gray> <green>" + actor
                        + "</green>";
        }
    }

    /**
     * Resolves the display name of the actor.
     *
     * @param event the audit event
     * @return the actor name
     */
    private static @NotNull String actorName(@NotNull AuditEvent event) {
        if (!event.actorName().equals("WORLD") && !event.actorName().equals("HOPPER")) {
            return event.actorName();
        }
        return event.actorName().toLowerCase();
    }
}
