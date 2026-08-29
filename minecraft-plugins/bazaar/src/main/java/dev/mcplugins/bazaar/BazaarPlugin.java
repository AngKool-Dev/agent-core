package dev.mcplugins.bazaar;

import net.milkbowl.vault.economy.Economy;
import org.bukkit.plugin.RegisteredServiceProvider;
import org.bukkit.plugin.java.JavaPlugin;

public class BazaarPlugin extends JavaPlugin {

    private BazaarManager manager;
    private BazaarGUI gui;
    private Economy economy;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        saveResource("auctions.yml", false);
        manager = new BazaarManager(this);
        gui = new BazaarGUI(this, manager);
        getServer().getPluginManager().registerEvents(gui, this);

        if (setupEconomy()) {
            getLogger().info("Vault economy hooked.");
        } else {
            getLogger().warning("Vault economy not found. Auctions will not use economy.");
        }

        getCommand("bazaar").setExecutor(new BazaarCommand(this, manager, gui));
        getCommand("bazaar").setTabCompleter(new BazaarCommand(this, manager, gui));
        getCommand("sell").setExecutor(new BazaarCommand(this, manager, gui));
        getCommand("sell").setTabCompleter(new BazaarCommand(this, manager, gui));
        getCommand("list").setExecutor(new BazaarCommand(this, manager, gui));
        getCommand("list").setTabCompleter(new BazaarCommand(this, manager, gui));
        getCommand("cancel").setExecutor(new BazaarCommand(this, manager, gui));
        getCommand("cancel").setTabCompleter(new BazaarCommand(this, manager, gui));

        getLogger().info("Bazaar enabled.");
    }

    @Override
    public void onDisable() {
        if (manager != null) {
            manager.save();
        }
        getLogger().info("Bazaar disabled.");
    }

    private boolean setupEconomy() {
        if (getServer().getPluginManager().getPlugin("Vault") == null) {
            return false;
        }
        RegisteredServiceProvider<Economy> rsp = getServer().getServicesManager().getRegistration(Economy.class);
        if (rsp == null) {
            return false;
        }
        economy = rsp.getProvider();
        return economy != null;
    }

    public Economy getEconomy() {
        return economy;
    }

    public String colorize(String text) {
        if (text == null) return "";
        return text.replace("&", "§");
    }
}
