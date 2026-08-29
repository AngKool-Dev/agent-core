package dev.mcplugins.skillforge;

import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.NamespacedKey;
import io.papermc.paper.persistence.PersistentDataContainerView;
import org.bukkit.plugin.PluginManager;

import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

public final class SkillEngine {

    final SkillForgePlugin plugin;
    final Map<UUID, Map<String, Integer>> xp = new ConcurrentHashMap<>();
    final Map<UUID, Map<String, Set<String>>> unlocked = new ConcurrentHashMap<>();
    final Map<UUID, String> activeSpec = new ConcurrentHashMap<>();
    final Map<UUID, AtomicInteger> totalCrafts = new ConcurrentHashMap<>();
    final Map<String, String> itemSignatures = new ConcurrentHashMap<>();
    final Map<UUID, Set<UUID>> apprenticeships = new ConcurrentHashMap<>();
    final Map<UUID, Integer> reputation = new ConcurrentHashMap<>();

    public SkillEngine(SkillForgePlugin plugin) {
        this.plugin = plugin;
    }

    public int xpFor(UUID uuid, String specId) {
        Map<String, Integer> m = xp.get(uuid);
        if (m == null) return 0;
        Integer v = m.get(specId.toLowerCase());
        return v == null ? 0 : v;
    }

    public int xpFor(UUID uuid) {
        Map<String, Integer> m = xp.get(uuid);
        if (m == null) return 0;
        return m.values().stream().mapToInt(Integer::intValue).sum();
    }

    public int totalCraftsFor(UUID uuid) {
        AtomicInteger ai = totalCrafts.get(uuid);
        return ai == null ? 0 : ai.get();
    }

    public int reputationFor(UUID uuid) {
        return reputation.getOrDefault(uuid, 0);
    }

    public void addXP(UUID uuid, String specId, int amount) {
        if (amount <= 0) return;
        Map<String, Integer> m = xp.computeIfAbsent(uuid, k -> new ConcurrentHashMap<>());
        String s = specId.toLowerCase();
        int before = m.getOrDefault(s, 0);
        int after = before + amount;
        m.put(s, after);
        plugin.markDirty();
        onTierUp(uuid, specId, before, after);
    }

    public void addXP(UUID uuid, int amount) {
        String spec = activeSpec.get(uuid);
        if (spec == null) return;
        addXP(uuid, spec, amount);
    }

    public void addReputation(UUID uuid, int amount) {
        reputation.merge(uuid, amount, Integer::sum);
        plugin.markDirty();
    }

    public void setActiveSpec(UUID uuid, String specId) {
        activeSpec.put(uuid, specId.toLowerCase());
        plugin.markDirty();
    }

    public String activeSpec(UUID uuid) {
        return activeSpec.get(uuid);
    }

    public boolean unlockSkill(UUID uuid, String specId, String skillId) {
        Map<String, Set<String>> u = unlocked.computeIfAbsent(uuid, k -> new ConcurrentHashMap<>());
        Set<String> s = u.computeIfAbsent(specId.toLowerCase(), k -> ConcurrentHashMap.newKeySet());
        String sid = skillId.toLowerCase();
        if (s.contains(sid)) return false;
        s.add(sid);
        plugin.markDirty();
        return true;
    }

    public boolean hasSkill(UUID uuid, String specId, String skillId) {
        Map<String, Set<String>> u = unlocked.get(uuid);
        if (u == null) return false;
        Set<String> s = u.get(specId.toLowerCase());
        if (s == null) return false;
        return s.contains(skillId.toLowerCase());
    }

    public Set<String> unlockedSkills(UUID uuid, String specId) {
        Map<String, Set<String>> u = unlocked.get(uuid);
        if (u == null) return Collections.emptySet();
        Set<String> s = u.get(specId.toLowerCase());
        return s == null ? Collections.emptySet() : s;
    }

