package dev.mcplugins.skillforge;

import org.bukkit.ChatColor;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.Plugin;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class Settings {

    final Map<String, Specialization> specializations = new HashMap<>();
    final List<Tier> tiers = new ArrayList<>();
    final Map<String, Map<String, List<SkillDefinition>>> skills = new HashMap<>();

    int autosaveSeconds = 300;
    boolean vaultEnabled = true;
    boolean bossbarEnabled = true;
    String currencySymbol = "S";
    double apprentishipFee = 250.0;
    double masterPercentCut = 0.10;
    double echoAttuneXPBonus = 0.15;
    double ecologyRareDropXP = 0.25;
    double claimWorkshopBonus = 0.20;
    double craftingBaseCost = 50.0;
    double grandmasterCraftPremium = 0.50;

    void load(Plugin plugin) {
        FileConfiguration c = plugin.getConfig();
        currencySymbol = c.getString("currency.symbol", "S");
        autosaveSeconds = Math.max(30, c.getInt("storage.autosave-seconds", 300));
        vaultEnabled = c.getBoolean("vault.enabled", true);
        bossbarEnabled = c.getBoolean("bossbar.enabled", true);
        apprentishipFee = Math.max(0, c.getDouble("economy.apprentiship-fee", 250.0));
        masterPercentCut = Math.min(0.5, Math.max(0, c.getDouble("economy.master-cut", 0.10)));
        echoAttuneXPBonus = Math.min(1.0, Math.max(0, c.getDouble("bonuses.echo-attune-xp", 0.15)));
        ecologyRareDropXP = Math.min(1.0, Math.max(0, c.getDouble("bonuses.ecology-rare-drop-xp", 0.25)));
        claimWorkshopBonus = Math.min(1.0, Math.max(0, c.getDouble("bonuses.claim-workshop-bonus", 0.20)));
        craftingBaseCost = Math.max(0, c.getDouble("economy.crafting-base-cost", 50.0));
        grandmasterCraftPremium = Math.min(1.0, Math.max(0, c.getDouble("economy.grandmaster-premium", 0.50)));

        specializations.clear();
        var sec = c.getConfigurationSection("specializations");
        if (sec != null) {
            for (String key : sec.getKeys(false)) {
                var s = sec.getConfigurationSection(key);
                if (s == null) continue;
                String id = key.toLowerCase();
                String name = s.getString("name", capitalize(key));
                String desc = s.getString("description", "");
                String color = s.getString("color", "&6");
                int maxAppr = s.getInt("max-apprentices", 3);
                List<String> starter = s.getStringList("starter-skills");
                specializations.put(id, new Specialization(id, name, desc, color, maxAppr, starter));
            }
        }

        tiers.clear();
        var ts = c.getConfigurationSection("tiers");
        if (ts != null) {
            for (String key : ts.getKeys(false)) {
                var t = ts.getConfigurationSection(key);
                if (t == null) continue;
                String id = key.toLowerCase();
                String name = t.getString("name", capitalize(key));
                String shortName = t.getString("short", name.substring(0, 1));
                int xp = t.getInt("xp", 0);
                tiers.add(new Tier(id, name, shortName, xp));
            }
            tiers.sort(Comparator.comparingInt(t -> t.xp));
        }

        skills.clear();
        var sk = c.getConfigurationSection("skills");
        if (sk != null) {
            for (String specKey : sk.getKeys(false)) {
                var specSec = sk.getConfigurationSection(specKey);
                if (specSec == null) continue;
                String specId = specKey.toLowerCase();
                Map<String, List<SkillDefinition>> byTier = new HashMap<>();
                skills.put(specId, byTier);
                for (String tierKey : specSec.getKeys(false)) {
                    var tierSec = specSec.getConfigurationSection(tierKey);
                    if (tierSec == null) continue;
                    List<SkillDefinition> list = new ArrayList<>();
                    for (String skillKey : tierSec.getKeys(false)) {
                        var s = tierSec.getConfigurationSection(skillKey);
                        if (s == null) continue;
                        String id = skillKey.toLowerCase();
                        String name = s.getString("name", capitalize(skillKey));
                        String desc = s.getString("description", "");
                        boolean signature = s.getBoolean("signature", false);
                        list.add(new SkillDefinition(id, name, desc, signature));
                    }
                    byTier.put(tierKey.toLowerCase(), list);
                }
            }
        }

        if (tiers.isEmpty()) {
            tiers.add(new Tier("journeyman", "Journeyman", "J", 0));
            tiers.add(new Tier("artisan", "Artisan", "A", 800));
            tiers.add(new Tier("master", "Master", "M", 3500));
            tiers.add(new Tier("grandmaster", "Grandmaster", "GM", 12000));
            tiers.add(new Tier("legend", "Legend", "L", 35000));
        }
    }

    // ── Accessors ──────────────────────────────────────────

    public List<Specialization> specializations() {
        return new ArrayList<>(specializations.values());
    }

    public Map<String, Specialization> specializationMap() {
        return specializations;
    }

    public List<Tier> tiers() {
        return tiers;
    }

    public int totalSkills() {
        int count = 0;
        for (var byTier : skills.values()) {
            for (var list : byTier.values()) {
                count += list.size();
            }
        }
        return count;
    }

    public Specialization getSpecialization(String id) {
        return specializations.get(id.toLowerCase());
    }

    public Tier getTier(int xp) {
        Tier current = tiers.get(0);
        for (Tier t : tiers) {
            if (xp >= t.xp) current = t;
        }
        return current;
    }

    public Tier getTier(String specId, UUID uuid, SkillEngine engine) {
        return getTier(engine.xpFor(uuid, specId));
    }

    public int xpForNextTier(int xp) {
        Tier current = getTier(xp);
        int idx = tiers.indexOf(current);
        if (idx + 1 < tiers.size()) {
            return tiers.get(idx + 1).xp - xp;
        }
        return 0;
    }

    public String activeSpec(UUID uuid, SkillEngine engine) {
        return engine.activeSpec(uuid);
    }

    public int xpFor(String specId, UUID uuid, SkillEngine engine) {
        return engine.xpFor(uuid, specId);
    }

    public boolean hasSkill(String specId, String skillId, UUID uuid, SkillEngine engine) {
        return engine.hasSkill(uuid, specId, skillId);
    }

    public List<SkillDefinition> skillsFor(String specId, String tierId) {
        Map<String, List<SkillDefinition>> byTier = skills.get(specId.toLowerCase());
        if (byTier == null) return Collections.emptyList();
        return byTier.getOrDefault(tierId.toLowerCase(), Collections.emptyList());
    }

    public boolean vaultEnabled() {
        return vaultEnabled;
    }

    public boolean bossbarEnabled() {
        return bossbarEnabled;
    }

    public String colored(String text) {
        return ChatColor.translateAlternateColorCodes('&', text);
    }

    private String capitalize(String s) {
        if (s == null || s.isEmpty()) return s;
        return s.substring(0, 1).toUpperCase() + s.substring(1).toLowerCase();
    }
}
