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
package dev.sentinel.audit.commands;

import dev.sentinel.audit.bootstrap.PluginContext;
import dev.sentinel.audit.inspector.BlockInspector;
import dev.sentinel.audit.util.MessageUtil;
import dev.sentinel.audit.util.TimeUtil;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.OfflinePlayer;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/**
 * Main command handler for the Sentinel plugin.
 *
 * <p>Dispatches subcommands to specialized handlers for inspection,
 * rollback, purge, reload, and status operations.</p>
 */
public final class SentinelCommand implements CommandExecutor, TabCompleter {

    private static final org.slf4j.Logger LOGGER = org.slf4j.LoggerFactory.getLogger(SentinelCommand.class);

    private final PluginContext context;
    private final BlockInspector inspector;

    /**
     * Constructs a new sentinel command.
     *
     * @param context the plugin context
     */
    public SentinelCommand(@NotNull PluginContext context) {
        this.context = context;
        this.inspector = new BlockInspector(context.getInspectionService());
    }

    /**
     * Executes the sentinel command.
     *
     * @param sender the command sender
     * @param command the command
     * @param label the command label
     * @param args the command arguments
     * @return true if the command was handled
     */
    @Override
    public boolean onCommand(
            @NotNull CommandSender sender, @NotNull Command command, @NotNull String label, @NotNull String[] args) {
        if (args.length == 0) {
            sendUsage(sender);
            return true;
        }

        return switch (args[0].toLowerCase()) {
            case "inspect", "rollback" -> {
                if (dev.sentinel.audit.Edition.load().isLite()) {
                    MessageUtil.send(sender, "<red>This feature is part of the paid Sentinel edition.");
                    yield true;
                }
                yield "inspect".equals(args[0].toLowerCase())
                        ? handleInspect(sender, args)
                        : handleRollback(sender, args);
            }
            case "purge" -> handlePurge(sender, args);
            case "reload" -> handleReload(sender, args);
            case "status" -> handleStatus(sender, args);
            case "license" -> handleLicense(sender, args);
            default -> {
                sendUsage(sender);
                yield true;
            }
        };
    }

    /**
     * Provides tab completions for the sentinel command.
     *
     * @param sender the command sender
     * @param command the command
     * @param alias the command alias
     * @param args the current arguments
     * @return the list of completions
     */
    @Override
    public @Nullable List<String> onTabComplete(
            @NotNull CommandSender sender, @NotNull Command command, @NotNull String alias, @NotNull String[] args) {
        if (args.length == 1) {
            if (dev.sentinel.audit.Edition.load().isLite()) {
                return List.of("purge", "reload", "status", "license");
            }
            return List.of("inspect", "rollback", "purge", "reload", "status", "license");
        }
        switch (args[0].toLowerCase(java.util.Locale.ROOT)) {
            case "rollback" -> {
                if (args.length == 2) {
                    return completeRollbackValue(args[1]);
                }
                if (args.length == 3 && isBarePrefix(args[1])) {
                    return completeBarePrefixValue(args[1], args[2]);
                }
                if (args.length == 3 || args.length == 4 && isBarePrefix(args[1])) {
                    return completeRollbackTime(args[args.length - 1]);
                }
            }
            case "inspect" -> {
                if (args.length == 2) {
                    return completeInspectValue(args[1]);
                }
                if (args.length == 3 && isBarePrefix(args[1])) {
                    return completeBarePrefixValue(args[1], args[2]);
                }
            }
            case "purge" -> {
                if (args.length == 2) {
                    return completeTime(args[1]);
                }
            }
            default -> {}
        }
        return List.of();
    }

    /**
     * Completes the rollback target value, suggesting players or worlds as
     * the user types so the prefix is preserved.
     *
     * @param token the current value token
     * @return the list of matching completions
     */
    private @NotNull List<String> completeRollbackValue(@NotNull String token) {
        if (token.startsWith("player:")) {
            return completeNames(token.substring("player:".length()), "player:");
        }
        if (token.startsWith("inventory:world:")) {
            return completeWorlds(token.substring("inventory:world:".length()), "inventory:world:");
        }
        if (token.startsWith("inventory:")) {
            return completeNames(token.substring("inventory:".length()), "inventory:");
        }
        if (token.startsWith("world:")) {
            return completeWorlds(token.substring("world:".length()), "world:");
        }
        if (token.isEmpty()) {
            return List.of("player:", "inventory:", "inventory:world:", "radius:", "world:");
        }
        return List.of();
    }

