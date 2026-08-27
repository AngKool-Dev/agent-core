package dev.mcplugins.echorealms;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Material;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.List;
import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;

public final class EchoCommand implements CommandExecutor, TabCompleter {

    private final EchoRealmsPlugin plugin;

    public EchoCommand(EchoRealmsPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        String name = cmd.getName().toLowerCase(Locale.ROOT);
        if (name.equals("er") && args.length == 0) {
            showMenu(sender);
            return true;
        }
        String sub = args.length == 0 ? "list" : args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "list" -> {
                for (String line : plugin.manager().listLines()) {
                    info(sender, line);
                }
            }
            case "attune" -> attune(sender);
            case "scan" -> {
                if (admin(sender)) {
                    return true;
                }
                plugin.manager().lifecyclePass();
                ok(sender, "Echo scan complete.");
                for (String line : plugin.manager().listLines()) {
                    info(sender, line);
                }
            }
            case "reload" -> {
                if (admin(sender)) {
                    return true;
                }
                plugin.reloadSettings();
                ok(sender, "EchoRealms configuration reloaded.");
            }
            default -> err(sender, "Usage: /echo [list|attune|scan|reload]");
        }
        return true;
    }

    private void showMenu(CommandSender sender) {
        Component title = Component.text("EchoRealms", NamedTextColor.LIGHT_PURPLE)
                .decorate(TextDecoration.BOLD);
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
        sender.sendMessage(title);
        sender.sendMessage(Component.text("Echo sites, memory shards, and XP attunement", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
        sender.sendMessage(Component.text("Commands:", NamedTextColor.YELLOW));
        sender.sendMessage(Component.text("/er list — View nearby echo sites", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/er attune — Draw experience and memory shards", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/er scan — Run a lifecycle pass on echoes", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/er reload — Reload EchoRealms config", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("How-tos:", NamedTextColor.YELLOW));
        sender.sendMessage(Component.text("\u2022 Find violet holograms at echo sites", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("\u2022 Deep echoes grant more XP but take longer to refresh", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("\u2022 Memory shards are crafting material for ChronoShards", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
    }

    private void attune(CommandSender sender) {
        if (!(sender instanceof Player p)) {
            err(sender, "Attunement requires a living soul. Console not accepted.");
            return;
        }
        EchoManager.ManifestedSite site = plugin.manager().at(p.getLocation());
        if (site == null) {
            info(p, "No echo reaches this place. Seek the violet holograms.");
            return;
        }
        if (!plugin.manager().attuneAllowed(site, p)) {
            info(p, "You have already drawn from this echo recently. Its memory needs time to renew.");
            return;
        }
        boolean deep = plugin.manager().isDeep(site.key());
        int xp = deep ? plugin.settings().deepXp : plugin.settings().attuneXp;
        p.giveExp(xp);
        plugin.manager().markAttuned(site, p);
        String lore = plugin.manager().loreFor(site, p);
        p.sendMessage(Component.text("\u29E1 " + lore, NamedTextColor.LIGHT_PURPLE));
        StringBuilder msg = new StringBuilder("The echo grants you ").append(xp).append(" experience");
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        if (rnd.nextDouble() < plugin.settings().shardChance) {
            int n = rnd.nextInt(plugin.settings().shardMin, plugin.settings().shardMax + 1);
            ItemStack shard = new ItemStack(Material.AMETHYST_SHARD, n);
            var meta = shard.getItemMeta();
            meta.displayName(Component.text("Memory Shard", NamedTextColor.LIGHT_PURPLE)
                    .decoration(TextDecoration.ITALIC, false));
            meta.lore(List.of(Component.text("Crystallised remnant of a fading build.", NamedTextColor.GRAY)
                    .decoration(TextDecoration.ITALIC, false)));
            shard.setItemMeta(meta);
            var leftover = p.getInventory().addItem(shard);
            leftover.values().forEach(rest ->
                    p.getWorld().dropItemNaturally(p.getLocation(), rest));
            msg.append(", and ").append(n).append(" Memory Shard").append(n > 1 ? "s" : "")
                    .append(" condense in your hands");
        }
        msg.append(deep ? ". The DEEP echo lingers on your mind." : ".");
        ok(p, msg.toString());
    }

    private boolean admin(CommandSender sender) {
        if (!sender.hasPermission("echorealms.admin")) {
            err(sender, "You need echorealms.admin.");
            return true;
        }
        return false;
    }

    private void ok(CommandSender sender, String msg) {
        sender.sendMessage(Component.text(msg, NamedTextColor.GREEN));
    }

    private void info(CommandSender sender, String msg) {
        sender.sendMessage(Component.text(msg, NamedTextColor.GRAY));
    }

    private void err(CommandSender sender, String msg) {
        sender.sendMessage(Component.text(msg, NamedTextColor.RED));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command cmd, String alias, String[] args) {
        if (args.length == 1) {
            String p = args[0].toLowerCase(Locale.ROOT);
            return List.of("list", "attune", "scan", "reload").stream()
                    .filter(s -> s.startsWith(p)).toList();
        }
        return List.of();
    }
}
