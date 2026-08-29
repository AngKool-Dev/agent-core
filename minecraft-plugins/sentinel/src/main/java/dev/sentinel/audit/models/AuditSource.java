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
 * Enumeration of sources that can generate audit events.
 *
 * <p>Identifies the origin of an auditable action, distinguishing
 * between player actions, automated systems, and administrative tools.</p>
 */
public enum AuditSource {

    /** The action was performed by a player. */
    PLAYER,

    /** The action was performed by the server console. */
    CONSOLE,

    /** The action was performed by a plugin or automated system. */
    PLUGIN,

    /** The action was performed by a command block. */
    COMMAND_BLOCK,

    /** The action was performed by a redstone mechanism. */
    REDSTONE,

    /** The action was performed by a natural game mechanic. */
    NATURAL,

    /** The action was performed by an entity (non-player). */
    ENTITY,

    /** The action was performed by the Sentinel plugin itself. */
    SENTINEL
}
