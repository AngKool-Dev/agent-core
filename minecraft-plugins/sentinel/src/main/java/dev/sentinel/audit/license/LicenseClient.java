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

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.time.Duration;
import java.util.Base64;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * HTTP client for the Sentinel license server.
 *
 * <p>Contacts {@code GET <serverUrl>/verify?key=<key>} and verifies the
 * Ed25519 signature of the server response using the public key baked into
 * this build. Responses that fail verification are treated as invalid so a
 * forged/mocked license server can never approve a key.</p>
 */
public final class LicenseClient {

    private static final Logger LOGGER = LoggerFactory.getLogger(LicenseClient.class);
    private static final Duration TIMEOUT = Duration.ofSeconds(8);

    /**
     * Maximum age of a signed license response before it is rejected. This
     * bounds the window in which a captured (valid) response can be replayed
     * after a key is revoked or expires.
     */
    private static final long RESPONSE_TTL_MS = 5L * 60L * 1000L;

    /** Allowed clock skew between the plugin and the license server. */
    private static final long CLOCK_SKEW_MS = 30L * 1000L;

    private static final String KEY_HEADER = "X-Sentinel-Key";

    private final String serverUrl;
    private final HttpClient http;

    /**
     * Constructs a license client.
     *
     * @param serverUrl the license server URL (may be empty for localhost)
     */
    public LicenseClient(@NotNull String serverUrl) {
        this.serverUrl = serverUrl.isBlank() ? "http://localhost:8080" : serverUrl;
        this.http = HttpClient.newBuilder().connectTimeout(TIMEOUT).build();
    }

    /**
     * Verifies a license key against the configured server.
     *
     * @param key the license key
     * @param publicKeyB64 the base64 Ed25519 public key
     * @return immutable verification result
     */
    public @NotNull LicenseResult verify(@Nullable String key, @NotNull String publicKeyB64) {
        if (key == null || key.isBlank()) {
            LOGGER.error("License enforcement is enabled but no license key is configured.");
            return LicenseResult.invalid("No license key configured");
        }
        String url = verifyUrl();
        try {
            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder(URI.create(url))
                    .timeout(TIMEOUT)
                    .GET()
                    .header("Accept", "application/json");
            if (key != null && !key.isBlank()) {
                requestBuilder.header(KEY_HEADER, key);
            }
            HttpResponse<String> response = http.send(requestBuilder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                return LicenseResult.invalid("License server returned status " + response.statusCode());
            }
            return parseAndVerify(response.body(), publicKeyB64);
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            LOGGER.error("License server unreachable: {}", exception.getMessage());
            return LicenseResult.invalid("License server unreachable: " + exception.getMessage());
        }
    }

    private String verifyUrl() {
        return serverUrl + "/verify";
    }

    private @NotNull LicenseResult parseAndVerify(String body, @NotNull String publicKeyB64) {
        try {
            JsonObject json = JsonParser.parseString(body).getAsJsonObject();
            boolean valid = json.has("valid") && json.get("valid").getAsBoolean();
            String key = json.has("key") ? json.get("key").getAsString() : "";
            long expires = json.has("expires") ? json.get("expires").getAsLong() : 0L;
            String ip = json.has("ip") ? json.get("ip").getAsString() : "";
            String reason = json.has("reason") ? json.get("reason").getAsString() : "";
            String sig = json.has("sig") ? json.get("sig").getAsString() : "";
            long iat = json.has("iat") ? json.get("iat").getAsLong() : 0L;

            if (!valid) {
                return LicenseResult.invalid(reason);
            }
            if (!verifySignature(publicKeyB64, valid, key, expires, ip, iat, sig)) {
                return LicenseResult.invalid("Signature verification failed");
            }
            long now = System.currentTimeMillis();
            if (iat <= 0L || now - iat > RESPONSE_TTL_MS || iat - now > CLOCK_SKEW_MS) {
                return LicenseResult.invalid("License response expired or replayed");
            }
            return LicenseResult.valid(expires, ip);
        } catch (RuntimeException exception) {
            LOGGER.error("Malformed license server response: {}", exception.getMessage());
            return LicenseResult.invalid("Malformed license server response");
        }
    }

    private boolean verifySignature(
            @NotNull String publicKeyB64,
            boolean valid,
            @NotNull String key,
            long expires,
            @NotNull String ip,
            long iat,
            @NotNull String sig) {
        try {
            byte[] canonical =
                    ("v1|" + valid + "|" + key + "|" + expires + "|" + ip + "|" + iat).getBytes(StandardCharsets.UTF_8);
            byte[] signature = Base64.getDecoder().decode(sig);
            byte[] pub = Base64.getDecoder().decode(publicKeyB64);
            KeyFactory factory = KeyFactory.getInstance("Ed25519");
            Signature verifier = Signature.getInstance("Ed25519");
            verifier.initVerify(factory.generatePublic(new X509EncodedKeySpec(pub)));
            verifier.update(canonical);
            return verifier.verify(signature);
        } catch (Exception exception) {
            LOGGER.error("Failed to verify license signature: {}", exception.getMessage());
            return false;
        }
    }
}
