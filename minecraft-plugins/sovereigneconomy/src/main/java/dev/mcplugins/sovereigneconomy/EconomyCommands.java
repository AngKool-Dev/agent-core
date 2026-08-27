package dev.mcplugins.sovereigneconomy;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class EconomyCommands implements CommandExecutor, TabCompleter {

    private static final int PER_PAGE = 8;

    private final SovereignEconomyPlugin plugin;

    public EconomyCommands(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        String name = cmd.getName().toLowerCase(Locale.ROOT);
        if (name.equals("se") && args.length == 0) {
            showMenu(sender);
            return true;
        }
        switch (name) {
            case "money", "bal", "balance" -> money(sender, args);
            case "pay" -> pay(sender, args);
            case "market" -> market(sender, args);
            case "bank" -> bank(sender, args);
            case "eco" -> eco(sender, args);
            default -> err(sender, "Unknown command.");
        }
        return true;
    }

    private void showMenu(CommandSender sender) {
        Component title = Component.text("SovereignEconomy", NamedTextColor.GOLD)
                .decorate(TextDecoration.BOLD);
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
        sender.sendMessage(title);
        sender.sendMessage(Component.text("Player economy, dynamic market, and interest-bearing savings", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
        sender.sendMessage(Component.text("Commands:", NamedTextColor.YELLOW));
        sender.sendMessage(Component.text("/se money — Check your wallet and savings balance", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/se pay <player> <amount> — Send money to another player", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/se market [browse|info|buy|sell] — Trade commodities", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/se bank [deposit|withdraw|status] — Manage your savings", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/se reload — Reload SovereignEconomy config (admin)", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("How-tos:", NamedTextColor.YELLOW));
        sender.sendMessage(Component.text("\u2022 Money sinks: market purchases and mob-spawn gating", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("\u2022 Interest compounds on savings every " + plugin.settings().interestIntervalMinutes + " min", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("\u2022 Market prices fluctuate with inflation", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
    }

    private void money(CommandSender sender, String[] args) {
        Settings s = plugin.settings();
        if (args.length >= 1 && sender.hasPermission("sovoreconomy.admin")) {
            Player target = Bukkit.getPlayerExact(args[0]);
            if (target == null) {
                err(sender, "Player not online: " + args[0]);
                return;
            }
            ok(sender, target.getName() + " holds "
                    + Text.money(plugin.ledger().wallet(target.getUniqueId()), s)
                    + " (savings " + Text.money(plugin.ledger().savings(target.getUniqueId()), s) + ")");
            return;
        }
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        ok(sender, "Wallet: " + Text.money(plugin.ledger().wallet(p.getUniqueId()), s)
                + "   Savings: " + Text.money(plugin.ledger().savings(p.getUniqueId()), s));
    }

    private void pay(CommandSender sender, String[] args) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        if (args.length < 2) {
            err(sender, "Usage: /pay <player> <amount>");
            return;
        }
        Player target = Bukkit.getPlayerExact(args[0]);
        if (target == null) {
            err(sender, "Player not online: " + args[0]);
            return;
        }
        double amount = parseAmount(args[1]);
        if (amount <= 0) {
            err(sender, "Amount must be positive.");
            return;
        }
        if (target.getUniqueId().equals(p.getUniqueId())) {
            err(sender, "You cannot pay yourself.");
            return;
        }
        if (plugin.ledger().pay(p.getUniqueId(), target.getUniqueId(), amount)) {
            ok(sender, "Paid " + Text.money(amount, plugin.settings()) + " to " + target.getName() + ".");
            ok(target, "Received " + Text.money(amount, plugin.settings()) + " from " + p.getName() + ".");
        } else {
            err(sender, "Insufficient funds.");
        }
    }

    private void market(CommandSender sender, String[] args) {
        String sub = args.length == 0 ? "browse" : args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "browse" -> {
                int page = 1;
                if (args.length >= 2) {
                    try {
                        page = Integer.parseInt(args[1]);
                    } catch (NumberFormatException ignored) {
                    }
                }
                for (String line : plugin.market().browsePage(page, PER_PAGE)) {
                    info(sender, line);
                }
            }
            case "info" -> {
                Commodity c = commodityArg(sender, args);
                if (c != null) {
                    for (String line : plugin.market().info(c)) {
                        info(sender, line);
                    }
                }
            }
            case "buy", "sell" -> {
                Player p = requirePlayer(sender);
                if (p == null) {
                    return;
                }
                if (args.length < 3) {
                    err(sender, "Usage: /market " + sub + " <item> <quantity>");
                    return;
                }
                Commodity c = plugin.market().commodity(args[1]);
                if (c == null) {
                    err(sender, "Unknown market item: " + args[1] + ". Try /market browse.");
                    return;
                }
                int qty;
                try {
                    qty = Integer.parseInt(args[2]);
                } catch (NumberFormatException ex) {
                    err(sender, "Quantity must be a number.");
                    return;
                }
                String result = sub.equals("buy")
                        ? plugin.market().buy(p, c, qty)
                        : plugin.market().sell(p, c, qty);
                info(sender, result);
            }
            default -> err(sender, "Usage: /market [browse|info|buy|sell]");
        }
    }

    private void bank(CommandSender sender, String[] args) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        Settings s = plugin.settings();
        String sub = args.length == 0 ? "status" : args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "status" -> info(sender, "Savings: "
                    + Text.money(plugin.ledger().savings(p.getUniqueId()), s)
                    + " earning " + String.format("%.2f%%", plugin.bank().annualRate() * 100)
                    + " per year (interest every " + s.interestIntervalMinutes + " min).");
            case "deposit", "withdraw" -> {
                if (args.length < 2) {
                    err(sender, "Usage: /bank " + sub + " <amount>");
                    return;
                }
                double amount = parseAmount(args[1]);
                boolean done = sub.equals("deposit")
                        ? plugin.ledger().depositSavings(p.getUniqueId(), amount)
                        : plugin.ledger().withdrawSavings(p.getUniqueId(), amount);
                if (done) {
                    ok(sender, sub.substring(0, 1).toUpperCase() + sub.substring(1) + "ed "
                            + Text.money(amount, s) + ". Savings now "
                            + Text.money(plugin.ledger().savings(p.getUniqueId()), s) + ".");
                } else {
                    err(sender, sub.equals("deposit") ? "Insufficient wallet funds." : "Insufficient savings.");
                }
            }
            default -> err(sender, "Usage: /bank [deposit|withdraw|status] [amount]");
        }
    }

    private void eco(CommandSender sender, String[] args) {
        if (!sender.hasPermission("sovoreconomy.admin")) {
            err(sender, "You need sovoreconomy.admin.");
            return;
        }
        String sub = args.length == 0 ? "stats" : args[0].toLowerCase(Locale.ROOT);
        Settings s = plugin.settings();
        switch (sub) {
            case "stats" -> {
                info(sender, "--- Sovereign Economy ---");
                info(sender, "CPI: " + String.format("%.4f", plugin.market().cpi())
                        + "  Inflation vs baseline: "
                        + Text.pct(plugin.market().inflationSinceReference()));
                info(sender, "Central-bank rate: " + String.format("%.2f%%", plugin.bank().annualRate() * 100)
                        + "/year  (target inflation " + String.format("%.1f%%", s.inflationTarget * 100) + ")");
                info(sender, "Accounts: " + plugin.ledger().accountCount()
                        + "   Commodities listed: " + plugin.market().commodities().size());
                List<Map.Entry<java.util.UUID, Double>> top = plugin.ledger().topWallets(5);
                int rank = 1;
                for (Map.Entry<java.util.UUID, Double> e : top) {
                    String name = Bukkit.getOfflinePlayer(e.getKey()).getName();
                    info(sender, String.format(" %d. %-16s %s",
                            rank++, name == null ? e.getKey().toString().substring(0, 8) : name,
                            Text.money(e.getValue(), s)));
                }
            }
            case "give" -> {
                if (args.length < 3) {
                    err(sender, "Usage: /eco give <player> <amount>");
                    return;
                }
                Player t = Bukkit.getPlayerExact(args[1]);
                double amt = args.length >= 3 ? parseAmount(args[2]) : -1;
                if (t == null || amt <= 0) {
                    err(sender, "Player must be online and amount positive.");
                    return;
                }
                plugin.ledger().deposit(t.getUniqueId(), amt);
                ok(sender, "Gave " + Text.money(amt, s) + " to " + t.getName() + ".");
            }
            case "set" -> {
                if (args.length < 3) {
                    err(sender, "Usage: /eco set <player> <amount>");
                    return;
                }
                Player t = Bukkit.getPlayerExact(args[1]);
                double amt = parseAmount(args[2]);
                if (t == null || amt < 0) {
                    err(sender, "Player must be online and amount non-negative.");
                    return;
                }
                plugin.ledger().setWallet(t.getUniqueId(), amt);
                ok(sender, t.getName() + " now holds " + Text.money(amt, s) + ".");
            }
            case "event" -> {
                plugin.events().fireRandom();
                ok(sender, "Event fired.");
            }
            case "reload" -> {
                plugin.reloadSettings();
                ok(sender, "Configuration reloaded.");
            }
            default -> err(sender, "Usage: /eco [stats|give|set|event|reload]");
        }
    }

    private Commodity commodityArg(CommandSender sender, String[] args) {
        if (args.length < 2) {
            err(sender, "Usage: /market info <item>");
            return null;
        }
        Commodity c = plugin.market().commodity(args[1]);
        if (c == null) {
            err(sender, "Unknown market item: " + args[1] + ". Try /market browse.");
        }
        return c;
    }

    private double parseAmount(String raw) {
        try {
            return Double.parseDouble(raw.replace(",", ""));
        } catch (NumberFormatException ex) {
            return -1;
        }
    }

    private Player requirePlayer(CommandSender sender) {
        if (sender instanceof Player p) {
            return p;
        }
        err(sender, "This command must be run by a player.");
        return null;
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
        String root = cmd.getName().toLowerCase(Locale.ROOT);
        List<String> out = new ArrayList<>();
        if (root.equals("market")) {
            if (args.length == 1) {
                filter(out, List.of("browse", "info", "buy", "sell"), args[0]);
            } else if (args.length == 2 && !args[0].equalsIgnoreCase("browse")) {
                for (Commodity c : plugin.market().commodities()) {
                    if (c.id.startsWith(args[1].toLowerCase(Locale.ROOT))) {
                        out.add(c.id);
                    }
                }
            } else if (args.length == 3 && (args[0].equalsIgnoreCase("buy") || args[0].equalsIgnoreCase("sell"))) {
                filter(out, List.of("1", "8", "16", "32", "64"), args[2]);
            }
        } else if (root.equals("bank")) {
            if (args.length == 1) {
                filter(out, List.of("status", "deposit", "withdraw"), args[0]);
            }
        } else if (root.equals("eco") && args.length == 1 && sender.hasPermission("sovoreconomy.admin")) {
            filter(out, List.of("stats", "give", "set", "event", "reload"), args[0]);
        } else if ((root.equals("pay") || root.equals("money")) && args.length == 0) {
            for (Player p : Bukkit.getOnlinePlayers()) {
                out.add(p.getName());
            }
        }
        return out;
    }

    private void filter(List<String> into, List<String> options, String prefix) {
        String p = prefix.toLowerCase(Locale.ROOT);
        for (String o : options) {
            if (o.startsWith(p)) {
                into.add(o);
            }
        }
    }
}
