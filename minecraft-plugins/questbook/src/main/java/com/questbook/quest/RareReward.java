package com.questbook.quest;

import org.bukkit.Material;

public class RareReward {
    private final Material material;
    private final int amount;
    private final double chance; // 0.0 - 1.0

    public RareReward(Material material, int amount, double chance) {
        this.material = material;
        this.amount = amount;
        this.chance = chance;
    }

    public Material getMaterial() { return material; }
    public int getAmount() { return amount; }
    public double getChance() { return chance; }

    public static RareReward fromConfig(String raw) {
        if (raw == null) return null;
        String[] parts = raw.split(":");
        String materialName = parts[0].trim().toUpperCase();
        int amount = 1;
        double chance = 100.0;
        if (parts.length > 1) {
            String[] rest = parts[1].split(",");
            for (String r : rest) {
                if (r.contains("%")) {
                    try { chance = Double.parseDouble(r.replace("%", "").trim()); }
                    catch (NumberFormatException ignored) {}
                } else {
                    try { amount = Integer.parseInt(r.trim()); }
                    catch (NumberFormatException ignored) {}
                }
            }
        }
        Material m;
        try {
            m = Material.valueOf(materialName);
        } catch (IllegalArgumentException e) {
            return null;
        }
        return new RareReward(m, amount, chance);
    }
}