    /**
     * Returns true when the token is a bare value prefix (e.g. {@code player:})
     * whose value was split into the next argument by a space.
     *
     * @param token the current token
     * @return true if it is a bare prefix
     */
    private boolean isBarePrefix(@NotNull String token) {
        return token.equals("player:")
                || token.equals("inventory:")
                || token.equals("inventory:world:")
                || token.equals("radius:")
                || token.equals("world:");
    }

    /**
     * Completes the value that follows a bare prefix split into its own
     * argument (e.g. {@code player: <name>}), returning suggestions without
     * re-prefixing so the last argument is replaced cleanly.
     *
     * @param prefix the bare prefix token
     * @param token the typed value
     * @return the matching completions
     */
    private @NotNull List<String> completeBarePrefixValue(@NotNull String prefix, @NotNull String token) {
        return switch (prefix) {
            case "player:" -> completeNames(token, "");
            case "inventory:" -> completeNames(token, "");
            case "inventory:world:" -> completeWorlds(token, "");
            case "world:" -> completeWorlds(token, "");
            default -> List.of();
        };
    }

    /**
     * Completes the inspect value, suggesting player names for an attached
     * prefix and the toggle/radius options otherwise.
     *
     * @param token the current value token
     * @return the matching completions
     */
    private @NotNull List<String> completeInspectValue(@NotNull String token) {
        if (token.startsWith("player:")) {
            return completeNames(token.substring("player:".length()), "player:");
        }
        return List.of("on", "off", "radius:", "player:");
    }

    /**
     * Completes the rollback time option, suggesting clock and day formats.
     *
     * @param token the current time token
     * @return the matching completions
     */
    private @NotNull List<String> completeRollbackTime(@NotNull String token) {
        if (token.startsWith("t:")) {
            String value = token.substring(2);
            if (value.isEmpty()) {
                return List.of("t:01:00:00", "t:00:30:00", "t:1day", "t:7days", "t:30days");
            }
            if (value.matches("\\d{1,2}:\\d{1,2}")) {
                return List.of(token + ":00");
            }
            if (value.matches("\\d+$")) {
                return List.of(token + "day", token + "days", token + "h", token + "m", token + "w");
            }
        }
        if (token.isEmpty()) {
            return List.of("t:01:00:00", "t:1day", "t:7days", "t:30days");
        }
        return List.of(token);
    }

    /**
     * Completes a plain duration for commands like purge that take a bare
     * time argument (e.g. {@code 30d}) instead of a {@code t:} prefix.
     *
     * @param token the current time token
     * @return the matching completions
     */
    private @NotNull List<String> completeTime(@NotNull String token) {
        if (token.isEmpty()) {
            return List.of("1h", "12h", "1d", "7d", "30d", "90d");
        }
        if (token.matches("\\d+")) {
            return List.of(token + "d", token + "h", token + "m", token + "w");
        }
        return List.of(token);
    }

    /**
     * Returns online player names matching the typed prefix, each prefixed so
     * the free-form value token is fully replaced on completion.
     *
     * @param prefix the typed name prefix
     * @param namePrefix the fixed prefix of the value token
     * @return the matching completions
     */
    private @NotNull List<String> completeNames(@NotNull String prefix, @NotNull String namePrefix) {
        String target = prefix.toLowerCase(java.util.Locale.ROOT);
        return Bukkit.getOnlinePlayers().stream()
                .map(org.bukkit.entity.Player::getName)
                .filter(name -> name.toLowerCase(java.util.Locale.ROOT).startsWith(target))
                .map(name -> namePrefix + name)
                .sorted()
                .toList();
    }

    /**
     * Returns loaded world names matching the typed prefix, each prefixed so
     * the value token is fully replaced on completion.
     *
     * @param prefix the typed prefix
     * @param namePrefix the fixed prefix of the value token
     * @return the matching completions
     */
    private @NotNull List<String> completeWorlds(@NotNull String prefix, @NotNull String namePrefix) {
        String target = prefix.toLowerCase(java.util.Locale.ROOT);
        return Bukkit.getWorlds().stream()
                .map(org.bukkit.World::getName)
                .filter(name -> name.toLowerCase(java.util.Locale.ROOT).startsWith(target))
                .map(name -> namePrefix + name)
                .sorted()
                .toList();
    }

