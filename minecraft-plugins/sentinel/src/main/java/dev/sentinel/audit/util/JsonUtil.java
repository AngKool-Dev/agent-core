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

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import java.lang.reflect.Type;
import java.util.Map;
import org.jetbrains.annotations.NotNull;

/**
 * Utility for JSON serialization and deserialization.
 *
 * <p>Provides convenience methods for converting between JSON strings
 * and Java objects using Gson.</p>
 */
public final class JsonUtil {

    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    private static final Type MAP_STRING_STRING_TYPE = new TypeToken<Map<String, String>>() {}.getType();

    private JsonUtil() {}

    /**
     * Serializes an object to a JSON string.
     *
     * @param value the object to serialize
     * @return the JSON string
     */
    public static String toJson(@NotNull Object value) {
        return GSON.toJson(value);
    }

    /**
     * Deserializes a JSON string to an object.
     *
     * @param json the JSON string
     * @param type the target class
     * @param <T> the target type
     * @return the deserialized object
     */
    public static <T> T fromJson(@NotNull String json, @NotNull Class<T> type) {
        return GSON.fromJson(json, type);
    }

    /**
     * Deserializes a JSON string to a map of strings.
     *
     * @param json the JSON string
     * @return the deserialized map
     */
    public static Map<String, String> toMap(@NotNull String json) {
        if (json.isBlank() || "{}".equals(json)) {
            return Map.of();
        }
        return GSON.fromJson(json, MAP_STRING_STRING_TYPE);
    }
}
