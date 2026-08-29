package dev.mcplugins.prime;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

public final class AuthCommand implements CommandExecutor, TabCompleter {

    private final PrimePlugin plugin;

    public AuthCommand(PrimePlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        String sub = args.length == 0 ? "status" : args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "register" -> handleRegister(sender, args);
            case "login" -> handleLogin(sender, args);
            case "changepassword" -> handleChangePassword(sender, args);
            case "status" -> handleStatus(sender);
            case "reload" -> handleReload(sender);
            case "premium" -> handlePremium(sender, args);
            case "unregister" -> handleUnregister(sender);
            default -> sender.sendMessage(plugin.colorize("&cUsage: /prime [register|login|changepassword|status|reload|premium|unregister]"));
        }
        return true;
    }

    private void handleRegister(CommandSender sender, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage(plugin.colorize("&cOnly players can register."));
            return;
        }
        if (args.length < 2) {
            sender.sendMessage(plugin.colorize("&cUsage: /register <password> <confirm>"));
            return;
        }
        if (!args[0].equals(args[1])) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.password-mismatch", "&cPasswords do not match.")));
            return;
        }
        int minLen = plugin.getConfig().getInt("auth.min-password-length", 6);
        if (args[0].length() < minLen) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.password-too-short", "&cPassword must be at least {min} characters.")
                    .replace("{min}", String.valueOf(minLen))));
            return;
        }
        if (plugin.getAuth().isPremium(p)) {
            sender.sendMessage(plugin.colorize("&cPremium accounts do not need to register."));
            return;
        }
        if (plugin.getAuth().isRegistered(p.getUniqueId())) {
            sender.sendMessage(plugin.colorize("&cAn account already exists. Use /login instead."));
            return;
        }
        boolean ok = plugin.getAuth().register(p.getUniqueId(), p.getName(), args[0]);
        if (ok) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.register-success", "&aAccount registered successfully.")));
            AuthListener.AuthSession session = plugin.getListener().getSession(p.getUniqueId());
            if (session != null) session.setAuthenticated(true);
        } else {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.register-failed", "&cRegistration failed.")
                    .replace("{reason}", "database error")));
        }
    }

    private void handleLogin(CommandSender sender, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage(plugin.colorize("&cOnly players can login."));
            return;
        }
        if (plugin.getAuth().isPremium(p)) {
            sender.sendMessage(plugin.colorize("&cPremium accounts do not need to login."));
            return;
        }
        if (args.length < 1) {
            sender.sendMessage(plugin.colorize("&cUsage: /login <password>"));
            return;
        }
        AuthListener.AuthSession session = plugin.getListener().getSession(p.getUniqueId());
        if (session != null && session.isAuthenticated()) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.already-logged-in", "&cYou are already authenticated.")));
            return;
        }
        if (!plugin.getAuth().isRegistered(p.getUniqueId())) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.not-registered", "&cNo account found. Use /register first.")));
            return;
        }
        if (plugin.getAuth().checkPassword(p.getUniqueId(), args[0])) {
            if (session != null) session.setAuthenticated(true);
            plugin.getAuth().recordLogin(p.getUniqueId(), p.getName(), p.getAddress().getAddress().getHostAddress());
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.login-success", "&aLogin successful. Welcome back, {player}!")
                    .replace("{player}", p.getName())));
        } else {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.login-failed", "&cLogin failed: {reason}")
                    .replace("{reason}", "incorrect password")));
        }
    }

    private void handleChangePassword(CommandSender sender, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage(plugin.colorize("&cOnly players can change password."));
            return;
        }
        if (args.length < 2) {
            sender.sendMessage(plugin.colorize("&cUsage: /changepassword <old> <new>"));
            return;
        }
        if (!args[1].equals(args[2])) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.password-mismatch", "&cPasswords do not match.")));
            return;
        }
        boolean ok = plugin.getAuth().changePassword(p.getUniqueId(), args[0], args[1]);
        if (ok) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.password-changed", "&aPassword changed successfully.")));
        } else {
            sender.sendMessage(plugin.colorize("&cIncorrect old password."));
        }
    }

    private void handleStatus(CommandSender sender) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage(plugin.colorize("&cOnly players can check status."));
            return;
        }
        String status = plugin.getAuth().getStatus(p.getUniqueId());
        String key = switch (status) {
            case "premium" -> "messages.status-premium";
            case "cracked" -> "messages.status-cracked";
            default -> "messages.status-unknown";
        };
        sender.sendMessage(plugin.colorize(plugin.getConfig().getString(key, "&e" + status)));
    }

    private void handleReload(CommandSender sender) {
        if (!sender.hasPermission("prime.admin")) {
            sender.sendMessage(plugin.colorize("&cYou need prime.admin."));
            return;
        }
        plugin.reloadConfig();
        plugin.getAuth(); // re-init config if needed
        sender.sendMessage(plugin.colorize("&aPrime configuration reloaded."));
    }

    private void handlePremium(CommandSender sender, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage(plugin.colorize("&cOnly players can use this."));
            return;
        }
        if (!sender.hasPermission("prime.admin")) {
            sender.sendMessage(plugin.colorize("&cYou need prime.admin."));
            return;
        }
        if (args.length < 1) {
            sender.sendMessage(plugin.colorize("&cUsage: /prime premium <player>"));
            return;
        }
        // Placeholder for future premium assignment
        sender.sendMessage(plugin.colorize("&aPremium status for &e" + args[0] + " &ais managed by Mojang account verification."));
    }

    private void handleUnregister(CommandSender sender) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage(plugin.colorize("&cOnly players can unregister."));
            return;
        }
        if (plugin.getAuth().unregister(p.getUniqueId())) {
            sender.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.unregister-success", "&cYour account has been unregistered.")));
        }
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command cmd, String alias, String[] args) {
        if (args.length == 1) {
            String start = args[0].toLowerCase(Locale.ROOT);
            return List.of("register", "login", "changepassword", "status", "reload", "premium", "unregister").stream()
                    .filter(s -> s.startsWith(start)).toList();
        }
        return List.of();
    }
}
