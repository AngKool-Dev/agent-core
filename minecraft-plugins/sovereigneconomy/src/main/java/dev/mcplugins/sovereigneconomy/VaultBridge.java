package dev.mcplugins.sovereigneconomy;

import net.milkbowl.vault.economy.Economy;
import net.milkbowl.vault.economy.EconomyResponse;
import org.bukkit.OfflinePlayer;
import org.bukkit.Bukkit;

import java.util.List;
import java.util.UUID;

public final class VaultBridge implements Economy {

    private final SovereignEconomyPlugin plugin;

    public VaultBridge(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
    }

    private UUID id(String name) {
        OfflinePlayer op = Bukkit.getOfflinePlayer(name);
        return op.getUniqueId();
    }

    public boolean isEnabled() {
        return plugin.isEnabled();
    }

    public String getName() {
        return "SovereignEconomy";
    }

    public boolean hasBankSupport() {
        return false;
    }

    public int fractionalDigits() {
        return 2;
    }

    public String format(double amount) {
        return Text.money(amount, plugin.settings());
    }

    public String currencyNamePlural() {
        return plugin.settings().currencyNamePlural;
    }

    public String currencyNameSingular() {
        return plugin.settings().currencyNameSingular;
    }

    public double getBalance(String player) {
        return plugin.ledger().wallet(id(player));
    }

    public double getBalance(OfflinePlayer player) {
        return plugin.ledger().wallet(player.getUniqueId());
    }

    public double getBalance(String player, String world) {
        return getBalance(player);
    }

    public double getBalance(OfflinePlayer player, String world) {
        return getBalance(player);
    }

    public boolean has(String player, double amount) {
        return plugin.ledger().has(id(player), amount);
    }

    public boolean has(OfflinePlayer player, double amount) {
        return plugin.ledger().has(player.getUniqueId(), amount);
    }

    public boolean has(String player, String world, double amount) {
        return has(player, amount);
    }

    public boolean has(OfflinePlayer player, String world, double amount) {
        return has(player, amount);
    }

    public EconomyResponse withdrawPlayer(String player, double amount) {
        return plugin.ledger().withdraw(id(player), amount)
                ? ok(amount, getBalance(player))
                : fail(amount, "Insufficient funds");
    }

    public EconomyResponse withdrawPlayer(OfflinePlayer player, double amount) {
        return plugin.ledger().withdraw(player.getUniqueId(), amount)
                ? ok(amount, getBalance(player))
                : fail(amount, "Insufficient funds");
    }

    public EconomyResponse withdrawPlayer(String player, String world, double amount) {
        return withdrawPlayer(player, amount);
    }

    public EconomyResponse withdrawPlayer(OfflinePlayer player, String world, double amount) {
        return withdrawPlayer(player, amount);
    }

    public EconomyResponse depositPlayer(String player, double amount) {
        plugin.ledger().deposit(id(player), amount);
        return ok(amount, getBalance(player));
    }

    public EconomyResponse depositPlayer(OfflinePlayer player, double amount) {
        plugin.ledger().deposit(player.getUniqueId(), amount);
        return ok(amount, getBalance(player));
    }

    public EconomyResponse depositPlayer(String player, String world, double amount) {
        return depositPlayer(player, amount);
    }

    public EconomyResponse depositPlayer(OfflinePlayer player, String world, double amount) {
        return depositPlayer(player, amount);
    }

    public boolean createPlayerAccount(String player) {
        plugin.ledger().account(id(player));
        return true;
    }

    public boolean createPlayerAccount(OfflinePlayer player) {
        plugin.ledger().account(player.getUniqueId());
        return true;
    }

    public boolean createPlayerAccount(String player, String world) {
        return createPlayerAccount(player);
    }

    public boolean createPlayerAccount(OfflinePlayer player, String world) {
        return createPlayerAccount(player);
    }

    public boolean hasAccount(String player) {
        return plugin.ledger().exists(id(player));
    }

    public boolean hasAccount(OfflinePlayer player) {
        return plugin.ledger().exists(player.getUniqueId());
    }

    public boolean hasAccount(String player, String world) {
        return hasAccount(player);
    }

    public boolean hasAccount(OfflinePlayer player, String world) {
        return hasAccount(player);
    }

    private EconomyResponse notImplemented() {
        return new EconomyResponse(0, 0,
                EconomyResponse.ResponseType.NOT_IMPLEMENTED, "Banks are not supported");
    }

    private EconomyResponse ok(double amount, double balance) {
        return new EconomyResponse(amount, balance,
                EconomyResponse.ResponseType.SUCCESS, null);
    }

    private EconomyResponse fail(double amount, String msg) {
        return new EconomyResponse(amount, 0,
                EconomyResponse.ResponseType.FAILURE, msg);
    }

    public EconomyResponse createBank(String name, String player) {
        return notImplemented();
    }

    public EconomyResponse createBank(String name, OfflinePlayer player) {
        return notImplemented();
    }

    public EconomyResponse deleteBank(String name) {
        return notImplemented();
    }

    public EconomyResponse bankBalance(String name) {
        return notImplemented();
    }

    public EconomyResponse bankHas(String name, double amount) {
        return notImplemented();
    }

    public EconomyResponse bankWithdraw(String name, double amount) {
        return notImplemented();
    }

    public EconomyResponse bankDeposit(String name, double amount) {
        return notImplemented();
    }

    public EconomyResponse isBankOwner(String name, String playerName) {
        return notImplemented();
    }

    public EconomyResponse isBankOwner(String name, OfflinePlayer player) {
        return notImplemented();
    }

    public EconomyResponse isBankMember(String name, String playerName) {
        return notImplemented();
    }

    public EconomyResponse isBankMember(String name, OfflinePlayer player) {
        return notImplemented();
    }

    public List<String> getBanks() {
        return List.of();
    }
}