    public int awardCraftXP(UUID uuid, String specId, ItemStack crafted) {
        Settings s = plugin.settings();
        int base = (int) s.craftingBaseCost;
        double bonus = 0;

        if (hasEchoAttuned(uuid)) {
            bonus += s.echoAttuneXPBonus;
        }
        if (isEcologyRare(crafted.getType())) {
            bonus += s.ecologyRareDropXP;
        }
        double claimMult = 1.0;
        if (hasWorkshopInChunk(uuid)) {
            claimMult += s.claimWorkshopBonus;
        }

        int total = (int) Math.round(base * (1 + bonus) * claimMult);
        totalCrafts.computeIfAbsent(uuid, k -> new AtomicInteger()).incrementAndGet();
        addXP(uuid, specId, total);
        return total;
    }

    public ItemStack signatureItem(UUID uuid, String specId, ItemStack base) {
        Settings s = plugin.settings();
        String spec = specId.toLowerCase();
        int xp = xpFor(uuid, specId);
        Tier tier = s.getTier(xp);

        if (tier.id.equals("journeyman")) {
            return null;
        }

        boolean grandmaster = tier.id.equals("grandmaster") || tier.id.equals("legend");
        double cost = s.craftingBaseCost * (1 + (grandmaster ? s.grandmasterCraftPremium : 0));

        if (s.vaultEnabled) {
            if (PluginWrapper.getVaultBalance(plugin, uuid) < cost) {
                return null;
            }
            PluginWrapper.deductVaultBalance(plugin, uuid, cost);
        } else {
            if (getNativeBalance(uuid) < cost) {
                return null;
            }
            deductNativeBalance(uuid, cost);
        }

        if (base == null) {
            base = new ItemStack(org.bukkit.Material.EMERALD);
        }

        ItemStack copy = base.clone();
        ItemMeta meta = copy.getItemMeta();
        if (meta == null) return null;
        org.bukkit.persistence.PersistentDataContainer pd = meta.getPersistentDataContainer();
        pd.set(new NamespacedKey(plugin, "spec"), PersistentDataType.STRING, spec);
        pd.set(new NamespacedKey(plugin, "tier"), PersistentDataType.STRING, tier.id);
        pd.set(new NamespacedKey(plugin, "xp"), PersistentDataType.INTEGER, xp);
        pd.set(new NamespacedKey(plugin, "uuid"), PersistentDataType.STRING, uuid.toString());
        pd.set(new NamespacedKey(plugin, "sf_count"), PersistentDataType.INTEGER, totalCraftsFor(uuid));

        String sigId = spec + "_" + tier.id + "_" + totalCraftsFor(uuid);
        itemSignatures.put(sigId, specId + " \u2022 " + tier.name + " \u2022 #" + totalCraftsFor(uuid) + " by " + getName(uuid));
        pd.set(new NamespacedKey(plugin, "sig_id"), PersistentDataType.STRING, sigId);
        copy.setItemMeta(meta);
        return copy;
    }

    public boolean isSignature(ItemStack item) {
        if (item == null || item.getType().isAir()) return false;
        PersistentDataContainerView pd = item.getPersistentDataContainer();
        return pd.has(new NamespacedKey(plugin, "spec")) &&
                pd.has(new NamespacedKey(plugin, "sf_count"));
    }

    public SignatureInfo signatureInfo(ItemStack item) {
        if (!isSignature(item)) return null;
        PersistentDataContainerView pd = item.getPersistentDataContainer();
        String spec = pd.get(new NamespacedKey(plugin, "spec"), PersistentDataType.STRING);
        String tier = pd.get(new NamespacedKey(plugin, "tier"), PersistentDataType.STRING);
        int xp = pd.get(new NamespacedKey(plugin, "xp"), PersistentDataType.INTEGER);
        String uuidStr = pd.get(new NamespacedKey(plugin, "uuid"), PersistentDataType.STRING);
        int count = pd.get(new NamespacedKey(plugin, "sf_count"), PersistentDataType.INTEGER);
        String sigId = pd.get(new NamespacedKey(plugin, "sig_id"), PersistentDataType.STRING);
        UUID uuid = uuidStr != null ? UUID.fromString(uuidStr) : null;
        String forgeName = itemSignatures.get(sigId);
        return new SignatureInfo(spec, tier, xp, uuid, count, forgeName);
    }

