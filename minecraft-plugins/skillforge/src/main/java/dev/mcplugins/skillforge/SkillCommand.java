package dev.mcplugins.skillforge;

import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.Sound;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

public final class SkillCommand implements CommandExecutor, TabCompleter {

    private final SkillForgePlugin plugin;

    public SkillCommand(SkillForgePlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        Settings s = plugin.settings();
        if (!(sender instanceof Player)) {
            sender.sendMessage(s.colored("&7SkillForge commands require a player."));
            return true;
        }

        Player p = (Player) sender;
        UUID uuid = p.getUniqueId();
        SkillEngine engine = plugin.engine();

        if (args.length == 0) {
            showMenu(p, engine, s);
            return true;
        }

        String sub = args[0].toLowerCase(Locale.ROOT);

        switch (sub) {
            case "set" -> {
                if (args.length < 2) {
                    sendHelp(p, "Usage: /skill set <specialization>");
                    return true;
                }
                switchSpec(p, args[1], engine);
            }
            case "xp" -> {
                if (args.length < 2) {
                    showXP(p, null, engine);
                } else {
                    showXP(p, args[1], engine);
                }
            }
            case "unlock" -> showUnlocks(p, engine);
            case "apprentice" -> handleApprentice(p, args, engine);
            case "award" -> handleAward(p, args, engine);
            case "craft" -> handleCraft(p, args, engine);
            case "check" -> handleCheck(p, args, engine);
            case "tree" -> showTree(p, args, engine);
            case "inspect" -> inspectItem(p, engine);
            case "sign" -> signItem(p, args, engine);
            case "tiers" -> handleTiers(p, args, s);
            default -> showMenu(p, engine, s);
        }
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 0) {
            return List.of("set", "xp", "unlock", "apprentice", "award", "craft", "check", "tree", "inspect", "sign", "tiers");
        }
        if (args.length == 1) {
            String sub = args[0].toLowerCase(Locale.ROOT);
            switch (sub) {
                case "set", "xp", "tree" -> {
                    List<String> specs = new ArrayList<>(plugin.settings().specializations.keySet());
                    return completions(specs, args.length > 1 ? args[1] : "");
                }
                case "apprentice" -> {
                    return List.of("add", "remove", "list");
                }
                case "award" -> {
                    return List.of("xp", "craft");
                }
                case "craft" -> {
                    return List.of("sign");
                }
                case "check" -> {
                    return List.of("spec", "tier", "unlock", "apprentice", "craft", "reputation");
                }
                case "tiers" -> {
                    return List.of("list");
                }
                default -> {
                    return List.of();
                }
            }
        }
        return List.of();
    }

    // ── Helpers ────────────────────────────────────────────

    private void sendHelp(Player p, String msg) {
        p.sendMessage(plugin.settings().colored("&c" + msg));
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

    private void showMenu(Player p, SkillEngine engine, Settings s) {
        String spec = engine.activeSpec(uuid(p));
        String specName = spec != null && s.getSpecialization(spec) != null
                ? s.getSpecialization(spec).name : "none selected";
        String tierName = spec != null ? s.getTier(spec, uuid(p), engine).name : "-";
        int xp = spec != null ? engine.xpFor(uuid(p), spec) : 0;
        int toNext = spec != null ? s.xpForNextTier(xp) : 0;

        p.sendMessage(s.colored("&6&l━━ SkillForge ━━"));
        if (spec == null || s.getSpecialization(spec) == null) {
            p.sendMessage(s.colored("&eYou have not chosen a specialization yet."));
            p.sendMessage(s.colored("&7Use &f/skill set <spec> &7to begin."));
        } else {
            p.sendMessage(s.colored("&eActive specialization: &f" + specName));
            p.sendMessage(s.colored("&eTier: &f" + tierName));
            p.sendMessage(s.colored("&eXP: &f" + xp + " (&f" + toNext + "&e to next)"));
        }
        p.sendMessage("");
        p.sendMessage(s.colored("&7/skill set <spec> &8— &7Switch specialization"));
        p.sendMessage(s.colored("&7/skill xp [spec] &8— &7View XP progress"));
        p.sendMessage(s.colored("&7/unlock &8— &7View unlocked skills"));
        p.sendMessage(s.colored("&7/apprentice add|remove|list"));
        p.sendMessage(s.colored("&7/award xp <amount> &8— &7Award XP to yourself"));
        p.sendMessage(s.colored("&7/award craft &8— &7Simulate a craft XP event"));
        p.sendMessage(s.colored("&7/craft sign &8— &7Craft a signature item"));
        p.sendMessage(s.colored("&7/check spec|tier|unlock|apprentice|craft|reputation"));
        p.sendMessage(s.colored("&7/tree [spec] &8— &7View skill tree"));
        p.sendMessage(s.colored("&7/inspect &8— &7Inspect item in hand"));
        p.sendMessage(s.colored("&7/sign [item] &8— &7Sign an item with your mark"));
        p.sendMessage(s.colored("&7/tiers list &8— &7List all tiers"));
        p.sendMessage(s.colored("&6&l━━━━━━━━━━━━━━━━━"));
    }

    private void switchSpec(Player p, String specId, SkillEngine engine) {
        Settings s = plugin.settings();
        Specialization sp = s.getSpecialization(specId);
        if (sp == null) {
            sendHelp(p, "Unknown specialization. Available: " + s.specializations.keySet());
            return;
        }
        engine.setActiveSpec(uuid(p), specId);
        p.sendMessage(s.colored("&aSwitched to &f" + sp.name + "&a."));
    }

    private void showXP(Player p, String specArg, SkillEngine engine) {
        Settings s = plugin.settings();
        String spec = specArg;
        if (spec == null || s.getSpecialization(spec) == null) {
            spec = engine.activeSpec(uuid(p));
        }
        if (spec == null || s.getSpecialization(spec) == null) {
            sendHelp(p, "No specialization selected or specified. Use /skill set <spec> first.");
            return;
        }

        int xp = engine.xpFor(uuid(p), spec);
        Tier tier = s.getTier(spec, uuid(p), engine);
        int nextXP = s.xpForNextTier(xp);
        Tier nextTier = s.getTier(xp + nextXP >= s.tiers.get(s.tiers.size() - 1).xp ? Integer.MAX_VALUE : xp + nextXP);

        p.sendMessage(s.colored("&e&l━━ " + s.getSpecialization(spec).name + " ━━"));
        p.sendMessage(s.colored("&fCurrent tier: &f" + tier.name + " &8(" + tier.xp + " XP)"));
        p.sendMessage(s.colored("&fXP in tier: &f" + (xp - tier.xp) + "/" + (nextTier.xp - tier.xp)));
        p.sendMessage(s.colored("&fXP to next tier: &f" + (nextTier.xp - xp)));
        p.sendMessage(s.colored("&fTotal crafts: &f" + engine.totalCraftsFor(uuid(p))));
        p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━"));

        if (nextTier != null && !nextTier.id.equals(tier.id)) {
            p.sendMessage(s.colored("&7Next tier: &f" + nextTier.name + " &8(" + nextTier.xp + " XP)"));
        }
    }

    private void showUnlocks(Player p, SkillEngine engine) {
        Settings s = plugin.settings();
        String spec = engine.activeSpec(uuid(p));
        if (spec == null || s.getSpecialization(spec) == null) {
            sendHelp(p, "No specialization selected. Use /skill set <spec> first.");
            return;
        }

        p.sendMessage(s.colored("&e&l━━ " + s.getSpecialization(spec).name + " — Unlocked Skills ━━"));
        Set<String> unlocked = engine.unlockedSkills(uuid(p), spec);
        if (unlocked.isEmpty()) {
            p.sendMessage(s.colored("&7No skills unlocked yet."));
        } else {
            for (String skill : unlocked) {
                SkillDefinition sd = findSkill(spec, skill, s);
                if (sd != null) {
                    p.sendMessage(s.colored("&f✓ &f" + sd.name + " — " + sd.description));
                }
            }
        }
        p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━━━━━━━"));
    }

    private void handleApprentice(Player p, String[] args, SkillEngine engine) {
        UUID me = uuid(p);
        if (args.length < 2) {
            sendHelp(p, "Usage: /apprentice add <player> | remove <player> | list");
            return;
        }

        String action = args[1].toLowerCase(Locale.ROOT);

        switch (action) {
            case "add" -> {
                if (args.length < 3) {
                    sendHelp(p, "Usage: /apprentice add <player>");
                    return;
                }
                Player target = Bukkit.getPlayer(args[2]);
                if (target == null) {
                    sendHelp(p, "Player not found online.");
                    return;
                }
                if (!engine.canAcceptApprentice(me)) {
                    p.sendMessage(plugin.settings().colored("&cYou cannot accept more apprentices."));
                    return;
                }
                if (engine.isApprenticeOf(target.getUniqueId(), me)) {
                    p.sendMessage(plugin.settings().colored("&7That player is already your apprentice."));
                    return;
                }
                Settings s = plugin.settings();
                if (s.vaultEnabled && engine.getVaultBalance(target.getUniqueId()) < s.apprentishipFee) {
                    p.sendMessage(s.colored("&cYou need &f" + s.apprentishipFee + " " + s.currencySymbol + "&c to register an apprentice."));
                    return;
                }
                engine.apprentice(me, target.getUniqueId());
                if (s.vaultEnabled) {
                    engine.deductVaultBalance(target.getUniqueId(), s.apprentishipFee);
                }
                p.sendMessage(s.colored("&a" + target.getName() + " &ais now your apprentice&a."));
                target.sendMessage(s.colored("&aYou are now an apprentice of &f" + p.getName() + "&a."));
            }
            case "remove" -> {
                if (args.length < 3) {
                    sendHelp(p, "Usage: /apprentice remove <player>");
                    return;
                }
                Player target = Bukkit.getPlayer(args[2]);
                if (target == null) {
                    sendHelp(p, "Player not found online.");
                    return;
                }
                if (!engine.isApprenticeOf(target.getUniqueId(), me)) {
                    p.sendMessage(plugin.settings().colored("&7That player is not your apprentice."));
                    return;
                }
                engine.unapprentice(me, target.getUniqueId());
                p.sendMessage(plugin.settings().colored("&a" + target.getName() + " &aremoved as your apprentice&a."));
            }
            case "list" -> {
                Set<UUID> apprs = engine.apprenticesOf(me);
                if (apprs.isEmpty()) {
                    p.sendMessage(plugin.settings().colored("&7You have no apprentices."));
                } else {
                    p.sendMessage(plugin.settings().colored("&e&l━━ Your Apprentices ━━"));
                    for (UUID u : apprs) {
                        p.sendMessage(plugin.settings().colored("&f• &f" + Bukkit.getOfflinePlayer(u).getName()));
                    }
                    p.sendMessage(plugin.settings().colored("&e&l━━━━━━━━━━━━━━━━━"));
                }
            }
            default -> sendHelp(p, "Usage: /apprentice add|remove|list");
        }
    }

    private void handleAward(Player p, String[] args, SkillEngine engine) {
        UUID me = uuid(p);
        if (args.length < 2) {
            sendHelp(p, "Usage: /award xp <amount> | /award craft");
            return;
        }

        String action = args[1].toLowerCase(Locale.ROOT);

        switch (action) {
            case "xp" -> {
                if (args.length < 3) {
                    sendHelp(p, "Usage: /award xp <amount>");
                    return;
                }
                try {
                    int amount = Integer.parseInt(args[2]);
                    if (amount <= 0) {
                        sendHelp(p, "Amount must be positive.");
                        return;
                    }
                    engine.addXP(me, amount);
                    String spec = engine.activeSpec(me);
                    p.sendMessage(plugin.settings().colored("&aAwarded &f" + amount + " XP&a. New total: &f" + engine.xpFor(me, spec) + "&a."));
                } catch (NumberFormatException e) {
                    sendHelp(p, "Invalid amount.");
                }
            }
            case "craft" -> {
                String spec = engine.activeSpec(me);
                if (spec == null) {
                    sendHelp(p, "No specialization selected.");
                    return;
                }
                ItemStack crafted = p.getInventory().getItemInMainHand();
                int xp = engine.awardCraftXP(me, spec, crafted);
                p.sendMessage(plugin.settings().colored("&aCraft XP awarded: &f" + xp + "&a. New total: &f" + engine.xpFor(me, spec) + "&a."));
            }
            default -> sendHelp(p, "Usage: /award xp <amount> | /award craft");
        }
    }

    private void handleCraft(Player p, String[] args, SkillEngine engine) {
        if (args.length < 2 || !args[1].equalsIgnoreCase("sign")) {
            showCraftInfo(p, engine);
            return;
        }
        signItem(p, args, engine);
    }

    private void showCraftInfo(Player p, SkillEngine engine) {
        UUID me = uuid(p);
        Settings s = plugin.settings();
        String spec = engine.activeSpec(me);

        p.sendMessage(s.colored("&e&l━━ Signature Crafting ━━"));
        if (spec == null) {
            p.sendMessage(s.colored("&cNo specialization selected. Use /skill set <spec> first."));
            p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━━━"));
            return;
        }

        int xp = engine.xpFor(me, spec);
        Tier tier = s.getTier(spec, me, engine);
        double cost = s.craftingBaseCost * (1 + (tier.id.equals("grandmaster") || tier.id.equals("legend")
                ? s.grandmasterCraftPremium : 0));

        p.sendMessage(s.colored("&fSpecialization: &f" + s.getSpecialization(spec).name));
        p.sendMessage(s.colored("&fTier: &f" + tier.name));
        p.sendMessage(s.colored("&fCraft cost: &f" + cost + " " + s.currencySymbol));
        p.sendMessage(s.colored("&fTotal crafts: &f" + engine.totalCraftsFor(me)));
        p.sendMessage(s.colored("&fReputation: &f" + engine.reputationFor(me)));

        if (tier.id.equals("journeyman")) {
            p.sendMessage(s.colored("&cYou must reach at least Artisan to craft signature items."));
        } else {
            boolean hasBalance = s.vaultEnabled ? engine.getVaultBalance(me) >= cost : engine.getNativeBalance(me) >= cost;
            if (hasBalance) {
                p.sendMessage(s.colored("&aYou can craft signature items right now."));
            } else {
                p.sendMessage(s.colored("&cYou lack the funds. Need &f" + cost + " " + s.currencySymbol));
            }
        }
        p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━━━━━━━"));
    }

    private void handleCheck(Player p, String[] args, SkillEngine engine) {
        if (args.length < 2) {
            sendHelp(p, "Usage: /check spec|tier|unlock|apprentice|craft|reputation");
            return;
        }
        String check = args[1].toLowerCase(Locale.ROOT);

        switch (check) {
            case "spec" -> {
                String spec = engine.activeSpec(uuid(p));
                p.sendMessage(plugin.settings().colored("&fActive spec: &f" + (spec != null ? plugin.settings().getSpecialization(spec).name : "none")));
            }
            case "tier" -> {
                String spec = engine.activeSpec(uuid(p));
                if (spec == null) {
                    p.sendMessage(plugin.settings().colored("&cNo spec selected."));
                    return;
                }
                p.sendMessage(plugin.settings().colored("&fTier: &f" + plugin.settings().getTier(spec, uuid(p), engine).name));
            }
            case "unlock" -> {
                String spec = engine.activeSpec(uuid(p));
                if (spec == null) {
                    p.sendMessage(plugin.settings().colored("&cNo spec selected."));
                    return;
                }
                Set<String> unlocked = engine.unlockedSkills(uuid(p), spec);
                p.sendMessage(plugin.settings().colored("&fUnlocked: &f" + unlocked.size() + " skills"));
            }
            case "apprentice" -> {
                int count = engine.getApprenticeCount(uuid(p));
                p.sendMessage(plugin.settings().colored("&fApprentices: &f" + count));
            }
            case "craft" -> {
                int count = engine.totalCraftsFor(uuid(p));
                p.sendMessage(plugin.settings().colored("&fTotal crafts: &f" + count));
            }
            case "reputation" -> {
                int rep = engine.reputationFor(uuid(p));
                p.sendMessage(plugin.settings().colored("&fReputation: &f" + rep));
            }
            default -> sendHelp(p, "Usage: /check spec|tier|unlock|apprentice|craft|reputation");
        }
    }

    private void showTree(Player p, String[] args, SkillEngine engine) {
        Settings s = plugin.settings();
        String specArg = args.length > 1 ? args[1] : engine.activeSpec(uuid(p));
        if (specArg == null || s.getSpecialization(specArg) == null) {
            sendHelp(p, "No specialization selected or specified. Use /skill set <spec> first.");
            return;
        }

        Specialization sp = s.getSpecialization(specArg);
        String spec = specArg.toLowerCase(Locale.ROOT);
        int xp = engine.xpFor(uuid(p), spec);
        Tier currentTier = s.getTier(spec, uuid(p), engine);

        p.sendMessage(s.colored("&e&l━━ " + sp.name + " — Skill Tree ━━"));
        p.sendMessage(s.colored("&fCurrent tier: &f" + currentTier.name));

        for (Tier tier : s.tiers) {
            String tierId = tier.id.toLowerCase(Locale.ROOT);
            Map<String, List<SkillDefinition>> byTier = s.skills.get(spec);
            if (byTier == null || !byTier.containsKey(tierId)) continue;
            List<SkillDefinition> skills = byTier.get(tierId);
            boolean unlocked = tier.id.equals(currentTier.id) ||
                    currentTier.id.equals("master") ||
                    currentTier.id.equals("grandmaster") ||
                    currentTier.id.equals("legend");
            boolean isCurrent = tier.id.equals(currentTier.id);

            String prefix = isCurrent ? s.colored("&f[" + tier.shortName + "] ") : s.colored("&8  " + tier.shortName + "  ");
            p.sendMessage(prefix + s.colored("&f" + tier.name + " (XP: " + tier.xp + ")"));
            for (SkillDefinition sd : skills) {
                boolean hasSkill = engine.hasSkill(uuid(p), specArg, sd.id);
                String symbol = hasSkill ? s.colored("&a✓") : (unlocked ? s.colored("&7○") : s.colored("&c■"));
                p.sendMessage("   " + symbol + " " + s.colored("&f" + sd.name + " — " + sd.description));
            }
            p.sendMessage("");
        }
        p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━━━━━━━━━━━━━"));
    }

    private void inspectItem(Player p, SkillEngine engine) {
        ItemStack item = p.getInventory().getItemInMainHand();
        if (item == null || item.getType().isAir()) {
            p.sendMessage(plugin.settings().colored("&cNothing in hand to inspect."));
            return;
        }
        if (!engine.isSignature(item)) {
            p.sendMessage(plugin.settings().colored("&cThis is not a signature item."));
            return;
        }
        SignatureInfo info = engine.signatureInfo(item);
        if (info == null) return;
        Specialization specDef = plugin.settings().getSpecialization(info.spec);
        String specName = specDef != null ? specDef.name : info.spec;

        p.sendMessage(plugin.settings().colored("&e&l━━ Signature Item ━━"));
        p.sendMessage(plugin.settings().colored("&fForged by: &f" + (info.forgeName != null ? info.forgeName : "Unknown")));
        p.sendMessage(plugin.settings().colored("&fSpecialization: &f" + specName));
        p.sendMessage(plugin.settings().colored("&fTier: &f" + info.tier));
        p.sendMessage(plugin.settings().colored("&fCrafts: &f#" + info.count));
        p.sendMessage(plugin.settings().colored("&fForge XP: &f" + info.xp));
        p.sendMessage(plugin.settings().colored("&e&l━━━━━━━━━━━━━━━━━━━━━"));
    }

    private void signItem(Player p, String[] args, SkillEngine engine) {
        ItemStack item = p.getInventory().getItemInMainHand();
        if (item == null || item.getType().isAir()) {
            sendHelp(p, "Nothing in hand to sign.");
            return;
        }
        if (engine.isSignature(item)) {
            sendHelp(p, "This item is already signed.");
            return;
        }
        Settings s = plugin.settings();
        String spec = engine.activeSpec(uuid(p));
        if (spec == null) {
            sendHelp(p, "No specialization selected. Use /skill set <spec> first.");
            return;
        }
        Tier tier = s.getTier(spec, uuid(p), engine);
        if (tier.id.equals("journeyman")) {
            sendHelp(p, "You must reach at least Artisan to sign items.");
            return;
        }
        double cost = s.craftingBaseCost * (1 + (tier.id.equals("grandmaster") || tier.id.equals("legend")
                ? s.grandmasterCraftPremium : 0));
        if (s.vaultEnabled && engine.getVaultBalance(uuid(p)) < cost) {
            sendHelp(p, "Insufficient funds. Need " + cost + " " + s.currencySymbol);
            return;
        }
        if (!s.vaultEnabled && engine.getNativeBalance(uuid(p)) < cost) {
            sendHelp(p, "Insufficient funds. Need " + cost + " " + s.currencySymbol);
            return;
        }
        ItemStack signed = engine.signatureItem(uuid(p), spec, item);
        if (signed == null) {
            sendHelp(p, "Failed to sign item. Not enough funds.");
            return;
        }
        p.getInventory().setItemInMainHand(signed);
        p.sendMessage(plugin.settings().colored("&a§l✦ §fYour item has been signed! §a§l✦"));
        p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.5f, 1.0f);
    }

    private void handleTiers(Player p, String[] args, Settings s) {
        if (args.length < 2) {
            sendHelp(p, "Usage: /skill tiers <specialization>");
            return;
        }
        String specArg = args[1];
        Specialization sp = s.getSpecialization(specArg);
        if (sp == null) {
            sendHelp(p, "Unknown specialization. Available: " + s.specializations.keySet());
            return;
        }

        String spec = sp.id;
        int xp = plugin.engine().xpFor(uuid(p), spec);
        Tier currentTier = s.getTier(spec, uuid(p), plugin.engine());

        p.sendMessage(s.colored("&e&l━━ " + sp.name + " — Tiers ━━"));
        p.sendMessage(s.colored("&fCurrent tier: &f" + currentTier.name + " &8(" + currentTier.xp + " XP)"));

        for (Tier tier : s.tiers()) {
            String tierId = tier.id.toLowerCase(Locale.ROOT);
            boolean isCurrent = tier.id.equals(currentTier.id);
            boolean unlocked = tier.xp <= xp;
            String prefix = isCurrent ? s.colored("&f[" + tier.shortName + "] ") : s.colored("&8  " + tier.shortName + "  ");
            String status = isCurrent ? s.colored("&aCURRENT") : (unlocked ? s.colored("&7UNLOCKED") : s.colored("&cLOCKED"));
            p.sendMessage(prefix + s.colored("&f" + tier.name + " &8(" + tier.xp + " XP) &8- " + status));
        }
        p.sendMessage(s.colored("&e&l━━━━━━━━━━━━━━━━━━━━━"));
    }

    private UUID uuid(Player p) {
        return p.getUniqueId();
    }

    private SkillDefinition findSkill(String specId, String skillId, Settings s) {
        String specLower = specId.toLowerCase(Locale.ROOT);
        String skillLower = skillId.toLowerCase(Locale.ROOT);
        Map<String, List<SkillDefinition>> byTier = s.skills.get(specLower);
        if (byTier == null) return null;
        for (List<SkillDefinition> list : byTier.values()) {
            for (SkillDefinition sd : list) {
                if (sd.id.equals(skillLower)) return sd;
            }
        }
        return null;
    }
}
