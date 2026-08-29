package dev.mcplugins.bazaar;

import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.Material;

import java.util.*;
import java.util.stream.Collectors;

public class BazaarCommand implements CommandExecutor, TabCompleter {

    private final BazaarPlugin plugin;
    private final BazaarManager manager;
    private final BazaarGUI gui;

    public BazaarCommand(BazaarPlugin plugin, BazaarManager manager, BazaarGUI gui) {
        this.plugin = plugin;
        this.manager = manager;
        this.gui = gui;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }
        Player player = (Player) sender;

        if (args.length == 0 || args[0].equalsIgnoreCase("gui") || args[0].equalsIgnoreCase("open")) {
            gui.open(player);
            return true;
        }
        if (args[0].equalsIgnoreCase("mylistings")) {
            gui.openMyListings(player);
            return true;
        }
        if (args[0].equalsIgnoreCase("help")) {
            sendHelp(player);
            return true;
        }
        if (args[0].equalsIgnoreCase("sell")) {
            if (!player.hasPermission("bazaar.sell")) {
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.no-permission", "&cYou don't have permission to do that.")));
                return true;
            }
            if (args.length < 2) {
                player.sendMessage(plugin.colorize("§cUsage: /bazaar sell <price> [duration]"));
                return true;
            }
            double price;
            try {
                price = Double.parseDouble(args[1]);
            } catch (NumberFormatException e) {
                player.sendMessage(plugin.colorize("§cInvalid price."));
                return true;
            }
            long duration = plugin.getConfig().getLong("settings.listing-duration-seconds", 604800);
            if (args.length >= 3) {
                try {
                    duration = Long.parseLong(args[2]);
                } catch (NumberFormatException e) {
                    player.sendMessage(plugin.colorize("§cInvalid duration."));
                    return true;
                }
            }
            ItemStack inHand = player.getInventory().getItemInMainHand();
            if (inHand == null || inHand.getType() == Material.AIR) {
                player.sendMessage(plugin.colorize("§cYou must hold an item to sell."));
                return true;
            }
            if (plugin.getConfig().getStringList("items.blacklist").contains(inHand.getType().name())) {
                player.sendMessage(plugin.colorize("§cThis item cannot be sold."));
                return true;
            }
            int maxListings = plugin.getConfig().getInt("settings.max-listings-per-player", 10);
            if (manager.getPlayerAuctions(player.getUniqueId()).size() >= maxListings) {
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.max-listings", "&cYou have reached the maximum number of listings.")));
                return true;
            }
            manager.createAuction(player.getUniqueId(), inHand.clone(), price, duration);
            player.getInventory().setItemInMainHand(new ItemStack(Material.AIR));
            player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auction-created", "&aAuction created for &e{item}&a at &e{price}&a.")
                    .replace("{item}", inHand.getType().name())
                    .replace("{price}", String.valueOf(price))));
            return true;
        }
        if (args[0].equalsIgnoreCase("list")) {
            if (!player.hasPermission("bazaar.list")) {
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.no-permission", "&cYou don't have permission to do that.")));
                return true;
            }
            List<BazaarManager.BazaarItem> playerAuctions = manager.getPlayerAuctions(player.getUniqueId());
            if (playerAuctions.isEmpty()) {
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.no-auctions", "&7No auctions found.")));
                return true;
            }
            player.sendMessage(plugin.colorize("§6Your Auctions:"));
            for (BazaarManager.BazaarItem auction : playerAuctions) {
                player.sendMessage(plugin.colorize("§8- §e" + auction.itemStack.getType().name() + " §7x" + auction.itemStack.getAmount() + " §7for §a" + auction.price));
            }
            return true;
        }
        if (args[0].equalsIgnoreCase("cancel")) {
            if (!player.hasPermission("bazaar.cancel")) {
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.no-permission", "&cYou don't have permission to do that.")));
                return true;
            }
            if (args.length < 2) {
                player.sendMessage(plugin.colorize("§cUsage: /bazaar cancel <id>"));
                return true;
            }
            Optional<BazaarManager.BazaarItem> auction = manager.getAuction(args[1]);
            if (auction.isEmpty() || !auction.get().seller.equals(player.getUniqueId())) {
                player.sendMessage(plugin.colorize("§cAuction not found."));
                return true;
            }
            manager.cancelAuction(args[1]);
            ItemStack item = auction.get().itemStack.clone();
            HashMap<Integer, ItemStack> leftover = player.getInventory().addItem(item);
            if (!leftover.isEmpty()) {
                player.getWorld().dropItemNaturally(player.getLocation(), leftover.get(0));
            }
            player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auction-cancelled", "&aAuction cancelled.")));
            return true;
        }
        if (args[0].equalsIgnoreCase("search")) {
            gui.open(player);
            return true;
        }
        sendHelp(player);
        return true;
    }

    private void sendHelp(Player player) {
        player.sendMessage(plugin.colorize("§6--- Bazaar Help ---"));
        player.sendMessage(plugin.colorize("§e/bazaar §7- Open bazaar"));
        player.sendMessage(plugin.colorize("§e/bazaar mylistings §7- View your listings"));
        player.sendMessage(plugin.colorize("§e/bazaar sell <price> [duration] §7- Sell item in hand"));
        player.sendMessage(plugin.colorize("§e/bazaar list §7- View your listings"));
        player.sendMessage(plugin.colorize("§e/bazaar cancel <id> §7- Cancel listing"));
        player.sendMessage(plugin.colorize("§e/bazaar search §7- Search auctions"));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!(sender instanceof Player)) return Collections.emptyList();
        if (args.length == 1) {
            return Arrays.asList("sell", "list", "cancel", "search", "help").stream()
                    .filter(s -> s.startsWith(args[0].toLowerCase()))
                    .collect(Collectors.toList());
        }
        if (args.length == 2 && args[0].equalsIgnoreCase("cancel")) {
            Player player = (Player) sender;
            return manager.getPlayerAuctions(player.getUniqueId()).stream()
                    .map(a -> a.id)
                    .filter(id -> id.startsWith(args[1]))
                    .collect(Collectors.toList());
        }
        return Collections.emptyList();
    }
}
