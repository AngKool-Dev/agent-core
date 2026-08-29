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
package dev.sentinel.audit.api.exception;

import dev.sentinel.audit.api.SentinelException;
import java.util.UUID;

/**
 * Thrown when an audit record cannot be found.
 *
 * <p>Indicates that a requested audit event does not exist in the
 * database or cache.</p>
 */
public class AuditRecordNotFoundException extends SentinelException {

    /**
     * Constructs a new exception for a missing audit record.
     *
     * @param eventId the ID of the missing audit event
     */
    public AuditRecordNotFoundException(UUID eventId) {
        super("Audit record not found: " + eventId);
    }

    /**
     * Constructs a new exception with a custom message.
     *
     * @param message the detail message
     */
    public AuditRecordNotFoundException(String message) {
        super(message);
    }
}
