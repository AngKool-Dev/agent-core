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

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;
import org.jetbrains.annotations.NotNull;

/**
 * Build-time baked license properties.
 *
 * <p>Values are injected by Maven resource filtering from the
 * {@code license.*} properties. Release builds ship with enforcement
 * enabled plus the license server URL and the Ed25519 public key; the
 * plugin then refuses to run without a valid, IP-bound license key.</p>
 */
public final class LicenseProperties {

    private static final String RESOURCE = "/license.properties";

    private final boolean enforce;
    private final String serverUrl;
    private final String publicKey;

    /**
     * Constructs license properties.
     *
     * @param enforce whether license enforcement is compiled in
     * @param serverUrl the license server URL
     * @param publicKey the base64 Ed25519 public key
     */
    public LicenseProperties(boolean enforce, @NotNull String serverUrl, @NotNull String publicKey) {
        this.enforce = enforce;
        this.serverUrl = serverUrl;
        this.publicKey = publicKey;
    }

    /**
     * Loads the baked license properties from the plugin resource.
     *
     * <p>If the resource is missing (e.g. during unit tests) a permissive
     * development profile is returned.</p>
     *
     * @return the loaded properties
     */
    public static @NotNull LicenseProperties load() {
        try (InputStream in = LicenseProperties.class.getResourceAsStream(RESOURCE)) {
            if (in == null) {
                return new LicenseProperties(false, "", "");
            }
            Properties props = new Properties();
            props.load(in);
            return new LicenseProperties(
                    Boolean.parseBoolean(props.getProperty("license.enforce", "false")),
                    props.getProperty("license.serverUrl", ""),
                    props.getProperty("license.publicKey", ""));
        } catch (IOException exception) {
            return new LicenseProperties(false, "", "");
        }
    }

    /**
     * Checks whether license enforcement is compiled into this build.
     *
     * @return true if enforcement is active
     */
    public boolean isEnforce() {
        return enforce;
    }

    /**
     * Gets the baked license server URL.
     *
     * @return the server URL
     */
    public @NotNull String getServerUrl() {
        return serverUrl;
    }

    /**
     * Gets the baked base64 Ed25519 public key.
     *
     * @return the public key
     */
    public @NotNull String getPublicKey() {
        return publicKey;
    }
}
