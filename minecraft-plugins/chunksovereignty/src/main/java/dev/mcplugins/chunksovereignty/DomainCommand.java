package dev.mcplugins.chunksovereignty;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
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
import java.util.UUID;

public final class DomainCommand implements CommandExecutor, TabCompleter {

    private final SovereigntyPlugin plugin;
    private final java.util.Map<UUID, Long> pendingUnclaimAll = new java.util.HashMap<>();

    public DomainCommand(SovereigntyPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        switch (cmd.getName().toLowerCase(Locale.ROOT)) {
            case "claim" -> claim(sender);
            case "unclaim" -> unclaim(sender);
            case "unclaimall" -> unclaimAll(sender);
            case "confirm" -> confirmUnclaimAll(sender);
            case "domain" -> domain(sender, args);
            case "trust" -> trustToggle(sender, args, true);
            case "untrust" -> trustToggle(sender, args, false);
            case "sovereignty" -> admin(sender, args);
            case "cs" -> cs(sender, args);
        }
        return true;
    }

    private void cs(CommandSender sender, String[] args) {
        if (args.length == 0) {
            showMenu(sender);
            return;
        }
        String sub = args[0].toLowerCase(Locale.ROOT);
        if (sub.equals("confirm")) {
            confirmUnclaimAll(sender);
            return;
        }
        switch (sub) {
            case "claim" -> claim(sender);
            case "unclaim" -> unclaim(sender);
            case "unclaimall" -> unclaimAll(sender);
            case "domain" -> domain(sender, java.util.Arrays.copyOfRange(args, 1, args.length));
            case "trust" -> trustToggle(sender, java.util.Arrays.copyOfRange(args, 1, args.length), true);
            case "untrust" -> trustToggle(sender, java.util.Arrays.copyOfRange(args, 1, args.length), false);
            case "sovereignty" -> admin(sender, java.util.Arrays.copyOfRange(args, 1, args.length));
            case "particles" -> toggleParticles(sender);
            case "help" -> showMenu(sender);
            default -> showMenu(sender);
        }
    }

    private void toggleParticles(CommandSender sender) {
        Settings s = plugin.settings();
        s.showParticles = !s.showParticles;
        ok(sender, "Border particles: " + (s.showParticles ? "ON" : "OFF"));
    }

    private void showMenu(CommandSender sender) {
        Component border = Component.text("  ", NamedTextColor.BLACK);
        info(sender, "  ");
        ok(sender, "    ChunkSovereignty v" + plugin.getDescription().getVersion());
        info(sender, " ");
        info(sender, "  Commands:");
        info(sender, "    /cs claim    - Claim the chunk you stand on");
        info(sender, "    /cs unclaim  - Release your chunk");
        info(sender, "    /cs domain   - Inspect domains");
        info(sender, "    /cs trust <player>   - Trust a player");
        info(sender, "    /cs untrust <player> - Revoke trust");
        info(sender, "    /cs particles - Toggle border particles");
        info(sender, " ");
        info(sender, "  How it works:");
        info(sender, "    - Claim to found a DOMAIN. Each claim costs influence.");
        info(sender, "    - Activity (playtime, block placement) mints influence.");
        info(sender, "    - Influence expands into adjacent chunks automatically.");
        info(sender, "    - Upkeep is charged per chunk/hour; unpaid -> lose chunks.");
        info(sender, "    - Larger domains earn crop-growth bonuses.");
        info(sender, "    - Purple particles show domain borders in-game.");
        info(sender, " ");
        info(sender, "  Admin:");
        ok(sender, "    /sovereignty scan   - Run a domain pass");
        ok(sender, "    /sovereignty reload - Reload config");
        info(sender, " ");
        info(sender, "  Tip: Use /cs domain map for a text map of nearby claims.");
    }

    private void claim(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        Settings s = plugin.settings();
        if (s.disabled(p.getWorld().getName())) {
            err(p, "This world rejects sovereignty.");
            return;
        }
        ChunkIndex.Claim c = at(p);
        ChunkIndex idx = plugin.index();
        UUID existing = idx.ownerAt(c);
        UUID id = p.getUniqueId();
        if (existing != null) {
            err(p, existing.equals(id) ? "You already rule this chunk."
                    : "Claimed by " + nameOf(existing) + ".");
            return;
        }
        int owned = idx.countOwned(id);
        if (owned >= s.maxChunks) {
            err(p, "Your domain is at its limit (" + s.maxChunks + " chunks).");
            return;
        }
        if (owned == 0) {
            idx.putClaim(c, id, System.currentTimeMillis());
            idx.addInfluence(id, s.startInfluence);
            ok(p, "You found a domain! Claimed " + c.x() + "," + c.z()
                    + " with " + String.format("%.0f", s.startInfluence) + " starting influence.");
        } else {
            if (!idx.spendInfluence(id, s.costPerChunk)) {
                err(p, "Expansion costs " + String.format("%.0f", s.costPerChunk)
                        + " influence; you hold " + String.format("%.1f", idx.influence(id)) + ".");
                return;
            }
            idx.putClaim(c, id, System.currentTimeMillis());
            Settings.Tier tier = s.tierFor(idx.countOwned(id));
            ok(p, "Claimed " + c.x() + "," + c.z() + ". Your domain is now a "
                    + tier.name() + " (" + idx.countOwned(id) + " chunks).");
        }
        plugin.markDirty();
    }

