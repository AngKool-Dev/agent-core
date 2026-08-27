package dev.mcplugins.mobecology;

import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.LivingEntity;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

public final class AdaptationManager {

    private enum Accent { SWIFT, ANCHORED, KEEN }

    private final MobEcologyPlugin plugin;
    private final Attribute hp;
    private final Attribute speed;
    private final Attribute armor;
    private final Attribute damage;
    private final Attribute follow;
    private final Attribute knockback;
    private final Attribute toughness;

    private final NamespacedKey tierKey;
    private final NamespacedKey baseHp;
    private final NamespacedKey baseSpeed;
    private final NamespacedKey baseArmor;
    private final NamespacedKey baseDamage;
    private final NamespacedKey baseFollow;
    private final NamespacedKey baseKb;
    private final NamespacedKey baseTough;

    AdaptationManager(MobEcologyPlugin plugin, Attribute hp, Attribute speed,
                      Attribute armor, Attribute damage, Attribute follow,
                      Attribute knockback, Attribute toughness) {
        this.plugin = plugin;
        this.hp = hp;
        this.speed = speed;
        this.armor = armor;
        this.damage = damage;
        this.follow = follow;
        this.knockback = knockback;
        this.toughness = toughness;
        this.tierKey = new NamespacedKey(plugin, "eco_tier");
        this.baseHp = new NamespacedKey(plugin, "eco_base_hp");
        this.baseSpeed = new NamespacedKey(plugin, "eco_base_speed");
        this.baseArmor = new NamespacedKey(plugin, "eco_base_armor");
        this.baseDamage = new NamespacedKey(plugin, "eco_base_damage");
        this.baseFollow = new NamespacedKey(plugin, "eco_base_follow");
        this.baseKb = new NamespacedKey(plugin, "eco_base_kb");
        this.baseTough = new NamespacedKey(plugin, "eco_base_tough");
    }

    public int tierFor(String species, EcologyRegion region) {
        double pressure = region.pressure.getOrDefault(species, 0.0);
        int tier = 0;
        for (int t : plugin.settings().tierThresholds) {
            if (pressure >= t) {
                tier++;
            }
        }
        return Math.min(tier, 3);
    }

    static Accent accentFor(String species) {
        return Accent.values()[Math.floorMod(species.hashCode(), Accent.values().length)];
    }

    void apply(LivingEntity le, MobEcologyPlugin.Category cat, EcologyRegion region, String species) {
        MobEcologyPlugin.Settings s = plugin.settings();
        if (!s.adaptEnabled) {
            return;
        }
        int t = tierFor(species, region);
        if (t <= 0) {
            return;
        }
        PersistentDataContainer pdc = le.getPersistentDataContainer();
        int stored = pdc.getOrDefault(tierKey, PersistentDataType.INTEGER, 0);
        if (stored >= t) {
            return;
        }
        boolean hostile = cat == MobEcologyPlugin.Category.HOSTILE;
        scale(pdc, le, hp, baseHp, 0.15 * t, 2.2);

        if (!s.variedTraits) {
            if (t >= 2) {
                scale(pdc, le, speed, baseSpeed, 0.08 * t, 1.6);
                if (hostile) {
                    scale(pdc, le, damage, baseDamage, 0.10 * t, 1.8);
                } else {
                    bump(pdc, le, armor, baseArmor, 2.0 * t, -1);
                }
            }
            if (t >= 3) {
                scale(pdc, le, follow, baseFollow, 0.15 * t, 6.0);
            }
        } else {
            if (t >= 2) {
                if (hostile) {
                    scale(pdc, le, damage, baseDamage, 0.10 * t, 1.8);
                } else {
                    bump(pdc, le, armor, baseArmor, 2.0 * t, -1);
                }
                Accent accent = accentFor(species);
                switch (accent) {
                    case SWIFT -> scale(pdc, le, speed, baseSpeed, 0.05 * t, 1.5);
                    case ANCHORED -> bump(pdc, le, knockback, baseKb, 0.12 * t, 0.85);
                    case KEEN -> scale(pdc, le, follow, baseFollow, 0.08 * t, 1.8);
                }
            }
            if (t >= 3) {
                bump(pdc, le, toughness, baseTough, 0.75 * t, -1);
            }
        }
        pdc.set(tierKey, PersistentDataType.INTEGER, t);
    }

    private void scale(PersistentDataContainer pdc, LivingEntity le, Attribute attr,
                       NamespacedKey baseKey, double fractionPerTier, double maxFactor) {
        if (attr == null) {
            return;
        }
        AttributeInstance inst = le.getAttribute(attr);
        if (inst == null) {
            return;
        }
        Double base = pdc.get(baseKey, PersistentDataType.DOUBLE);
        if (base == null || base <= 0) {
            base = inst.getBaseValue();
            pdc.set(baseKey, PersistentDataType.DOUBLE, base);
        }
        double target = base * (1.0 + fractionPerTier);
        target = Math.min(target, base * maxFactor);
        inst.setBaseValue(target);
    }

    private void bump(PersistentDataContainer pdc, LivingEntity le, Attribute attr,
                      NamespacedKey baseKey, double amount, double maxTotal) {
        if (attr == null) {
            return;
        }
        AttributeInstance inst = le.getAttribute(attr);
        if (inst == null) {
            return;
        }
        Double base = pdc.get(baseKey, PersistentDataType.DOUBLE);
        if (base == null) {
            base = inst.getBaseValue();
            pdc.set(baseKey, PersistentDataType.DOUBLE, base);
        }
        double target = base + amount;
        if (maxTotal > 0) {
            target = Math.min(target, maxTotal);
        }
        inst.setBaseValue(target);
    }
}
