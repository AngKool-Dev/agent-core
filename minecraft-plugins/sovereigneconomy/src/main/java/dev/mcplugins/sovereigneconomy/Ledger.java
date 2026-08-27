package dev.mcplugins.sovereigneconomy;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class Ledger {

    public static final class Account {
        public double wallet;
        public double savings;

        Account(double wallet, double savings) {
            this.wallet = wallet;
            this.savings = savings;
        }
    }

    private final SovereignEconomyPlugin plugin;
    private final Map<UUID, Account> accounts = new HashMap<>();
    private final Object lock = new Object();

    public Ledger(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
    }

    public Account account(UUID id) {
        synchronized (lock) {
            Account a = accounts.get(id);
            if (a == null) {
                a = new Account(plugin.settings().startingBalance, 0);
                accounts.put(id, a);
                plugin.markDirty();
            }
            return a;
        }
    }

    public boolean exists(UUID id) {
        synchronized (lock) {
            return accounts.containsKey(id);
        }
    }

    public boolean has(UUID id, double amount) {
        synchronized (lock) {
            Account a = accounts.get(id);
            return a != null && a.wallet >= amount;
        }
    }

    public double wallet(UUID id) {
        return account(id).wallet;
    }

    public double savings(UUID id) {
        return account(id).savings;
    }

    public void setWallet(UUID id, double value) {
        synchronized (lock) {
            account(id).wallet = Math.max(0, value);
            plugin.markDirty();
        }
    }

    public boolean withdraw(UUID id, double amount) {
        if (amount <= 0) {
            return false;
        }
        synchronized (lock) {
            Account a = account(id);
            if (a.wallet < amount) {
                return false;
            }
            a.wallet -= amount;
            plugin.markDirty();
            return true;
        }
    }

    public void deposit(UUID id, double amount) {
        if (amount <= 0) {
            return;
        }
        synchronized (lock) {
            account(id).wallet += amount;
            plugin.markDirty();
        }
    }

    public boolean pay(UUID from, UUID to, double amount) {
        if (amount <= 0 || from.equals(to)) {
            return false;
        }
        synchronized (lock) {
            Account a = account(from);
            if (a.wallet < amount) {
                return false;
            }
            a.wallet -= amount;
            account(to).wallet += amount;
            plugin.markDirty();
            return true;
        }
    }

    public boolean depositSavings(UUID id, double amount) {
        synchronized (lock) {
            Account a = account(id);
            if (a.wallet < amount || amount <= 0) {
                return false;
            }
            a.wallet -= amount;
            a.savings += amount;
            plugin.markDirty();
            return true;
        }
    }

    public boolean withdrawSavings(UUID id, double amount) {
        synchronized (lock) {
            Account a = account(id);
            if (a.savings < amount || amount <= 0) {
                return false;
            }
            a.savings -= amount;
            a.wallet += amount;
            plugin.markDirty();
            return true;
        }
    }

    public void applyInterestToAll(double factor) {
        synchronized (lock) {
            for (Account a : accounts.values()) {
                if (a.savings > 0) {
                    a.savings *= factor;
                }
            }
            plugin.markDirty();
        }
    }

    public List<Map.Entry<UUID, Double>> topWallets(int n) {
        synchronized (lock) {
            List<Map.Entry<UUID, Double>> rows = new ArrayList<>();
            for (Map.Entry<UUID, Account> e : accounts.entrySet()) {
                rows.add(Map.entry(e.getKey(), e.getValue().wallet + e.getValue().savings));
            }
            rows.sort(Comparator.comparing(Map.Entry<UUID, Double>::getValue).reversed());
            return rows.size() > n ? rows.subList(0, n) : rows;
        }
    }

    public int accountCount() {
        synchronized (lock) {
            return accounts.size();
        }
    }

    public void load(Map<UUID, Account> loaded) {
        synchronized (lock) {
            accounts.clear();
            accounts.putAll(loaded);
        }
    }

    public Map<UUID, Account> snapshot() {
        synchronized (lock) {
            return new HashMap<>(accounts);
        }
    }
}
