package dev.mcplugins.prime;

import org.bukkit.plugin.java.JavaPlugin;

public final class PrimePlugin extends JavaPlugin {

    private DatabaseManager database;
    private AuthManager auth;
    private AuthListener listener;

    @Override
    public void onEnable() {
        saveDefaultConfig();

        database = new DatabaseManager(this);
        database.backup();

        try {
            database.connect();
        } catch (Exception e) {
            getLogger().severe("Prime database connection failed: " + e.getMessage());
            getServer().getPluginManager().disablePlugin(this);
            return;
        }

        auth = new AuthManager(this, database);
        listener = new AuthListener(this, auth);

        getServer().getPluginManager().registerEvents(listener, this);
        getServer().getPluginManager().registerEvents(new AuthProtectionListener(this, auth), this);

        AuthCommand executor = new AuthCommand(this);
        getCommand("prime").setExecutor(executor);
        getCommand("prime").setTabCompleter(executor);
        getCommand("register").setExecutor(executor);
        getCommand("login").setExecutor(executor);
        getCommand("changepassword").setExecutor(executor);
        getCommand("auth").setExecutor(executor);

        getLogger().info(() -> "Prime enabled: cracked players must authenticate, premium players bypass.");
    }

    @Override
    public void onDisable() {
        if (listener != null) {
            listener.getSessions().clear();
        }
        if (database != null) {
            database.disconnect();
        }
    }

    public DatabaseManager getDatabase() {
        return database;
    }

    public AuthManager getAuth() {
        return auth;
    }

    public AuthListener getListener() {
        return listener;
    }

    public String colorize(String input) {
        if (input == null) return "";
        return input.replace("&", "§");
    }
}
