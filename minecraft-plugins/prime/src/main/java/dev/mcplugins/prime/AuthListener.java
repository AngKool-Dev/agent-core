package dev.mcplugins.prime;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public final class AuthListener implements Listener {

    private final PrimePlugin plugin;
    private final AuthManager auth;
    private final Map<UUID, AuthSession> sessions = new ConcurrentHashMap<>();

    public AuthListener(PrimePlugin plugin, AuthManager auth) {
        this.plugin = plugin;
        this.auth = auth;
    }

    @EventHandler
    public void onPreLogin(AsyncPlayerPreLoginEvent event) {
        UUID uuid = event.getUniqueId();
        if (auth.isPremium(Bukkit.getOfflinePlayer(uuid))) {
            plugin.getDatabase().backup();
        }
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        UUID uuid = player.getUniqueId();
        String status = auth.getStatus(uuid);

        AuthSession session = new AuthSession(uuid, status, player.getName());
        sessions.put(uuid, session);

        if ("premium".equals(status) && plugin.getConfig().getBoolean("sessions.auto-login-premium")) {
            session.setAuthenticated(true);
            auth.recordLogin(uuid, player.getName(), player.getAddress().getAddress().getHostAddress());
            player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.premium-welcome", "&aPremium account detected. Welcome, {player}!")
                    .replace("{player}", player.getName())));
            return;
        }

        if ("cracked".equals(status) && plugin.getConfig().getLong("sessions.session-ttl", 86400) > 0) {
            plugin.getDatabase().async(() -> {
                try (var ps = plugin.getDatabase().prepareStatement(
                        "SELECT token, expires_at FROM prime_sessions WHERE player_uuid = ?")) {
                    ps.setString(1, uuid.toString());
                    try (var rs = ps.executeQuery()) {
                        if (rs.next()) {
                            long expires = rs.getLong("expires_at");
                            if (System.currentTimeMillis() < expires) {
                                String token = rs.getString("token");
                                session.setSessionToken(token);
                                session.setAuthenticated(true);
                                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.session-restored", "&aSession restored. Welcome back, {player}!")
                                        .replace("{player}", player.getName())));
                                auth.recordLogin(uuid, player.getName(), player.getAddress().getAddress().getHostAddress());
                                return;
                            }
                        }
                    }
                } catch (Exception e) {
                    plugin.getLogger().warning("Prime session check failed: " + e.getMessage());
                }
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auth-required", "&cPlease authenticate with /login <password>")));
            });
            return;
        }

        if ("cracked".equals(status) && !session.isAuthenticated()) {
            player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auth-required", "&cPlease authenticate with /login <password>")));
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        UUID uuid = event.getPlayer().getUniqueId();
        AuthSession session = sessions.remove(uuid);
        if (session != null && session.isAuthenticated() && session.getSessionToken() != null) {
            long ttl = plugin.getConfig().getLong("sessions.session-ttl", 86400) * 1000L;
            long expires = System.currentTimeMillis() + ttl;
            plugin.getDatabase().async(() -> {
                try (var ps = plugin.getDatabase().prepareStatement(
                        "INSERT OR REPLACE INTO prime_sessions (token, player_uuid, expires_at) VALUES (?, ?, ?)")) {
                    ps.setString(1, session.getSessionToken());
                    ps.setString(2, uuid.toString());
                    ps.setLong(3, expires);
                    ps.executeUpdate();
                } catch (Exception e) {
                    plugin.getLogger().warning("Prime session save failed: " + e.getMessage());
                }
            });
        }
    }

    public AuthSession getSession(UUID uuid) {
        return sessions.get(uuid);
    }

    public Map<UUID, AuthSession> getSessions() {
        return sessions;
    }

    public static class AuthSession {
        private final UUID uuid;
        private final String status;
        private final String username;
        private boolean authenticated;
        private String sessionToken;

        public AuthSession(UUID uuid, String status, String username) {
            this.uuid = uuid;
            this.status = status;
            this.username = username;
        }

        public UUID getUuid() { return uuid; }
        public String getStatus() { return status; }
        public String getUsername() { return username; }
        public boolean isAuthenticated() { return authenticated; }
        public void setAuthenticated(boolean authenticated) { this.authenticated = authenticated; }
        public String getSessionToken() { return sessionToken; }
        public void setSessionToken(String sessionToken) { this.sessionToken = sessionToken; }
    }
}
