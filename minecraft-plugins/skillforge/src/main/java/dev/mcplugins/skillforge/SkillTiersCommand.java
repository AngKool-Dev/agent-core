package dev.mcplugins.skillforge;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

public final class SkillTiersCommand implements CommandExecutor, TabCompleter {

    private final SkillForgePlugin plugin;

    public SkillTiersCommand(SkillForgePlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        Settings s = plugin.settings();

        if (!(sender instanceof Player)) {
            sender.sendMessage(s.colored("&cThis command requires a player."));
            return true;
        }

        Player p = (Player) sender;

        if (args.length == 0) {
            showTiers(p, s);
            return true;
        }

        String sub = args[0].toLowerCase(Locale.ROOT);

        switch (sub) {
            case "list" -> showTiers(p, s);
            case "xp" -> showTierXP(p, s);
            default -> sendHelp(p, s);
        }

        return true;
    }

    private void showTiers(Player p, Settings s) {
        p.sendMessage(s.colored("&e&l━━ Tiers ━━"));
        for (Tier tier : s.tiers()) {
            String prefix = tier.id.equals("legend") || tier.id.equals("grandmaster")
                    ? s.colored("&f[" + tier.shortName + "] ")
                    : s.colored("&8  " + tier.shortName + "  ");
            p.sendMessage(prefix + s.colored("&f" + tier.name + " &8(" + tier.xp + " XP)"));
        }
        p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━━━━━"));
    }

    private void showTierXP(Player p, Settings s) {
        Settings settings = plugin.settings();
        String spec = plugin.engine().activeSpec(p.getUniqueId());
        if (spec == null || settings.getSpecialization(spec) == null) {
            p.sendMessage(settings.colored("&cNo specialization selected. Use /skill set <spec> first."));
            return;
        }

        int xp = plugin.engine().xpFor(p.getUniqueId(), spec);
        Tier current = settings.getTier(spec, p.getUniqueId(), plugin.engine());

        p.sendMessage(settings.colored("&e&l━━ Tier Progress ━━"));
        p.sendMessage(settings.colored("&fCurrent tier: &f" + current.name + " &8(" + current.xp + " XP)"));
        p.sendMessage(settings.colored("&fXP in tier: &f" + (xp - current.xp) + "/" + (nextTierXp(xp, settings) - current.xp)));
        p.sendMessage(settings.colored("&fXP to next tier: &f" + (nextTierXp(xp, settings) - xp)));
        p.sendMessage(settings.colored("&e&l━━━━━━━━━━━━━━━━━━━━━"));
    }

    private int nextTierXp(int xp, Settings s) {
        Tier current = s.getTier(xp);
        int idx = s.tiers().indexOf(current);
        if (idx + 1 < s.tiers().size()) {
            return s.tiers().get(idx + 1).xp;
        }
        return current.xp;
    }

    private void sendHelp(Player p, Settings s) {
        p.sendMessage(s.colored("&cUsage: /skill tiers [list|xp]"));
        p.sendMessage(s.colored("&7/tiers list &8— &7List all tiers"));
        p.sendMessage(s.colored("&7/tiers xp &8— &7Show XP to next tier"));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 0) {
            return List.of("list", "xp");
        }
        if (args.length == 1) {
            return completions(List.of("list", "xp"), args[0]);
        }
        return Collections.emptyList();
    }

    private List<String> completions(List<String> choices, String prefix) {
        String lower = prefix.toLowerCase(Locale.ROOT);
        List<String> result = new ArrayList<>();
        for (String c : choices) {
            if (c.toLowerCase(Locale.ROOT).startsWith(lower)) {
                result.add(c);
            }
        }
        return result;
    }
}