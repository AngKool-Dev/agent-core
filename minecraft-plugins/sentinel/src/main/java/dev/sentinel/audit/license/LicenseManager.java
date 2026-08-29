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

import dev.sentinel.audit.config.SentinelConfig.LicenseConfig;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Orchestrates license enforcement for the plugin.
 *
 * <p>When enforcement is compiled in ({@code release} Maven profile), the
 * plugin calls the license server at startup and fails closed — the plugin
 * disables itself unless a valid, IP-bound license key is presented. The
 * license is re-verified periodically so a revoked or IP-mismatched key
 * stops working quickly. Development builds (default profile) run
 * unrestricted.</p>
 */
public final class LicenseManager {

    private static final Logger LOGGER = LoggerFactory.getLogger(LicenseManager.class);

    private static final long MIN_INTERVAL_MINUTES = 1L;
    private static final long INITIAL_CHECK_TICKS = 20L;

    /**
     * Consecutive transient (network/unreachable) failures tolerated before the
     * plugin disables itself. Definitive rejections (revoked, expired, forged,
     * unknown key) disable immediately. This prevents a single transient blip or a
     * targeted network outage from taking down every premium server at once.
     */
    private static final int MAX_TRANSIENT_FAILURES = 3;

    private final LicenseProperties properties;
    private final LicenseConfig config;
    private final LicenseClient client;
    private final JavaPlugin plugin;

    private volatile boolean licensed;
    private volatile LicenseResult lastResult;
    private org.bukkit.scheduler.BukkitTask recheckTask;
    private int consecutiveTransientFailures = 0;

    /**
     * Constructs a license manager.
     *
     * @param plugin the owning plugin
     * @param properties the baked license properties
     * @param config the license configuration
     */
    public LicenseManager(
            @NotNull JavaPlugin plugin, @NotNull LicenseProperties properties, @NotNull LicenseConfig config) {
        this.plugin = plugin;
        this.properties = properties;
        this.config = config;
        this.client = new LicenseClient(properties.getServerUrl());
    }

    /**
     * Starts license enforcement.
     *
     * <p>In enforced (release) builds this blocks plugin startup until the
     * license is verified; in development builds it returns immediately.</p>
     *
     * @return true if the plugin may continue enabling
     */
    public boolean start() {
        if (!properties.isEnforce()) {
            LOGGER.warn("License enforcement is disabled (development build).");
            this.licensed = true;
            return true;
        }
        LOGGER.info("Verifying Sentinel license against {}", properties.getServerUrl());

        LicenseResult result = client.verify(config.getKey(), properties.getPublicKey());
        this.lastResult = result;

        if (!result.valid()) {
            LOGGER.error("License rejected: {}. Sentinel will not run.", result.reason());
            scheduleRecheck();
            return false;
        }

        LOGGER.info("License verified (expires: {}, bound to {})", describe(result.expiresAt()), result.boundIp());
        this.licensed = true;
        scheduleRecheck();
        return true;
    }

    private void scheduleRecheck() {
        long intervalTicks = Math.max(MIN_INTERVAL_MINUTES, config.getCheckIntervalMinutes()) * 60L * 20L;
        this.recheckTask = plugin.getServer()
                .getScheduler()
                .runTaskTimerAsynchronously(plugin, this::recheck, INITIAL_CHECK_TICKS, intervalTicks);
    }

    private void recheck() {
        if (!properties.isEnforce()) {
            return;
        }
        LicenseResult result = client.verify(config.getKey(), properties.getPublicKey());
        this.lastResult = result;
        if (result.valid()) {
            this.licensed = true;
            consecutiveTransientFailures = 0;
            return;
        }
        if (!isTransientFailure(result.reason())) {
            disable("License invalid (" + result.reason() + ")");
            return;
        }
        if (++consecutiveTransientFailures >= MAX_TRANSIENT_FAILURES) {
            disable("License server unreachable after " + consecutiveTransientFailures + " attempts");
        } else {
            LOGGER.warn(
                    "License re-check failed ({}), attempt {}/{}; will retry before disabling.",
                    result.reason(),
                    consecutiveTransientFailures,
                    MAX_TRANSIENT_FAILURES);
        }
    }

    private void disable(String message) {
        if (this.licensed) {
            this.licensed = false;
            LOGGER.error("{}; disabling Sentinel.", message);
            plugin.getServer()
                    .getScheduler()
                    .runTask(plugin, () -> plugin.getServer().getPluginManager().disablePlugin(plugin));
        }
    }

    private static boolean isTransientFailure(@NotNull String reason) {
        return reason.contains("unreachable") || reason.contains("returned status");
    }

    /**
     * Checks whether the plugin is currently licensed.
     *
     * @return true if licensed or enforcement is disabled
     */
    public boolean isLicensed() {
        return licensed;
    }

    /**
     * Gets the most recent verification result.
     *
     * @return the last result
     */
    public @NotNull LicenseResult getLastResult() {
        return lastResult;
    }

    /**
     * Cancels the periodic re-verification task.
     */
    public void shutdown() {
        if (recheckTask != null) {
            recheckTask.cancel();
            recheckTask = null;
        }
    }

    private static String describe(long expiresAt) {
        if (expiresAt <= 0L) {
            return "never";
        }
        return java.time.Instant.ofEpochMilli(expiresAt).toString();
    }
}
