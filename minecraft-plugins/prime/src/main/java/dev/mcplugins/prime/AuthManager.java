package dev.mcplugins.prime;

import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.Server;
import org.bukkit.entity.Player;
import org.mindrot.jbcrypt.BCrypt;

import java.sql.*;
import java.util.UUID;

public final class AuthManager {

    private final PrimePlugin plugin;
    private final DatabaseManager db;

    public AuthManager(PrimePlugin plugin, DatabaseManager db) {
        this.plugin = plugin;
        this.db = db;
    }

    public boolean isPremium(OfflinePlayer player) {
        if (player.isOnline()) {
            Player online = player.getPlayer();
            if (online != null && online.isOnline()) {
                return online.getUniqueId().version() == 2;
            }
        }
        return player.getUniqueId().version() == 2;
    }

    public boolean isRegistered(UUID uuid) {
        try (PreparedStatement ps = db.prepareStatement(
                "SELECT 1 FROM prime_players WHERE uuid = ?")) {
            ps.setString(1, uuid.toString());
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in isRegistered: " + e.getMessage());
            return false;
        }
    }

    public boolean isUsernameTakenByPremium(String username) {
        try (PreparedStatement ps = db.prepareStatement(
                "SELECT 1 FROM prime_players WHERE LOWER(username) = LOWER(?) AND is_premium = 1")) {
            ps.setString(1, username);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in isUsernameTakenByPremium: " + e.getMessage());
            return false;
        }
    }

    public boolean register(UUID uuid, String username, String password) {
        if (isUsernameTakenByPremium(username)) {
            return false;
        }
        String hash = BCrypt.hashpw(password, BCrypt.gensalt(12));
        String now = String.valueOf(System.currentTimeMillis());
        try (PreparedStatement ps = db.prepareStatement(
                "INSERT OR REPLACE INTO prime_players (uuid, username, password_hash, is_premium, registered_at, last_login) " +
                "VALUES (?, ?, ?, 0, ?, ?)")) {
            ps.setString(1, uuid.toString());
            ps.setString(2, username);
            ps.setString(3, hash);
            ps.setString(4, now);
            ps.setString(5, now);
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in register: " + e.getMessage());
            return false;
        }
    }

    public boolean checkPassword(UUID uuid, String password) {
        try (PreparedStatement ps = db.prepareStatement(
                "SELECT password_hash FROM prime_players WHERE uuid = ?")) {
            ps.setString(1, uuid.toString());
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) return false;
                String hash = rs.getString("password_hash");
                return hash != null && BCrypt.checkpw(password, hash);
            }
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in checkPassword: " + e.getMessage());
            return false;
        }
    }

    public boolean changePassword(UUID uuid, String oldPassword, String newPassword) {
        if (!checkPassword(uuid, oldPassword)) {
            return false;
        }
        String hash = BCrypt.hashpw(newPassword, BCrypt.gensalt(12));
        try (PreparedStatement ps = db.prepareStatement(
                "UPDATE prime_players SET password_hash = ? WHERE uuid = ?")) {
            ps.setString(1, hash);
            ps.setString(2, uuid.toString());
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in changePassword: " + e.getMessage());
            return false;
        }
    }

    public boolean unregister(UUID uuid) {
        try (PreparedStatement ps = db.prepareStatement(
                "DELETE FROM prime_players WHERE uuid = ?")) {
            ps.setString(1, uuid.toString());
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in unregister: " + e.getMessage());
            return false;
        }
    }

    public void recordLogin(UUID uuid, String username, String ip) {
        String now = String.valueOf(System.currentTimeMillis());
        try (PreparedStatement ps = db.prepareStatement(
                "UPDATE prime_players SET last_login = ?, last_ip = ?, username = ? WHERE uuid = ?")) {
            ps.setString(1, now);
            ps.setString(2, ip);
            ps.setString(3, username);
            ps.setString(4, uuid.toString());
            ps.executeUpdate();
        } catch (SQLException e) {
            plugin.getLogger().warning("Prime DB error in recordLogin: " + e.getMessage());
        }
    }

    public String getStatus(UUID uuid) {
        if (isPremium(Bukkit.getOfflinePlayer(uuid))) {
            return "premium";
        }
        if (isRegistered(uuid)) {
            return "cracked";
        }
        return "unknown";
    }
}
