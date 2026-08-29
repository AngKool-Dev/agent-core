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

import java.time.Duration;
import java.time.Instant;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.jetbrains.annotations.NotNull;

/**
 * Utility for time parsing and formatting.
 *
 * <p>Provides helpers for converting between duration strings (e.g.,
 * "30d", "12h", "45m") and {@link Duration} objects.</p>
 */
public final class TimeUtil {

    private static final Pattern DURATION_PATTERN = Pattern.compile(
            "(\\d+)\\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w)", Pattern.CASE_INSENSITIVE);

    private static final Pattern CLOCK_PATTERN = Pattern.compile("(\\d{1,2}):(\\d{1,2}):(\\d{1,2})");

    private TimeUtil() {}

    /**
     * Parses a duration string into a {@link Duration}.
     *
     * <p>Supported formats: unit suffixes like {@code "30d"}, {@code "12h"},
     * {@code "45m"}, {@code "1w"}, full words like {@code "1day"},
     * {@code "7days"}, and clock times like {@code "01:30:15"} (hours,
     * minutes, seconds).</p>
     *
     * @param input the duration string
     * @return the parsed duration
     */
    public static Duration parseDuration(@NotNull String input) {
        Matcher clockMatcher = CLOCK_PATTERN.matcher(input.trim());
        if (clockMatcher.matches()) {
            long hours = Long.parseLong(clockMatcher.group(1));
            long minutes = Long.parseLong(clockMatcher.group(2));
            long seconds = Long.parseLong(clockMatcher.group(3));
            if (minutes > 59 || seconds > 59) {
                throw new IllegalArgumentException("Invalid clock format: " + input);
            }
            return Duration.ofHours(hours).plusMinutes(minutes).plusSeconds(seconds);
        }

        Matcher matcher = DURATION_PATTERN.matcher(input);
        Duration total = Duration.ZERO;
        boolean found = false;

        while (matcher.find()) {
            long value = Long.parseLong(matcher.group(1));
            String unit = matcher.group(2).toLowerCase();
            total = total.plus(
                    switch (unit) {
                        case "s", "sec", "secs", "second", "seconds" -> Duration.ofSeconds(value);
                        case "m", "min", "mins", "minute", "minutes" -> Duration.ofMinutes(value);
                        case "h", "hr", "hrs", "hour", "hours" -> Duration.ofHours(value);
                        case "d", "day", "days" -> Duration.ofDays(value);
                        case "w", "week", "weeks" -> Duration.ofDays(value * 7);
                        default -> Duration.ZERO;
                    });
            found = true;
        }

        if (!found) {
            throw new IllegalArgumentException("Invalid duration format: " + input);
        }
        return total;
    }

    /**
     * Formats a duration into a human-readable string.
     *
     * @param duration the duration
     * @return the formatted string
     */
    public static String format(@NotNull Duration duration) {
        long days = duration.toDays();
        long hours = duration.toHours() % 24;
        long minutes = duration.toMinutes() % 60;
        long seconds = duration.getSeconds() % 60;

        StringBuilder builder = new StringBuilder();
        if (days > 0) {
            builder.append(days).append("d ");
        }
        if (hours > 0) {
            builder.append(hours).append("h ");
        }
        if (minutes > 0) {
            builder.append(minutes).append("m ");
        }
        if (seconds > 0 || builder.isEmpty()) {
            builder.append(seconds).append("s");
        }
        return builder.toString().trim();
    }

    /**
     * Formats a timestamp as an ISO-8601 string.
     *
     * @param instant the instant
     * @return the formatted timestamp
     */
    public static String formatInstant(@NotNull Instant instant) {
        return instant.toString();
    }
}