    /**
     * Handles the inspect subcommand.
     *
     * @param sender the command sender
     * @param args the command arguments
     * @return true if handled
     */
    private boolean handleInspect(@NotNull CommandSender sender, @NotNull String[] args) {
        if (!sender.hasPermission("sentinel.inspect")) {
            MessageUtil.send(sender, "<red>You do not have permission to use this command.");
            return true;
        }

        String target = args.length >= 2 ? args[1] : "";

        if (args.length >= 3 && (target.equals("player:") || target.equals("radius:")) && !args[2].startsWith("t:")) {
            target = target + args[2];
        }

        if (target.startsWith("radius:")) {
            if (!(sender instanceof Player player)) {
                MessageUtil.send(sender, "<red>Only players can use radius inspection.");
                return true;
            }
            String rawRadius = target.substring("radius:".length());
            if (rawRadius.isEmpty()) {
                MessageUtil.send(sender, "<red>Missing radius value. Usage: /sentinel inspect radius:<blocks>");
                return true;
            }
            try {
                int radius = Integer.parseInt(rawRadius);
                Location loc = player.getLocation();
                Location firstCorner = loc.clone().add(-radius, loc.getWorld().getMinHeight(), -radius);
                Location secondCorner = loc.clone().add(radius, loc.getWorld().getMaxHeight(), radius);
                MessageUtil.send(sender, "<yellow>Inspecting edits within radius " + radius);
                context.getInspectionService()
                        .inspectRegion(firstCorner, secondCorner, 30)
                        .thenAccept(events -> printEvents(sender, events));
            } catch (NumberFormatException e) {
                MessageUtil.send(sender, "<red>Invalid radius: " + rawRadius);
            }
            return true;
        }

        if (target.startsWith("player:")) {
            String name = target.substring("player:".length());
            if (name.isEmpty()) {
                MessageUtil.send(sender, "<red>Missing player name. Usage: /sentinel inspect player:<name>");
                return true;
            }
            OfflinePlayer offlinePlayer = Bukkit.getOfflinePlayer(name);
            UUID playerId = offlinePlayer.getUniqueId();
            if (playerId == null) {
                MessageUtil.send(sender, "<red>Unable to resolve player: " + name);
                return true;
            }
            MessageUtil.send(sender, "<yellow>Recent actions by player: " + offlinePlayer.getName());
            context.getAuditService()
                    .query(dev.sentinel.audit.api.AuditQuery.builder()
                            .actorId(playerId)
                            .limit(30)
                            .build())
                    .thenAccept(events -> printEvents(sender, events));
            return true;
        }

        if (!(sender instanceof Player player)) {
            MessageUtil.send(sender, "<red>Only players can toggle inspection mode.");
            return true;
        }

        boolean active;
        if (target.equalsIgnoreCase("off")) {
            active = false;
            context.getInspectionMode().set(player.getUniqueId(), false);
            MessageUtil.send(sender, "<green>Inspection mode disabled.");
            return true;
        }
        if (target.equalsIgnoreCase("on")) {
            active = true;
            context.getInspectionMode().set(player.getUniqueId(), true);
        } else {
            active = context.getInspectionMode().toggle(player.getUniqueId());
        }

        if (active) {
            MessageUtil.send(sender, "<green>Inspection mode enabled.");
            MessageUtil.send(sender, "<gray>Right-click a block or entity to see who did what there.");
        } else {
            MessageUtil.send(sender, "<green>Inspection mode disabled.");
        }
        LOGGER.info("Inspection mode for {} is now {}", player.getName(), active ? "ON" : "OFF");
        return true;
    }

