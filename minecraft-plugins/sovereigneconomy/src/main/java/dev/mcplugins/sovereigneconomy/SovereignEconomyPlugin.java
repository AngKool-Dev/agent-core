package dev.mcplugins.sovereigneconomy;

import net.milkbowl.vault.economy.Economy;
import org.bukkit.Bukkit;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.ServicePriority;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.UUID;

public final class SovereignEconomyPlugin extends JavaPlugin {

    private final Settings settings = new Settings();
    private Ledger ledger;
    private MarketEngine market;
    private BankEngine bank;
    private EventEngine events;
    private EconomyStore store;
    private volatile boolean dirty;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        settings.load(this);

        ledger = new Ledger(this);
        market = new MarketEngine(this);
        bank = new BankEngine(this);
        events = new EventEngine(this);
        store = new EconomyStore(this);
        store.load(ledger, market, bank);

        EconomyCommands commands = new EconomyCommands(this);
        for (String name : new String[]{"money", "bal", "balance", "pay", "market", "bank", "eco", "se"}) {
            PluginCommand cmd = getCommand(name.equals("bal") || name.equals("balance") ? "money" : name);
            if (cmd != null) {
                cmd.setExecutor(commands);
                cmd.setTabCompleter(commands);
            }
        }

        if (settings.vaultEnabled) {
            try {
                Class.forName("net.milkbowl.vault.economy.Economy");
                if (getServer().getPluginManager().getPlugin("Vault") != null) {
                    VaultBridge bridge = new VaultBridge(this);
                    getServer().getServicesManager().register(Economy.class, bridge,
                            this, ServicePriority.High);
                    getLogger().info("Registered as high-priority Vault economy provider.");
                } else {
                    getLogger().info("Vault plugin absent - running standalone.");
                }
            } catch (ClassNotFoundException ex) {
                getLogger().info("VaultAPI not present - running standalone.");
            }
        }

        long interestTicks = settings.interestIntervalMinutes * 60L * 20L;
        long eventTicks = settings.eventIntervalMinutes * 60L * 20L;
        long autosaveTicks = settings.autosaveSeconds * 20L;

        Bukkit.getScheduler().runTaskTimer(this, this::interestTick,
                interestTicks, interestTicks);
        Bukkit.getScheduler().runTaskTimer(this, this::eventTick,
                eventTicks / 2 + (long) (Math.random() * eventTicks / 2), eventTicks);
        Bukkit.getScheduler().runTaskTimer(this, () -> {
            if (dirty) {
                dirty = false;
                store.saveAsync(ledger, market, bank);
            }
        }, autosaveTicks, autosaveTicks);

        getLogger().info(() -> "SovereignEconomy enabled: " + market.commodities().size()
                + " commodities, spread " + Math.round(settings.spread * 100) + "%, rate "
                + String.format("%.2f%%", bank.annualRate() * 100));
    }

    private void interestTick() {
        bank.adaptRate();
        bank.applyInterest();
        market.revertAll();
        store.saveAsync(ledger, market, bank);
        dirty = false;
    }

    private void eventTick() {
        if (Math.random() < settings.eventChance) {
            events.fireRandom();
        }
    }

    @Override
    public void onDisable() {
        if (store != null && ledger != null && market != null && bank != null) {
            store.saveSync(ledger, market, bank);
        }
    }

    public Settings settings() {
        return settings;
    }

    public Ledger ledger() {
        return ledger;
    }

    public MarketEngine market() {
        return market;
    }

    public BankEngine bank() {
        return bank;
    }

    public EventEngine events() {
        return events;
    }

    public void markDirty() {
        dirty = true;
    }

    public void reloadSettings() {
        reloadConfig();
        settings.load(this);
    }

    // ── SkillForge integration ─────────────────────────────
    public int getWalletBalanceDirect(UUID uuid) {
        return (int) Math.round(ledger.account(uuid).wallet);
    }

    public void deductWalletBalanceDirect(UUID uuid, double amount) {
        ledger.withdraw(uuid, amount);
    }
}