    private void unclaim(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        ChunkIndex.Claim c = at(p);
        ChunkIndex idx = plugin.index();
        UUID owner = idx.ownerAt(c);
        if (owner == null || !owner.equals(p.getUniqueId())) {
            err(p, "This is not yours to release.");
            return;
        }
        idx.remove(c);
        plugin.markDirty();
        ok(p, "Released " + c.x() + "," + c.z() + " back to the wilds.");
    }

    private void unclaimAll(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        UUID id = p.getUniqueId();
        long now = System.currentTimeMillis();
        Long previous = pendingUnclaimAll.get(id);
        if (previous != null && now - previous < 60_000) {
            err(p, "You already have a pending unclaimall. Use /cs confirm to finish it.");
            return;
        }
        pendingUnclaimAll.put(id, now);
        ok(p, "§c§lWARNING: §7This will release §eALL §7of your claims.");
        ok(p, "Type §e/cs confirm §7within §e60 seconds §7to confirm.");
        ok(p, "Or wait and the request will expire.");
    }

    private void confirmUnclaimAll(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        UUID id = p.getUniqueId();
        Long requestedAt = pendingUnclaimAll.remove(id);
        if (requestedAt == null || System.currentTimeMillis() - requestedAt > 60_000) {
            err(p, "No pending unclaimall request. Use /cs unclaimall first.");
            return;
        }
        ChunkIndex idx = plugin.index();
        int count = idx.countOwned(id);
        if (count == 0) {
            ok(p, "You have no claims to release.");
            return;
        }
        List<ChunkIndex.Claim> toRemove = new java.util.ArrayList<>(idx.chunksOf(id));
        for (ChunkIndex.Claim c : toRemove) {
            idx.remove(c);
        }
        plugin.markDirty();
        ok(p, "Released " + toRemove.size() + " claims back to the wilds.");
    }

    private void domain(CommandSender sender, String[] args) {
        String sub = args.length == 0 ? "here" : args[0].toLowerCase(Locale.ROOT);
        ChunkIndex idx = plugin.index();
        Settings s = plugin.settings();
        switch (sub) {
            case "here" -> {
                Player p = requirePlayer(sender);
                if (p == null) {
                    return;
                }
                ChunkIndex.Claim c = at(p);
                UUID owner = idx.ownerAt(c);
                if (owner == null) {
                    info(p, "Wilderness. /claim to found or expand a domain.");
                    return;
                }
                Settings.Tier tier = s.tierFor(idx.countOwned(owner));
                info(p, "Domain of " + nameOf(owner) + " - " + tier.name()
                        + " (" + idx.countOwned(owner) + "/" + s.maxChunks + " chunks)");
                if (owner.equals(p.getUniqueId())) {
                    info(p, "Treasury: " + String.format("%.1f", idx.influence(owner))
                            + " influence. Expansion costs "
                            + String.format("%.0f", s.costPerChunk) + "; upkeep "
                            + String.format("%.1f", idx.countOwned(owner) * s.upkeepPerChunkHour)
                            + "/hour.");
                } else if (idx.isTrusted(owner, p.getUniqueId())) {
                    info(p, "You are trusted here.");
                }
            }
            case "map" -> drawMap(sender);
            case "stats" -> stats(sender);
            default -> err(sender, "Usage: /domain [here|map|stats]");
        }
    }