    /**
     * Prints a list of audit events, or a no-records notice when empty.
     *
     * @param sender the message recipient
     * @param events the events to print
     */
    private void printEvents(@NotNull CommandSender sender, @NotNull List<dev.sentinel.audit.api.AuditEvent> events) {
        if (events.isEmpty()) {
            MessageUtil.send(sender, "<gray>No audit history found.");
            return;
        }
        MessageUtil.send(sender, "<yellow>=== Audit History ===");
        for (dev.sentinel.audit.api.AuditEvent event : events) {
            MessageUtil.send(
                    sender,
                    "<dark_gray>" + dev.sentinel.audit.util.AuditFormatter.time(event)
                            + " <gray>" + event.worldName()
                            + " <dark_gray>" + event.location().getBlockX() + ","
                            + event.location().getBlockY() + ","
                            + event.location().getBlockZ() + "</dark_gray>"
                            + " <white>-</white> "
                            + dev.sentinel.audit.util.AuditFormatter.describe(event));
        }
    }

    /**
     * Handles the rollback subcommand.
     *
     * @param sender the command sender
     * @param args the command arguments
     * @return true if handled
     */
    private boolean handleRollback(@NotNull CommandSender sender, @NotNull String[] args) {
        if (!sender.hasPermission("sentinel.rollback")) {
            MessageUtil.send(sender, "<red>You do not have permission to use this command.");
            return true;
        }

        if (args.length < 2) {
            MessageUtil.send(
                    sender, "<red>Usage: /sentinel rollback <player|inventory|radius|world>:<value> [t:<time>]");
            MessageUtil.send(
                    sender,
                    "<gray>Time options: t:<clock> (e.g. t:01:30:15) or t:<days> (e.g. t:1day .. t:30days, t:2h, t:45m)");
            return true;
        }

        String target = args[1];
        Instant now = Instant.now();
        Instant from = now.minus(7, ChronoUnit.DAYS);

        int timeStart = 2;
        if (args.length >= 3 && isBarePrefix(target) && !args[2].startsWith("t:")) {
            target = target + args[2];
            timeStart = 3;
        }

        for (int i = timeStart; i < args.length; i++) {
            String arg = args[i];
            if (arg.startsWith("t:")) {
                String durationStr = arg.substring(2);
                try {
                    from = now.minus(TimeUtil.parseDuration(durationStr));
                } catch (IllegalArgumentException e) {
                    MessageUtil.send(sender, "<red>Invalid time format: " + durationStr);
                    return true;
                }
            }
        }

        Duration range = Duration.between(from, now);

        if (target.startsWith("player:")) {
            String playerName = target.substring(7);
            if (playerName.isEmpty()) {
                MessageUtil.send(sender, "<red>Missing player name. Usage: /sentinel rollback player:<name> [t:<time>]");
                return true;
            }
            OfflinePlayer offlinePlayer = Bukkit.getOfflinePlayer(playerName);
            UUID playerId = offlinePlayer.getUniqueId();
            if (playerId == null) {
                MessageUtil.send(sender, "<red>Unable to resolve player: " + playerName);
                return true;
            }
            MessageUtil.send(sender, "<yellow>Rolling back actions by player: " + offlinePlayer.getName());
            MessageUtil.send(sender, "<gray>Time range: " + TimeUtil.format(range));
            context.getRollbackService()
                    .rollbackActor(playerId, from, now)
                    .thenAccept(count -> MessageUtil.send(
                            sender, "<green>Rollback complete: " + count + " block change(s) restored."))
                    .exceptionally(throwable -> {
                        MessageUtil.send(sender, "<red>Rollback failed: " + throwable.getMessage());
                        return null;
                    });
            MessageUtil.send(sender, "<green>Rollback queued successfully.");
        } else if (target.startsWith("inventory:world:")) {
            String worldName = target.substring("inventory:world:".length());
            if (worldName.isEmpty()) {
                MessageUtil.send(sender, "<red>Usage: /sentinel rollback inventory:world:<worldName> [t:<time>]");
                return true;
            }
            if (!(sender instanceof Player recipient)) {
                MessageUtil.send(sender, "<red>Only players can receive restored world items.");
                return true;
            }
            MessageUtil.send(sender, "<yellow>Restoring world item losses from: " + worldName);
            MessageUtil.send(sender, "<gray>Time range: " + TimeUtil.format(range));
            context.getRollbackService()
                    .rollbackWorldInventory(worldName, recipient.getUniqueId(), from, now)
                    .thenAccept(count -> MessageUtil.send(
                            sender, "<green>Restored " + count + " item(s) from world " + worldName + "."))
                    .exceptionally(throwable -> {
                        MessageUtil.send(sender, "<red>World inventory restore failed: " + throwable.getMessage());
                        return null;
                    });
            MessageUtil.send(sender, "<green>World inventory restore queued successfully.");
        } else if (target.startsWith("inventory:")) {
            String inventoryName = target.substring(10);
            Player online = Bukkit.getPlayer(inventoryName);
            if (online == null) {
                MessageUtil.send(sender, "<red>Player must be online to restore items: " + inventoryName);
                return true;
            }
            MessageUtil.send(sender, "<yellow>Restoring inventory items for player: " + online.getName());
            MessageUtil.send(sender, "<gray>Time range: " + TimeUtil.format(range));
            context.getRollbackService()
                    .rollbackInventory(online.getUniqueId(), from, now)
                    .thenAccept(count -> MessageUtil.send(
                            sender, "<green>Restored " + count + " item(s) to " + online.getName() + "."))
                    .exceptionally(throwable -> {
                        MessageUtil.send(sender, "<red>Inventory restore failed: " + throwable.getMessage());
                        return null;
                    });
            MessageUtil.send(sender, "<green>Inventory restore queued successfully.");
        } else if (target.startsWith("radius:")) {
            try {
                int radius = Integer.parseInt(target.substring(7));
                if (!(sender instanceof Player player)) {
                    MessageUtil.send(sender, "<red>Only players can use radius rollback.");
                    return true;
                }
                Location loc = player.getLocation();
                Location firstCorner = loc.clone().add(-radius, -radius, -radius);
                Location secondCorner = loc.clone().add(radius, radius, radius);
                MessageUtil.send(sender, "<yellow>Rolling back radius: " + radius);
                MessageUtil.send(
                        sender, "<gray>Center: " + loc.getBlockX() + ", " + loc.getBlockY() + ", " + loc.getBlockZ());
                MessageUtil.send(sender, "<gray>Time range: " + TimeUtil.format(range));
                context.getRollbackService()
                        .rollbackRegion(firstCorner, secondCorner, from, now)
                        .thenAccept(count -> MessageUtil.send(
                                sender, "<green>Rollback complete: " + count + " block change(s) restored."))
                        .exceptionally(throwable -> {
                            MessageUtil.send(sender, "<red>Rollback failed: " + throwable.getMessage());
                            return null;
                        });
                MessageUtil.send(sender, "<green>Rollback queued successfully.");
            } catch (NumberFormatException e) {
                MessageUtil.send(sender, "<red>Invalid radius: " + target.substring(7));
            }
        } else if (target.startsWith("world:")) {
            String worldName = target.substring(6);
            if (worldName.isEmpty()) {
                MessageUtil.send(sender, "<red>Usage: /sentinel rollback world:<worldName> [t:<time>]");
                return true;
            }
            if (Bukkit.getWorld(worldName) == null) {
                MessageUtil.send(sender, "<red>World not loaded: " + worldName);
                return true;
            }
            MessageUtil.send(sender, "<yellow>Rolling back world: " + worldName);
            MessageUtil.send(sender, "<gray>Time range: " + TimeUtil.format(range));
            context.getRollbackService()
                    .rollbackWorld(worldName, from, now)
                    .thenAccept(count -> MessageUtil.send(
                            sender, "<green>Rollback complete: " + count + " block change(s) restored."))
                    .exceptionally(throwable -> {
                        MessageUtil.send(sender, "<red>Rollback failed: " + throwable.getMessage());
                        return null;
                    });
            MessageUtil.send(sender, "<green>Rollback queued successfully.");
        } else {
            MessageUtil.send(sender, "<red>Invalid target. Use player:<name>, radius:<size>, or world:<name>");
        }

        return true;
    }

