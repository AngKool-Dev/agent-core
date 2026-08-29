package dev.mcplugins.prime;

import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.sql.*;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

public final class DatabaseManager {

    private final JavaPlugin plugin;
    private final Executor executor = Executors.newSingleThreadExecutor();
    private final File dbFile;
    private Connection connection;

    public DatabaseManager(JavaPlugin plugin) {
        this.plugin = plugin;
        this.dbFile = new File(plugin.getDataFolder(), plugin.getConfig().getString("database.file", "prime.db"));
    }

    public synchronized void connect() throws SQLException {
        if (connection != null && !connection.isClosed()) {
            return;
        }
        String url = "jdbc:sqlite:" + dbFile.getAbsolutePath();
        connection = DriverManager.getConnection(url);
        connection.setAutoCommit(true);
        try (Statement stmt = connection.createStatement()) {
            stmt.execute("""
                CREATE TABLE IF NOT EXISTS prime_players (
                    uuid TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT,
                    is_premium INTEGER NOT NULL DEFAULT 0,
                    registered_at INTEGER NOT NULL,
                    last_login INTEGER NOT NULL,
                    last_ip TEXT
                )
                """);
            stmt.execute("""
                CREATE TABLE IF NOT EXISTS prime_sessions (
                    token TEXT PRIMARY KEY,
                    player_uuid TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    FOREIGN KEY (player_uuid) REFERENCES prime_players(uuid) ON DELETE CASCADE
                )
                """);
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON prime_sessions(expires_at)");
        }
    }

    public synchronized void disconnect() {
        if (connection != null) {
            try {
                connection.close();
            } catch (SQLException ignored) {
            } finally {
                connection = null;
            }
        }
    }

    public void async(Runnable task) {
        executor.execute(task);
    }

    public void backup() {
        async(() -> {
            try {
                if (!dbFile.exists()) return;
                Path backup = Path.of(dbFile.getAbsolutePath() + ".bak");
                Files.copy(dbFile.toPath(), backup, StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException e) {
                plugin.getLogger().warning("Prime database backup failed: " + e.getMessage());
            }
        });
    }

    public synchronized Connection getConnection() throws SQLException {
        if (connection == null || connection.isClosed()) {
            connect();
        }
        return connection;
    }

    public synchronized PreparedStatement prepareStatement(String sql) throws SQLException {
        return getConnection().prepareStatement(sql);
    }
}
