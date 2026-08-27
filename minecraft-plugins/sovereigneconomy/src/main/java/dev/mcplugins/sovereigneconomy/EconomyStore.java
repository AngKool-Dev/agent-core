package dev.mcplugins.sovereigneconomy;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public final class EconomyStore {

    private final SovereignEconomyPlugin plugin;
    private final Path file;

    EconomyStore(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
        this.file = plugin.getDataFolder().toPath().resolve("data").resolve("economy.yml");
    }

    public void load(Ledger ledger, MarketEngine market, BankEngine bank) {
        if (!Files.isRegularFile(file)) {
            return;
        }
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file.toFile());
        ConfigurationSection accounts = y.getConfigurationSection("accounts");
        Map<UUID, Ledger.Account> loaded = new HashMap<>();
        if (accounts != null) {
            for (String key : accounts.getKeys(false)) {
                try {
                    UUID id = UUID.fromString(key);
                    ConfigurationSection a = accounts.getConfigurationSection(key);
                    if (a != null) {
                        loaded.put(id, new Ledger.Account(a.getDouble("wallet"),
                                a.getDouble("savings")));
                    }
                } catch (IllegalArgumentException ignored) {
                }
            }
        }
        ledger.load(loaded);

        ConfigurationSection marketSec = y.getConfigurationSection("market");
        Map<String, Double> mults = new HashMap<>();
        if (marketSec != null) {
            for (String id : marketSec.getKeys(false)) {
                mults.put(id.toLowerCase(), marketSec.getDouble(id + ".mult", 1.0));
            }
        }
        market.loadMults(mults);

        bank.setAnnualRate(y.getDouble("bank.rate", plugin.settings().baseAnnualRate));
    }

    public void saveAsync(Ledger ledger, MarketEngine market, BankEngine bank) {
        String data = serialize(ledger, market, bank);
        plugin.getServer().getScheduler().runTaskAsynchronously(plugin,
                () -> write(data));
    }

    public void saveSync(Ledger ledger, MarketEngine market, BankEngine bank) {
        write(serialize(ledger, market, bank));
    }

    private String serialize(Ledger ledger, MarketEngine market, BankEngine bank) {
        YamlConfiguration y = new YamlConfiguration();
        for (Map.Entry<UUID, Ledger.Account> e : ledger.snapshot().entrySet()) {
            String base = "accounts." + e.getKey() + ".";
            y.set(base + "wallet", round(e.getValue().wallet));
            y.set(base + "savings", round(e.getValue().savings));
        }
        for (Map.Entry<String, Double> e : market.multSnapshot().entrySet()) {
            y.set("market." + e.getKey() + ".mult", Math.round(e.getValue() * 10000.0) / 10000.0);
        }
        y.set("bank.rate", Math.round(bank.annualRate() * 100000.0) / 100000.0);
        return y.saveToString();
    }

    private static double round(double v) {
        return Math.round(v * 100.0) / 100.0;
    }

    private void write(String data) {
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, data);
        } catch (IOException ex) {
            plugin.getLogger().warning("Failed to save economy data: " + ex.getMessage());
        }
    }
}