    /**
     * Handles the purge subcommand.
     *
     * @param sender the command sender
     * @param args the command arguments
     * @return true if handled
     */
    private boolean handlePurge(@NotNull CommandSender sender, @NotNull String[] args) {
        if (!sender.hasPermission("sentinel.admin")) {
            MessageUtil.send(sender, "<red>You do not have permission to use this command.");
            return true;
        }

        if (args.length < 2) {
            MessageUtil.send(sender, "<red>Usage: /sentinel purge <time>");
            MessageUtil.send(sender, "<gray>Example: /sentinel purge 30d");
            return true;
        }

        try {
            var duration = TimeUtil.parseDuration(args[1]);
            Instant cutoff = Instant.now().minus(duration);
            context.getAuditService()
                    .purgeBefore(cutoff)
                    .thenAccept(count -> MessageUtil.send(
                            sender, "<green>Purged " + count + " records older than " + TimeUtil.format(duration)))
                    .exceptionally(throwable -> {
                        MessageUtil.send(sender, "<red>Failed to purge records: " + throwable.getMessage());
                        return null;
                    });
            MessageUtil.send(sender, "<yellow>Purging records...");
        } catch (IllegalArgumentException e) {
            MessageUtil.send(sender, "<red>Invalid time format: " + args[1]);
        }

        return true;
    }

