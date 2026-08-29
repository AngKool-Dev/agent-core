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

import java.util.List;
import org.jetbrains.annotations.NotNull;

/**
 * Immutable paginated result wrapper for query responses.
 *
 * <p>Contains the result items along with pagination metadata to
 * support efficient browsing of large result sets.</p>
 *
 * @param <T> the type of items in the result
 * @param items the result items
 * @param total the total number of matching items
 * @param page the current page number (0-based)
 * @param pageSize the number of items per page
 * @param hasNext whether there are more pages available
 */
public record PaginatedResult<T>(@NotNull List<T> items, long total, int page, int pageSize, boolean hasNext) {

    /**
     * Creates a paginated result.
     *
     * @param items the result items
     * @param total the total number of matching items
     * @param page the current page number
     * @param pageSize the page size
     * @param <T> the item type
     * @return a new paginated result
     */
    public static <T> PaginatedResult<T> of(@NotNull List<T> items, long total, int page, int pageSize) {
        int totalPages = pageSize > 0 ? (int) Math.ceil((double) total / pageSize) : 0;
        return new PaginatedResult<>(List.copyOf(items), total, page, pageSize, page + 1 < totalPages);
    }

    /**
     * Creates an empty paginated result.
     *
     * @param <T> the item type
     * @return an empty paginated result
     */
    public static <T> PaginatedResult<T> empty() {
        return new PaginatedResult<>(List.of(), 0, 0, 0, false);
    }
}