    public void apprentice(UUID master, UUID appr) {
        Set<UUID> s = apprenticeships.computeIfAbsent(master, k -> ConcurrentHashMap.newKeySet());
        if (s.add(appr)) {
            plugin.markDirty();
        }
    }

    public void unapprentice(UUID master, UUID appr) {
        Set<UUID> s = apprenticeships.get(master);
        if (s != null && s.remove(appr)) {
            plugin.markDirty();
        }
    }

    public Set<UUID> apprenticesOf(UUID master) {
        return apprenticeships.getOrDefault(master, Collections.emptySet());
    }

    public boolean isApprenticeOf(UUID appr, UUID master) {
        return apprenticeships.getOrDefault(master, Collections.emptySet()).contains(appr);
    }

    public Map<UUID, Set<UUID>> apprenticeships() {
        return apprenticeships;
    }

    public void awardApprenticeXP(UUID apprentice, int amount) {
        addXP(apprentice, amount);
    }

    public int getApprenticeCount(UUID master) {
        return apprenticeships.getOrDefault(master, Collections.emptySet()).size();
    }

    public boolean canAcceptApprentice(UUID master) {
        Settings s = plugin.settings();
        String spec = activeSpec.get(master);
        if (spec == null) return false;
        Specialization sp = s.getSpecialization(spec);
        if (sp == null) return false;
        return getApprenticeCount(master) < sp.maxApprentices;
    }

    public void recordCraft(UUID uuid, String specId) {
        totalCrafts.computeIfAbsent(uuid, k -> new AtomicInteger()).incrementAndGet();
        plugin.markDirty();
    }

    // ── Cross-plugin accessors ─────────────────────────────

    public double getVaultBalance(UUID uuid) {
        return PluginWrapper.getVaultBalance(plugin, uuid);
    }

    public boolean deductVaultBalance(UUID uuid, double amount) {
        return PluginWrapper.deductVaultBalance(plugin, uuid, amount);
    }

    public int getNativeBalance(UUID uuid) {
        return PluginWrapper.getWalletBalance(plugin, uuid);
    }

    public void deductNativeBalance(UUID uuid, double amount) {
        PluginWrapper.deductWalletBalance(plugin, uuid, amount);
    }

    public boolean hasEchoAttuned(UUID uuid) {
        return false;
    }

    public boolean hasWorkshopInChunk(UUID uuid) {
        return PluginWrapper.playerHasClaimedChunk(plugin, uuid);
    }

    // ── Internal ───────────────────────────────────────────

    private void onTierUp(UUID uuid, String specId, int before, int after) {
        Settings s = plugin.settings();
        Tier oldTier = s.getTier(before);
        Tier newTier = s.getTier(after);
        if (!oldTier.id.equals(newTier.id)) {
            String name = getName(uuid);
            if (name != null) {
                plugin.getLogger().info("[SkillForge] " + name + " reached " + newTier.name + " in " + specId);
            }
            if (newTier.id.equals("master") || newTier.id.equals("grandmaster") || newTier.id.equals("legend")) {
                unlockAllSkills(uuid, specId, after);
            }
        }
    }

    private void unlockAllSkills(UUID uuid, String specId, int after) {
        Settings s = plugin.settings();
        String spec = specId.toLowerCase();
        Map<String, Map<String, java.util.List<SkillDefinition>>> skills = s.skills;
        if (skills == null) return;
        Map<String, java.util.List<SkillDefinition>> byTier = skills.get(spec);
        if (byTier == null) return;
        for (java.util.List<SkillDefinition> list : byTier.values()) {
            for (SkillDefinition sd : list) {
                if (!hasSkill(uuid, specId, sd.id)) {
                    unlockSkill(uuid, specId, sd.id);
                }
            }
        }
    }

    private boolean isEcologyRare(org.bukkit.Material mat) {
        return mat == org.bukkit.Material.AMETHYST_SHARD ||
                mat == org.bukkit.Material.DIAMOND ||
                mat == org.bukkit.Material.NETHERITE_INGOT ||
                mat == org.bukkit.Material.EMERALD;
    }

    private String getName(UUID uuid) {
        OfflinePlayer p = Bukkit.getOfflinePlayer(uuid);
        return p.getName();
    }
}
