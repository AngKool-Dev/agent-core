package dev.mcplugins.skillforge;

import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.PluginManager;

import java.lang.reflect.Method;
import java.util.UUID;

/**
 * Static helpers that use Bukkit's plugin manager + reflection to talk to
 * other plugins without compile-time deps. Safe to call even when a plugin
 * is absent (returns safe defaults).
 */
public final class PluginWrapper {

    private PluginWrapper() { }

    // ── ChunkSovereignty ──────────────────────────────────

    public static boolean playerHasClaimedChunk(Plugin caller, UUID uuid) {
        return callPluginSafe(caller, "ChunkSovereignty",
                "dev.mcplugins.chunksovereignty.SovereigntyPlugin",
                null, "playerHasClaimedChunk", uuid);
    }

    // ── MobEcology ────────────────────────────────────────
    // MobEcology has no domestication API yet — check returns false until added.

    public static boolean playerHasDomesticated(Plugin caller, UUID uuid) {
        return callPluginSafe(caller, "MobEcology",
                "dev.mcplugins.mobecology.MobEcologyPlugin",
                null, "playerHasDomesticated", uuid);
    }

    // ── Vault / SovereignEconomy ──────────────────────────

    public static double getVaultBalance(Plugin caller, UUID uuid) {
        return getVaultBalance(caller, Bukkit.getOfflinePlayer(uuid));
    }

    public static double getVaultBalance(Plugin caller, OfflinePlayer player) {
        try {
            PluginManager pm = Bukkit.getPluginManager();
            Plugin vault = pm.getPlugin("Vault");
            if (vault == null) return 0;

            Class<?> api = Class.forName("net.milkbowl.vault.economy.Economy");
            Method getEconomy = Class.forName("net.milkbowl.vault.Vault").getMethod("getEconomy");
            Object economy = getEconomy.invoke(vault);
            if (economy == null) return 0;

            Number bal = (Number) api.getMethod("getBalance", OfflinePlayer.class).invoke(economy, player);
            return bal != null ? bal.doubleValue() : 0;
        } catch (Exception e) {
            return 0;
        }
    }

    public static boolean deductVaultBalance(Plugin caller, UUID uuid, double amount) {
        try {
            PluginManager pm = Bukkit.getPluginManager();
            Plugin vault = pm.getPlugin("Vault");
            if (vault == null) return false;

            Class<?> api = Class.forName("net.milkbowl.vault.economy.Economy");
            Method getEconomy = Class.forName("net.milkbowl.vault.Vault").getMethod("getEconomy");
            Object economy = getEconomy.invoke(vault);
            if (economy == null) return false;

            OfflinePlayer op = Bukkit.getOfflinePlayer(uuid);
            economy.getClass().getMethod("withdrawPlayer", OfflinePlayer.class, double.class).invoke(economy, op, amount);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // ── SovereignEconomy direct wallet ─────────────────────

    public static int getWalletBalance(Plugin caller, UUID uuid) {
        return callPluginSafeInt(caller, "SovereignEconomy",
                "dev.mcplugins.sovereigneconomy.SovereignEconomyPlugin",
                null, "getWalletBalanceDirect", uuid);
    }

    public static boolean deductWalletBalance(Plugin caller, UUID uuid, double amount) {
        return callPluginSafe(caller, "SovereignEconomy",
                "dev.mcplugins.sovereigneconomy.SovereignEconomyPlugin",
                null, "deductWalletBalanceDirect", uuid, amount);
    }

    // ── Internal helpers ──────────────────────────────────

    private static boolean callPluginSafe(Plugin caller, String pluginName,
            String pluginClass, String getter, String method, Object... args) {
        try {
            PluginManager pm = Bukkit.getPluginManager();
            Plugin plugin = pm.getPlugin(pluginName);
            if (plugin == null) return false;
            Class<?> cls = pluginClass != null ? plugin.getClass().getClassLoader().loadClass(pluginClass) : plugin.getClass();
            Object target = getter != null ? cls.getMethod(getter).invoke(plugin) : plugin;
            Method m = findMethod(cls, method, args);
            Object result = m.invoke(target, args);
            if (result instanceof Boolean b) return b;
            return false;
        } catch (Exception e) {
            return false;
        }
    }

    private static int callPluginSafeInt(Plugin caller, String pluginName,
            String pluginClass, String getter, String method, Object... args) {
        try {
            PluginManager pm = Bukkit.getPluginManager();
            Plugin plugin = pm.getPlugin(pluginName);
            if (plugin == null) return 0;
            Class<?> cls = pluginClass != null ? plugin.getClass().getClassLoader().loadClass(pluginClass) : plugin.getClass();
            Object target = getter != null ? cls.getMethod(getter).invoke(plugin) : plugin;
            Method m = findMethod(cls, method, args);
            Object result = m.invoke(target, args);
            return result != null ? ((Number) result).intValue() : 0;
        } catch (Exception e) {
            return 0;
        }
    }

    private static Method findMethod(Class<?> cls, String name, Object[] args) throws NoSuchMethodException {
        Class<?>[] paramTypes = argsToClasses(args);
        try {
            return cls.getMethod(name, paramTypes);
        } catch (NoSuchMethodException e) {
            // Try finding a method whose parameter count matches (for primitive coercion)
            for (Method m : cls.getMethods()) {
                if (m.getName().equals(name) && m.getParameterCount() == args.length) {
                    return m;
                }
            }
            throw e;
        }
    }

    private static Class<?>[] argsToClasses(Object[] args) {
        Class<?>[] cs = new Class<?>[args.length];
        for (int i = 0; i < args.length; i++) {
            cs[i] = args[i].getClass();
        }
        return cs;
    }
}