    private void drawMap(CommandSender sender) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        ChunkIndex idx = plugin.index();
        int pcx = p.getLocation().getBlockX() >> 4;
        int pcz = p.getLocation().getBlockZ() >> 4;
        UUID me = p.getUniqueId();
        StringBuilder head = new StringBuilder("   ");
        for (int dx = -4; dx <= 4; dx++) {
            head.append(Math.abs(dx) % 10);
        }
        info(p, head.toString());
        for (int dz = -4; dz <= 4; dz++) {
            StringBuilder row = new StringBuilder(String.format(" %d ", Math.abs(dz) % 10));
            for (int dx = -4; dx <= 4; dx++) {
                UUID owner = idx.ownerAt(new ChunkIndex.Claim(
                        p.getWorld().getName(), pcx + dx, pcz + dz));
                if (dx == 0 && dz == 0) {
                    row.append(owner == null ? '+' : '@');
                } else {
                    row.append(owner == null ? '.' : owner.equals(me) ? '#' : 'o');
                }
            }
            info(p, row.toString());
        }
        info(p, "@ you  # your land  o foreign  . wilds");
    }

    private void stats(CommandSender sender) {
        ChunkIndex idx = plugin.index();
        info(sender, "--- Sovereignty ---");
        info(sender, "Claims total: " + idx.totalClaims()
                + "   Domains tracked: " + idx.influenceSnapshot().size());
        List<Map.Entry<UUID, Integer>> ranked = new ArrayList<>();
        java.util.HashSet<UUID> owners = new java.util.HashSet<>();
        for (var e : idx.allClaims()) {
            owners.add(e.getValue().owner);
        }
        for (UUID o : owners) {
            ranked.add(Map.entry(o, idx.countOwned(o)));
        }
        ranked.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));
        int rank = 1;
        for (var e : ranked.subList(0, Math.min(5, ranked.size()))) {
            Settings.Tier t = plugin.settings().tierFor(e.getValue());
            info(sender, String.format(" %d. %-16s %s (%d chunks)", rank++,
                    nameOf(e.getKey()), t.name(), e.getValue()));
        }
    }

    private void trustToggle(CommandSender sender, String[] args, boolean grant) {
        Player p = requirePlayer(sender);
        if (p == null) {
            return;
        }
        if (args.length < 1) {
            err(p, "Usage: /" + (grant ? "trust" : "untrust") + " <player>");
            return;
        }
        Player target = Bukkit.getPlayerExact(args[0]);
        if (target == null || target.getUniqueId().equals(p.getUniqueId())) {
            err(p, "Target must be another online player.");
            return;
        }
        if (grant) {
            plugin.index().trust(p.getUniqueId(), target.getUniqueId());
            ok(p, target.getName() + " may now build across your domain.");
        } else {
            plugin.index().untrust(p.getUniqueId(), target.getUniqueId());
            ok(p, target.getName() + "'s rights revoked.");
        }
        plugin.markDirty();
    }

    private void admin(CommandSender sender, String[] args) {
        if (!sender.hasPermission("sovereignty.admin")) {
            err(sender, "You need sovereignty.admin.");
            return;
        }
        String sub = args.length == 0 ? "scan" : args[0].toLowerCase(Locale.ROOT);
        if (sub.equals("reload")) {
            plugin.reloadSettings();
            ok(sender, "Sovereignty configuration reloaded.");
        } else {
            List<String> log = plugin.engine().runPass();
            ok(sender, "Sovereignty pass complete (" + log.size() + " events).");
            for (String l : log) {
                info(sender, " " + l);
            }
        }
    }

    private ChunkIndex.Claim at(Player p) {
        return new ChunkIndex.Claim(p.getWorld().getName(),
                p.getLocation().getBlockX() >> 4, p.getLocation().getBlockZ() >> 4);
    }

    private String nameOf(UUID id) {
        String n = Bukkit.getOfflinePlayer(id).getName();
        return n == null ? "Unknown" : n;
    }

    private Player requirePlayer(CommandSender sender) {
        if (sender instanceof Player p) {
            return p;
        }
        err(sender, "Run this as a player.");
        return null;
    }

    private void ok(CommandSender s, String m) {
        s.sendMessage(Component.text(m, NamedTextColor.GREEN));
    }

    private void info(CommandSender s, String m) {
        s.sendMessage(Component.text(m, NamedTextColor.GRAY));
    }

    private void err(CommandSender s, String m) {
        s.sendMessage(Component.text(m, NamedTextColor.RED));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command cmd, String alias, String[] args) {
        if (cmd.getName().equalsIgnoreCase("cs") && args.length == 1) {
            return List.of("claim", "unclaim", "unclaimall", "confirm", "domain", "trust", "untrust",
                    "sovereignty", "particles", "help").stream()
                    .filter(x -> x.startsWith(args[0].toLowerCase(Locale.ROOT))).toList();
        }
        if (cmd.getName().equalsIgnoreCase("cs") && args.length == 2
                && (args[0].equalsIgnoreCase("domain"))) {
            return List.of("here", "map", "stats").stream()
                    .filter(x -> x.startsWith(args[1].toLowerCase(Locale.ROOT))).toList();
        }
        if (cmd.getName().equalsIgnoreCase("domain") && args.length == 1) {
            return List.of("here", "map", "stats").stream()
                    .filter(x -> x.startsWith(args[0].toLowerCase(Locale.ROOT))).toList();
        }
        if ((cmd.getName().equalsIgnoreCase("trust") || cmd.getName().equalsIgnoreCase("untrust"))
                && args.length <= 1) {
            List<String> names = new ArrayList<>();
            for (Player pl : Bukkit.getOnlinePlayers()) {
                if (!pl.getName().toLowerCase(Locale.ROOT)
                        .startsWith(args.length == 0 ? "" : args[0].toLowerCase(Locale.ROOT))) {
                    continue;
                }
                names.add(pl.getName());
            }
            return names;
        }
        if (cmd.getName().equalsIgnoreCase("sovereignty") && args.length <= 1) {
            return List.of("scan", "reload");
        }
        return List.of();
    }
}
