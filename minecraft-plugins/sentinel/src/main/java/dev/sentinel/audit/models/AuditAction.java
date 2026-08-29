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

/**
 * Enumeration of all auditable actions tracked by Sentinel.
 *
 * <p>Each action type represents a distinct category of game event
 * that can be recorded, inspected, and rolled back.</p>
 */
public enum AuditAction {

    /** A block was placed. */
    BLOCK_PLACE,

    /** A block was broken. */
    BLOCK_BREAK,

    /** A block was modified (e.g., opened, toggled, or changed state). */
    BLOCK_MODIFY,

    /** An item was moved within an inventory. */
    INVENTORY_MOVE,

    /** An item was picked up from the ground. */
    INVENTORY_PICKUP,

    /** An item was dropped on the ground. */
    INVENTORY_DROP,

    /** An item was crafted. */
    INVENTORY_CRAFT,

    /** An item was smelted. */
    INVENTORY_SMELT,

    /** An item was enchanted. */
    INVENTORY_ENCHANT,

    /** An item was traded with a villager. */
    INVENTORY_TRADE,

    /** A player joined the server. */
    PLAYER_JOIN,

    /** A player left the server. */
    PLAYER_QUIT,

    /** A player died. */
    PLAYER_DEATH,

    /** A player was killed by another entity. */
    PLAYER_KILL,

    /** A player sent a chat message. */
    PLAYER_CHAT,

    /** A player used a command. */
    PLAYER_COMMAND,

    /** A player teleported. */
    PLAYER_TELEPORT,

    /** An entity was damaged. */
    ENTITY_DAMAGE,

    /** An entity was killed. */
    ENTITY_DEATH,

    /** An entity was spawned. */
    ENTITY_SPAWN,

    /** An entity was tamed. */
    ENTITY_TAME,

    /** An entity was despawned. */
    ENTITY_DESPAWN,

    /** A dropped item entity despawned on the ground. */
    ITEM_DESPAWN,

    /** A dropped item entity fell out of the world (the void). */
    ITEM_VOID,

    /** A dropped item entity was destroyed by the environment (fire, lava, etc.). */
    ITEM_BURN,

    /** A liquid (water or lava) flowed into a previously dry block. */
    LIQUID_FLOW,

    /** A fire block was created when a block was ignited. */
    FIRE_CATCH,

    /** A fire block spread to a neighbouring block. */
    FIRE_SPREAD,

    /** A fire block faded out. */
    FIRE_FADE,

    /** A container was opened. */
    CONTAINER_OPEN,

    /** A container was closed. */
    CONTAINER_CLOSE,

    /** A container's contents were changed. */
    CONTAINER_CHANGE,

    /** A sign was edited. */
    SIGN_EDIT,

    /** A command block was modified. */
    COMMAND_BLOCK_MODIFY,

    /** A structure was generated. */
    STRUCTURE_GENERATE,

    /** A world edit operation was performed. */
    WORLD_EDIT,

    /** A rollback operation was performed. */
    ROLLBACK,

    /** An administrative action was performed. */
    ADMIN_ACTION
}
