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
package dev.sentinel.audit.license;

import org.jetbrains.annotations.NotNull;

/**
 * Immutable result of a license verification.
 *
 * @param valid whether the license is valid
 * @param reason a human-readable explanation when the license is invalid
 * @param expiresAt epoch millis when the license expires (0 = never)
 * @param boundIp the IP the key is bound to
 */
public record LicenseResult(
        boolean valid,
        @NotNull String reason,
        long expiresAt,
        @NotNull String boundIp) {

    /**
     * Creates a valid result.
     *
     * @param expiresAt epoch millis when the license expires (0 = never)
     * @param boundIp the bound server IP
     * @return the result
     */
    public static @NotNull LicenseResult valid(long expiresAt, @NotNull String boundIp) {
        return new LicenseResult(true, "OK", expiresAt, boundIp);
    }

    /**
     * Creates an invalid result.
     *
     * @param reason the failure reason
     * @return the result
     */
    public static @NotNull LicenseResult invalid(@NotNull String reason) {
        return new LicenseResult(false, reason, 0L, "");
    }
}
