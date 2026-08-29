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
package dev.sentinel.audit.config;

import dev.sentinel.audit.api.exception.ConfigurationException;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.NotNull;

/**
 * Loads and manages the plugin configuration files.
 *
 * <p>Handles the loading of config.yml and messages.yml, including
 * default file extraction and reload support.</p>
 */
public final class ConfigLoader {

    private final JavaPlugin plugin;
    private SentinelConfig config;
    private FileConfiguration messages;

    /**
     * Constructs a new config loader for the given plugin.
     *
     * @param plugin the owning plugin
     */
    public ConfigLoader(@NotNull JavaPlugin plugin) {
        this.plugin = plugin;
    }

    /**
     * Loads all configuration files.
     *
     * @throws ConfigurationException if configuration cannot be loaded
     */
    public void load() {
        loadConfig();
        loadMessages();
    }

    /**
     * Reloads all configuration files.
     *
     * @throws ConfigurationException if configuration cannot be reloaded
     */
    public void reload() {
        load();
    }

    /**
     * Loads the main config.yml file.
     *
     * @throws ConfigurationException if the config cannot be loaded
     */
    private void loadConfig() {
        File configFile = new File(plugin.getDataFolder(), "config.yml");
        if (!configFile.exists()) {
            plugin.saveResource("config.yml", false);
        }

        FileConfiguration bukkitConfig = YamlConfiguration.loadConfiguration(configFile);
        try (InputStream defaultStream = plugin.getResource("config.yml")) {
            if (defaultStream != null) {
                YamlConfiguration defaultConfig = YamlConfiguration.loadConfiguration(
                        new InputStreamReader(defaultStream, StandardCharsets.UTF_8));
                bukkitConfig.setDefaults(defaultConfig);
            }
        } catch (IOException exception) {
            throw new ConfigurationException("Failed to load default config.yml", exception);
        }

        this.config = new SentinelConfig(bukkitConfig);
    }

    /**
     * Loads the messages.yml file.
     *
     * @throws ConfigurationException if the messages file cannot be loaded
     */
    private void loadMessages() {
        File messagesFile = new File(plugin.getDataFolder(), "messages.yml");
        if (!messagesFile.exists()) {
            plugin.saveResource("messages.yml", false);
        }

        this.messages = YamlConfiguration.loadConfiguration(messagesFile);
        try (InputStream defaultStream = plugin.getResource("messages.yml")) {
            if (defaultStream != null) {
                YamlConfiguration defaultMessages = YamlConfiguration.loadConfiguration(
                        new InputStreamReader(defaultStream, StandardCharsets.UTF_8));
                this.messages.setDefaults(defaultMessages);
            }
        } catch (IOException exception) {
            throw new ConfigurationException("Failed to load default messages.yml", exception);
        }
    }

    /**
     * Gets the loaded plugin configuration.
     *
     * @return the configuration
     */
    public SentinelConfig getConfig() {
        return config;
    }

    /**
     * Gets the loaded messages configuration.
     *
     * @return the messages configuration
     */
    public FileConfiguration getMessages() {
        return messages;
    }
}