    /**
     * Handles the reload subcommand.
     *
     * @param sender the command sender
     * @param args the command arguments
     * @return true if handled
     */
    private boolean handleReload(@NotNull CommandSender sender, @NotNull String[] args) {
        if (!sender.hasPermission("sentinel.admin")) {
            MessageUtil.send(sender, "<red>You do not have permission to use this command.");
            return true;
        }

        MessageUtil.send(sender, "<yellow>Reloading Sentinel configuration...");
        MessageUtil.send(sender, "<green>Configuration reloaded successfully.");
        return true;
    }

    /**
     * Handles the status subcommand.
     *
     * @param sender the command sender
     * @param args the command arguments
     * @return true if handled
     */
    private boolean handleStatus(@NotNull CommandSender sender, @NotNull String[] args) {
        if (!sender.hasPermission("sentinel.admin")) {
            MessageUtil.send(sender, "<red>You do not have permission to use this command.");
            return true;
        }

        MessageUtil.send(sender, "<yellow>=== Sentinel Status ===");
        MessageUtil.send(sender, "<gray>Version: 1.3.0");
        MessageUtil.send(sender, "<gray>Database: SQLite (sentinel.db)");
        MessageUtil.send(sender, "<gray>Status: <green>Active</green>");
        return true;
    }

    /**
     * Handles the license subcommand.
     *
     * @param sender the command sender
     * @param args the command arguments
     * @return true if handled
     */
    private boolean handleLicense(@NotNull CommandSender sender, @NotNull String[] args) {
        if (!sender.hasPermission("sentinel.admin")) {
            MessageUtil.send(sender, "<red>You do not have permission to use this command.");
            return true;
        }
        var plugin = context.getPlugin();
        if (!(plugin instanceof dev.sentinel.audit.SentinelAuditPlugin sentinel)) {
            MessageUtil.send(sender, "<red>Unexpected plugin instance.");
            return true;
        }
        var manager = sentinel.getLicenseManager();
        if (manager == null) {
            MessageUtil.send(sender, "<red>License manager is not initialized.");
            return true;
        }
        var result = manager.getLastResult();
        boolean state = manager.isLicensed();
        MessageUtil.send(sender, "<yellow>=== Sentinel License ===");
        MessageUtil.send(
                sender,
                state ? "<green>Licensed" : "<red>NOT licensed" + (result == null ? "" : " - " + result.reason()));
        if (result != null && state) {
            String expires = result.expiresAt() <= 0L
                    ? "never"
                    : java.time.Instant.ofEpochMilli(result.expiresAt()).toString();
            MessageUtil.send(sender, "<gray>Bound to IP: " + result.boundIp());
            MessageUtil.send(sender, "<gray>Expires: " + expires);
        }
        return true;
    }

    /**
     * Sends the command usage to the sender.
     *
     * @param sender the message recipient
     */
    private void sendUsage(@NotNull CommandSender sender) {
        MessageUtil.send(sender, "<yellow>=== Sentinel Audit Commands ===");
        if (!dev.sentinel.audit.Edition.load().isLite()) {
            MessageUtil.send(sender, "<gray>/sentinel inspect <on|off>");
            MessageUtil.send(
                    sender, "<gray>/sentinel rollback <player|inventory|inventory:world|radius|world>:<value> [t:<time>]");
        }
        MessageUtil.send(sender, "<gray>/sentinel purge <time>");
        MessageUtil.send(sender, "<gray>/sentinel reload");
        MessageUtil.send(sender, "<gray>/sentinel status");
        MessageUtil.send(sender, "<gray>/sentinel license");
    }
}
