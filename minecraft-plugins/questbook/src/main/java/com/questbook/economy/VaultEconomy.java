package com.questbook.economy;

import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.lang.reflect.Method;
import java.util.logging.Level;

/**
 * Thin reflective bridge to the Vault economy API.
 * <p>
 * VaultAPI is NOT a compile/runtime dependency of QuestBook. Instead we resolve
 * the {@code net.milkbowl.vault.economy.Economy} class by name at runtime and
 * invoke the needed methods via reflection. This means QuestBook always loads even
 * when no Vault/economy plugin is installed, and will work with ANY economy
 * plugin that registers a Vault {@code Economy} service.
 */
public class VaultEconomy {
    private final JavaPlugin plugin;
    private boolean available = false;
    private Object economy = null;            // an Economy instance
    private Class<?> economyClass = null;
    private Method depositMethod = null;
    private Method currencyNameMethod = null;
    private Method getNameMethod = null;
    private Method balanceMethod = null;

    public VaultEconomy(JavaPlugin plugin) {
        this.plugin = plugin;
    }

    public boolean setup() {
        try {
            economyClass = Class.forName("net.milkbowl.vault.economy.Economy");
        } catch (Throwable t) {
            plugin.getLogger().log(Level.INFO, "Vault/VaultAPI not present - money rewards disabled. Install Vault + any economy plugin to enable money payouts.");
            return false;
        }
        try {
            org.bukkit.plugin.RegisteredServiceProvider<?> rsp =
                Bukkit.getServicesManager().getRegistration(economyClass);
            if (rsp == null) {
                plugin.getLogger().log(Level.INFO, "No economy service registered - money rewards disabled. (Load an economy plugin + Vault, then reload.)");
                return false;
            }
            economy = rsp.getProvider();
            if (economy == null) {
                plugin.getLogger().log(Level.WARNING, "Economy service provider is null - money rewards disabled.");
                return false;
            }
            depositMethod = economyClass.getMethod("depositPlayer", OfflinePlayer.class, double.class);
            currencyNameMethod = economyClass.getMethod("currencyNamePlural");
            getNameMethod = economyClass.getMethod("getName");
            balanceMethod = economyClass.getMethod("getBalance", OfflinePlayer.class);
            plugin.getLogger().log(Level.INFO, "Economy service hooked: {0} (provider={1})", new Object[]{economyName(), rsp.getPlugin().getName()});
            available = true;
            return true;
        } catch (Throwable t) {
            plugin.getLogger().log(Level.WARNING, "Vault economy hook failed: " + t, t);
            return false;
        }
    }

    public boolean isAvailable() { return available; }

    public double deposit(Player player, double amount) {
        if (!available || economy == null || depositMethod == null || amount <= 0) return 0.0;
        try {
            Object resp = depositMethod.invoke(economy, player, amount);
            if (resp != null) {
                // EconomyResponse exposes `amount` as a public field (no getter in VaultAPI 1.7)
                try {
                    return ((Number) resp.getClass().getField("amount").get(resp)).doubleValue();
                } catch (NoSuchFieldException | IllegalAccessException e) {
                    // fallback to transactionSuccess check
                    try {
                        Boolean ok = (Boolean) resp.getClass().getMethod("transactionSuccess").invoke(resp);
                        return ok != null && ok ? amount : 0.0;
                    } catch (Throwable t) {
                        return 0.0;
                    }
                }
            }
        } catch (ReflectiveOperationException e) {
            plugin.getLogger().log(Level.WARNING, "Failed to deposit economy reward for " + player.getName() + ": " + e.getMessage());
        }
        return 0.0;
    }

    public String currencyName(Player player) {
        if (!available || economy == null) return "coins";
        try {
            if (currencyNameMethod != null) {
                Object val = currencyNameMethod.invoke(economy);
                if (val != null && !val.toString().isEmpty()) return val.toString();
            }
            if (getNameMethod != null) return (String) getNameMethod.invoke(economy);
        } catch (ReflectiveOperationException e) {
            // fall through
        }
        return "coins";
    }

    public double balance(OfflinePlayer player) {
        if (!available || economy == null || balanceMethod == null) return 0.0;
        try {
            Object val = balanceMethod.invoke(economy, player);
            return val == null ? 0.0 : ((Number) val).doubleValue();
        } catch (ReflectiveOperationException e) {
            plugin.getLogger().log(Level.WARNING, "Failed to read balance for " + player.getName() + ": " + e.getMessage());
            return 0.0;
        }
    }

    private String economyName() {
        try {
            if (getNameMethod != null) return (String) getNameMethod.invoke(economy);
            return economy != null ? economy.toString() : "unknown";
        } catch (ReflectiveOperationException e) {
            return "unknown";
        }
    }
}
