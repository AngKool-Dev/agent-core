package dev.mcplugins.purge;

import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Item;
import org.bukkit.event.Listener;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

public final class PurgePlugin extends JavaPlugin implements CommandExecutor, TabCompleter {

    private PurgeConfig config;
    private PurgeTask task;
    private BukkitTask scheduler;
    private BukkitTask itemCollector;
    private final AtomicLong asyncItemsRemoved = new AtomicLong(0);

    @Override
    public void onEnable() {
        saveDefaultConfig();
        config = new PurgeConfig(this);
        task = new PurgeTask(this);
        getServer().getPluginManager().registerEvents(task, this);

        var purgeCmd = getCommand("purge");
        if (purgeCmd != null) {
            purgeCmd.setExecutor(this);
            purgeCmd.setTabCompleter(this);
        }

        scheduleTask();
        startItemCollector();
        getLogger().info("Purge enabled.");
    }

    @Override
    public void onDisable() {
        if (scheduler != null) {
            scheduler.cancel();
            scheduler = null;
        }
        if (itemCollector != null) {
            itemCollector.cancel();
            itemCollector = null;
        }
        task = null;
        getLogger().info("Purge disabled.");
    }

    public void reloadSettings() {
        config.reload(this);
        scheduleTask();
        restartItemCollector();
    }

    private void scheduleTask() {
        if (scheduler != null) {
            scheduler.cancel();
            scheduler = null;
        }
        if (!config.isEnabled()) {
            task = null;
            return;
        }
        task = new PurgeTask(this);
        getServer().getPluginManager().registerEvents(task, this);
        scheduler = task.runTaskTimer(this, 1L, 1L);
        getLogger().info("Auto-purge scheduled every " + (config.getIntervalSeconds()) + " seconds.");
    }

    private void startItemCollector() {
        if (itemCollector != null) {
            itemCollector.cancel();
        }
        long interval = config.getIntervalTicks();
        long delay = config.getWarnBeforeTicks() > 0 ? config.getWarnBeforeTicks() : 20L;
        itemCollector = Bukkit.getScheduler().runTaskTimer(this, () -> {
            if (!config.isEnabled()) return;
            asyncItemsRemoved.set(0);
            for (World world : Bukkit.getWorlds()) {
                if (config.clearing.mobs.disabledWorlds.contains(world.getName())) continue;
                if (!config.clearing.itemsSettings.enabled) continue;
                for (Item item : world.getEntitiesByClass(Item.class)) {
                    if (!item.isDead() && task.shouldRemove(item, config)) {
                        item.remove();
                        asyncItemsRemoved.incrementAndGet();
                    }
                }
                if (config.clearing.mobs.clearFallingBlocks) {
                    for (org.bukkit.entity.FallingBlock fb : world.getEntitiesByClass(org.bukkit.entity.FallingBlock.class)) {
                        if (!fb.isDead()) {
                            fb.remove();
                            asyncItemsRemoved.incrementAndGet();
                        }
                    }
                }
            }
        }, delay, interval);
    }

    private void restartItemCollector() {
        if (itemCollector != null) {
            itemCollector.cancel();
            itemCollector = null;
        }
        startItemCollector();
    }

    public long getAsyncItemsRemoved() {
        return asyncItemsRemoved.get();
    }

    public PurgeConfig settings() {
        return config;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        String perm = "purge.use";
        if (args.length > 0) {
            String sub = args[0].toLowerCase(Locale.ROOT);
            if (sub.equals("clear")) {
                perm = "purge.clear";
            } else if (sub.equals("reload") || sub.equals("enable") || sub.equals("disable")) {
                perm = "purge.admin";
            }
        }
        if (!sender.hasPermission(perm)) {
            sender.sendMessage(colorize(config.messages.noPermission));
            return true;
        }

        if (args.length == 0 || args[0].equalsIgnoreCase("status")) {
            if (config.isEnabled()) {
                sender.sendMessage(colorize(config.messages.statusEnabled
                        .replace("{interval}", String.valueOf(config.getIntervalSeconds()))));
            } else {
                sender.sendMessage(colorize(config.messages.statusDisabled));
            }
            return true;
        }
        if (args[0].equalsIgnoreCase("enable")) {
            config.setEnabled(true);
            scheduleTask();
            startItemCollector();
            sender.sendMessage(colorize(config.messages.enable
                    .replace("{interval}", String.valueOf(config.getIntervalSeconds()))));
            return true;
        }
        if (args[0].equalsIgnoreCase("disable")) {
            config.setEnabled(false);
            scheduleTask();
            if (itemCollector != null) {
                itemCollector.cancel();
                itemCollector = null;
            }
            sender.sendMessage(colorize(config.messages.disable));
            return true;
        }
        if (args[0].equalsIgnoreCase("clear")) {
            if (!sender.hasPermission("purge.clear")) {
                sender.sendMessage(colorize(config.messages.noPermission));
                return true;
            }
            PurgeResult result = task.clearNow();
            if (result.itemsCleared == 0 && result.hostilesCleared == 0 && result.passivesCleared == 0) {
                sender.sendMessage(colorize(config.messages.nothingToClear));
            } else {
                sender.sendMessage(colorize(config.messages.manualClear
                        .replace("{items}", String.valueOf(result.itemsCleared))
                        .replace("{hostiles}", String.valueOf(result.hostilesCleared))
                        .replace("{passives}", String.valueOf(result.passivesCleared))));
            }
            return true;
        }
        if (args[0].equalsIgnoreCase("reload")) {
            reloadSettings();
            sender.sendMessage(colorize(config.messages.reload));
            return true;
        }
        return false;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!sender.hasPermission("purge.use")) {
            return Collections.emptyList();
        }
        if (args.length == 1) {
            return Arrays.asList("status", "clear", "enable", "disable", "reload").stream()
                    .filter(s -> s.startsWith(args[0].toLowerCase(Locale.ROOT)))
                    .collect(java.util.stream.Collectors.toList());
        }
        return Collections.emptyList();
    }

    public static String colorize(String text) {
        if (text == null) return "";
        return text.replace("&", "§");
    }

    public static final class PurgeResult {
        public final int itemsCleared;
        public final int hostilesCleared;
        public final int passivesCleared;

        public PurgeResult(int itemsCleared, int hostilesCleared, int passivesCleared) {
            this.itemsCleared = itemsCleared;
            this.hostilesCleared = hostilesCleared;
            this.passivesCleared = passivesCleared;
        }
    }
}
