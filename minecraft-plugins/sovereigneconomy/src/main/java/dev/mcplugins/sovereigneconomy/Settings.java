package dev.mcplugins.sovereigneconomy;

import org.bukkit.configuration.ConfigurationSection;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Settings {

    public String currencySymbol = "S";
    public String currencyNameSingular = "sovereign";
    public String currencyNamePlural = "sovereigns";
    public double startingBalance = 250.0;
    public double spread = 0.05;
    public double reversionPerHour = 0.06;
    public int autosaveSeconds = 300;

    public double baseAnnualRate = 0.04;
    public double minAnnualRate = 0.005;
    public double maxAnnualRate = 0.10;
    public double inflationTarget = 0.02;
    public double rateStep = 0.005;
    public int interestIntervalMinutes = 60;

    public int eventIntervalMinutes = 45;
    public double eventChance = 0.65;

    public boolean vaultEnabled = true;

    public final Map<String, Commodity> commodities = new LinkedHashMap<>();

    public void load(SovereignEconomyPlugin plugin) {
        var c = plugin.getConfig();
        currencySymbol = c.getString("currency.symbol", "S");
        currencyNameSingular = c.getString("currency.name-singular", "sovereign");
        currencyNamePlural = c.getString("currency.name-plural", "sovereigns");
        startingBalance = Math.max(0, c.getDouble("currency.starting-balance", 250.0));
        spread = Math.min(0.4, Math.max(0.0, c.getDouble("market.spread", 0.05)));
        reversionPerHour = Math.min(1.0, Math.max(0.0, c.getDouble("market.reversion-per-hour", 0.06)));
        autosaveSeconds = Math.max(30, c.getInt("storage.autosave-seconds", 300));

        baseAnnualRate = c.getDouble("bank.base-annual-rate", 0.04);
        minAnnualRate = c.getDouble("bank.min-annual-rate", 0.005);
        maxAnnualRate = c.getDouble("bank.max-annual-rate", 0.10);
        inflationTarget = c.getDouble("bank.inflation-target", 0.02);
        rateStep = c.getDouble("bank.rate-step", 0.005);
        interestIntervalMinutes = Math.max(5, c.getInt("bank.interval-minutes", 60));

        eventIntervalMinutes = Math.max(5, c.getInt("events.interval-minutes", 45));
        eventChance = Math.min(1.0, Math.max(0.0, c.getDouble("events.chance", 0.65)));

        vaultEnabled = c.getBoolean("vault.enabled", true);

        commodities.clear();
        ConfigurationSection sec = c.getConfigurationSection("market.commodities");
        if (sec != null) {
            for (String id : sec.getKeys(false)) {
                ConfigurationSection e = sec.getConfigurationSection(id);
                if (e == null) {
                    continue;
                }
                double base = e.getDouble("base", 1.0);
                double depth = e.getDouble("depth", 500);
                if (base > 0 && !commodities.containsKey(id.toLowerCase())) {
                    commodities.put(id.toLowerCase(),
                            new Commodity(id.toLowerCase(), base, depth));
                }
            }
        }
    }
}
