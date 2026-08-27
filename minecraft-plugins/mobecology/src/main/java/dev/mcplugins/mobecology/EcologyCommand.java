package dev.mcplugins.mobecology;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class EcologyCommand implements CommandExecutor, TabCompleter {

    private static final List<String> SUBS = List.of("status", "scan", "top", "reset", "reload");

    private final MobEcologyPlugin plugin;

    EcologyCommand(MobEcologyPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        String name = command.getName().toLowerCase(Locale.ROOT);
        if (name.equals("me") && args.length == 0) {
            showMenu(sender);
            return true;
        }
        String sub = args.length == 0 ? "status" : args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "status" -> status(sender);
            case "scan" -> scan(sender);
            case "top" -> top(sender, args);
            case "reset" -> reset(sender);
            case "reload" -> reload(sender);
            default -> sender.sendMessage(Component.text("Usage: /ecology [status|scan|top|reset|reload]",
                    NamedTextColor.GRAY));
        }
        return true;
    }

    private void showMenu(CommandSender sender) {
        Component title = Component.text("MobEcology", NamedTextColor.DARK_GREEN)
                .decorate(TextDecoration.BOLD);
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
        sender.sendMessage(title);
        sender.sendMessage(Component.text("Ecosystem balance tracking and mob population management", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
        sender.sendMessage(Component.text("Commands:", NamedTextColor.YELLOW));
        sender.sendMessage(Component.text("/me status — View ecosystem status for your region", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/me scan — Force a region rescan", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/me top [n] — List most imbalanced regions", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/me reset — Clear current region's population data (admin)", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("/me reload — Reload MobEcology config (admin)", NamedTextColor.AQUA));
        sender.sendMessage(Component.text("How-tos:", NamedTextColor.YELLOW));
        sender.sendMessage(Component.text("\u2022 Each region is a 16x16 chunk grid", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("\u2022 Overcrowded mobs (RED) will starve", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("\u2022 Strained ecosystems (YELLOW) adapt over time", NamedTextColor.GRAY));
        sender.sendMessage(Component.text("- - - - - - - - - - - - - - - -", NamedTextColor.DARK_GRAY));
    }

    private void status(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        RegionKey key = keyOf(p);
        EcologyRegion r = tracker().peek(key);
        long staleMs = plugin.settings().censusIntervalSeconds * 1000L;
        if (r == null || System.currentTimeMillis() - r.lastCensus > staleMs) {
            r = tracker().region(key);
            tracker().census(key);
        }
        sendStatus(sender, key, r, false);
    }

    private void scan(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        RegionKey key = keyOf(p);
        tracker().region(key);
        tracker().census(key);
        sender.sendMessage(Component.text("Region re-scanned.", NamedTextColor.GREEN));
        sendStatus(sender, key, tracker().peek(key), false);
    }

    private void top(CommandSender sender, String[] args) {
        int n = 10;
        if (args.length >= 2) {
            try {
                n = Math.max(1, Math.min(25, Integer.parseInt(args[1])));
            } catch (NumberFormatException ignored) {
            }
        }
        record Row(RegionKey key, double score, boolean scanned) {}
        List<Row> rows = new ArrayList<>();
        for (Map.Entry<RegionKey, EcologyRegion> e : tracker().regions().entrySet()) {
            rows.add(new Row(e.getKey(), engine().imbalanceScore(e.getValue()), e.getValue().lastCensus > 0));
        }
        rows.sort(Comparator.comparingDouble(Row::score).reversed());
        sender.sendMessage(Component.text("--- Most imbalanced regions ---", NamedTextColor.GOLD));
        int shown = 0;
        for (Row row : rows) {
            if (shown >= n) {
                break;
            }
            if (!row.scanned()) {
                continue;
            }
            shown++;
            NamedTextColor color = row.score() < 0.15 ? NamedTextColor.GREEN
                    : row.score() < 0.4 ? NamedTextColor.YELLOW : NamedTextColor.RED;
            sender.sendMessage(Component.text(String.format("%s (%d,%d)", row.key().world(),
                            row.key().rx(), row.key().rz()), NamedTextColor.WHITE)
                    .append(Component.text(" - " + Math.round(row.score() * 100) + "% off-balance", color)));
        }
        if (shown == 0) {
            sender.sendMessage(Component.text("No censused regions yet.", NamedTextColor.GRAY));
        }
    }

    private void reset(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        if (!sender.hasPermission("mobecology.admin")) {
            sender.sendMessage(Component.text("You need mobecology.admin.", NamedTextColor.RED));
            return;
        }
        EcologyRegion r = tracker().peek(keyOf(p));
        if (r == null) {
            sender.sendMessage(Component.text("Nothing tracked here yet.", NamedTextColor.GRAY));
            return;
        }
        r.pop.clear();
        r.pressure.clear();
        r.lastSeen.clear();
        r.lastCensus = 0;
        sender.sendMessage(Component.text("Region state cleared; next census rebuilds it.", NamedTextColor.GREEN));
    }

    private void reload(CommandSender sender) {
        if (!sender.hasPermission("mobecology.admin")) {
            sender.sendMessage(Component.text("You need mobecology.admin.", NamedTextColor.RED));
            return;
        }
        plugin.reloadSettings();
        sender.sendMessage(Component.text("MobEcology configuration reloaded.", NamedTextColor.GREEN));
    }

    private void sendStatus(CommandSender sender, RegionKey key, EcologyRegion r, boolean verbose) {
        sender.sendMessage(Component.text("--- Ecosystem: " + key.world() + " (" + key.rx()
                + "," + key.rz() + ") ---", NamedTextColor.GOLD));
        for (MobEcologyPlugin.Category cat : new MobEcologyPlugin.Category[]{
                MobEcologyPlugin.Category.PASSIVE, MobEcologyPlugin.Category.HOSTILE,
                MobEcologyPlugin.Category.WATER, MobEcologyPlugin.Category.AMBIENT}) {
            double cap = plugin.settings().capacity(cat);
            double total = r.total(plugin.speciesCategories(), cat);
            double ratio = cap <= 0 ? 0 : total / cap;
            NamedTextColor color = ratio > 1.2 ? NamedTextColor.RED
                    : ratio < 0.3 ? NamedTextColor.YELLOW : NamedTextColor.GREEN;
            sender.sendMessage(Component.text(String.format("%-8s", cat.label()), NamedTextColor.WHITE)
                    .append(Component.text(bar(ratio), color))
                    .append(Component.text(String.format(" %.0f / %.0f", total, cap), NamedTextColor.GRAY)));
        }
        java.util.List<Map.Entry<String, Double>> overridden = new ArrayList<>();
        for (Map.Entry<String, Double> e : r.pop.entrySet()) {
            if (plugin.settings().capacityOverrides.containsKey(e.getKey().toLowerCase(Locale.ROOT))) {
                overridden.add(e);
            }
        }
        if (!overridden.isEmpty()) {
            overridden.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
            sender.sendMessage(Component.text("Species overrides:", NamedTextColor.GRAY));
            int shown = 0;
            for (Map.Entry<String, Double> e : overridden) {
                if (shown++ == 5) {
                    break;
                }
                String idLow = e.getKey().toLowerCase(Locale.ROOT);
                String catName = plugin.speciesCategories().getOrDefault(e.getKey(), "IGNORED");
                double effCap;
                try {
                    effCap = engine().effectiveCapacity(idLow,
                            MobEcologyPlugin.Category.valueOf(catName));
                } catch (IllegalArgumentException ex) {
                    continue;
                }
                double ratio = effCap <= 0 ? 0 : e.getValue() / effCap;
                NamedTextColor color = ratio > 1.0 ? NamedTextColor.RED : NamedTextColor.AQUA;
                sender.sendMessage(Component.text(String.format("  %-14s", e.getKey()), NamedTextColor.WHITE)
                        .append(Component.text(bar(ratio / 1.25), color))
                        .append(Component.text(String.format(" %.0f / %.0f", e.getValue(), effCap),
                                NamedTextColor.GRAY)));
            }
        }
        List<Map.Entry<String, Double>> adapted = new ArrayList<>();
        for (Map.Entry<String, Double> e : r.pressure.entrySet()) {
            if (adaptation().tierFor(e.getKey(), r) > 0) {
                adapted.add(e);
            }
        }
        if (adapted.isEmpty()) {
            sender.sendMessage(Component.text("Adaptations: none under pressure", NamedTextColor.GRAY));
        } else {
            adapted.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
            StringBuilder sb = new StringBuilder();
            int count = 0;
            for (Map.Entry<String, Double> e : adapted) {
                if (count++ == 3) {
                    break;
                }
                int tier = adaptation().tierFor(e.getKey(), r);
                if (count > 1) {
                    sb.append(", ");
                }
                sb.append(e.getKey()).append(" T").append(tier).append("*".repeat(tier));
            }
            sender.sendMessage(Component.text("Adaptations: ", NamedTextColor.GRAY)
                    .append(Component.text(sb.toString(), NamedTextColor.LIGHT_PURPLE)));
        }
        double score = engine().imbalanceScore(r);
        String verdict = score < 0.15 ? "BALANCED" : score < 0.4 ? "STRAINED" : "COLLAPSING";
        NamedTextColor color = score < 0.15 ? NamedTextColor.GREEN : score < 0.4 ? NamedTextColor.YELLOW : NamedTextColor.RED;
        sender.sendMessage(Component.text("Verdict: ", NamedTextColor.GRAY)
                .append(Component.text(verdict + String.format(" (%.0f%%)", score * 100), color)));
    }

    private String bar(double ratio) {
        double clamped = Math.max(0, Math.min(1.25, ratio)) / 1.25;
        int filled = (int) Math.round(clamped * 10);
        return "[" + "\u2588".repeat(filled) + "\u2591".repeat(10 - filled) + "]";
    }

    private PopulationTracker tracker() {
        return plugin.tracker();
    }

    private BalanceEngine engine() {
        return plugin.engine();
    }

    private AdaptationManager adaptation() {
        return plugin.adaptation();
    }

    private RegionKey keyOf(Player p) {
        return RegionKey.of(p.getWorld(), p.getLocation().getBlockX() >> 4,
                p.getLocation().getBlockZ() >> 4, plugin.settings().regionChunks);
    }

    private Player requirePlayer(CommandSender sender) {
        if (sender instanceof Player p) {
            return p;
        }
        sender.sendMessage(Component.text("This subcommand must be run by a player (uses your region).",
                NamedTextColor.RED));
        return null;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            String prefix = args[0].toLowerCase(Locale.ROOT);
            List<String> out = new ArrayList<>();
            for (String s : SUBS) {
                if (s.startsWith(prefix)) {
                    out.add(s);
                }
            }
            return out;
        }
        if (args.length == 2 && args[0].equalsIgnoreCase("top")) {
            return List.of("5", "10", "25");
        }
        return List.of();
    }
}
