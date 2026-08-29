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
package dev.sentinel.audit;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;
import org.jetbrains.annotations.NotNull;

/**
 * The baked plugin edition.
 *
 * <p>Value is injected by Maven resource filtering from the
 * {@code sentinel.edition} property. The default build is {@link #FULL}
 * (the paid feature set). The {@code lite} Maven profile bakes
 * {@link #LITE}, which compiles out premium features so the free Modrinth
 * build still works without a license key.</p>
 */
public enum Edition {

    FULL,
    LITE;

    private static final String RESOURCE = "/edition.properties";

    private static volatile Edition loaded;

    /**
     * Loads the baked edition from the plugin resource.
     *
     * <p>If the resource is missing (e.g. during unit tests) the full
     * edition is returned.</p>
     *
     * @return the baked edition
     */
    public static @NotNull Edition load() {
        Edition current = loaded;
        if (current != null) {
            return current;
        }
        synchronized (Edition.class) {
            if (loaded == null) {
                loaded = parse();
            }
            return loaded;
        }
    }

    private static @NotNull Edition parse() {
        try (InputStream in = Edition.class.getResourceAsStream(RESOURCE)) {
            if (in == null) {
                return FULL;
            }
            Properties props = new Properties();
            props.load(in);
            return "lite".equalsIgnoreCase(props.getProperty("sentinel.edition", "full")) ? LITE : FULL;
        } catch (IOException exception) {
            return FULL;
        }
    }

    /**
     * Checks whether this is the free Lite edition.
     *
     * @return true if Lite
     */
    public boolean isLite() {
        return this == LITE;
    }
}
