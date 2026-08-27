package dev.mcplugins.sovereigneconomy;

import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class MarketEngine {

    private final SovereignEconomyPlugin plugin;

    public MarketEngine(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
    }

    public Commodity commodity(String id) {
        return plugin.settings().commodities.get(id.toLowerCase());
    }

    public Collection<Commodity> commodities() {
        return plugin.settings().commodities.values();
    }

    public double cpi() {
        double weighted = 0;
        double weights = 0;
        for (Commodity c : commodities()) {
            weighted += c.mult * c.depth;
            weights += c.depth;
        }
        return weights == 0 ? 1.0 : weighted / weights;
    }

    public double inflationSinceReference() {
        double now = cpi();
        double ref = referenceCpi();
        return ref <= 0 ? 0 : now / ref - 1.0;
    }

    public double referenceCpi() {
        double weighted = 0;
        double weights = 0;
        for (Commodity c : commodities()) {
            weighted += c.referenceMult * c.depth;
            weights += c.depth;
        }
        return weights == 0 ? 1.0 : weighted / weights;
    }

    public void revertAll() {
        double f = plugin.settings().reversionPerHour;
        for (Commodity c : commodities()) {
            c.revert(f);
        }
        plugin.markDirty();
    }

    public void snapshotReference() {
        for (Commodity c : commodities()) {
            c.referenceMult = c.mult;
        }
        plugin.markDirty();
    }

    public Result quoteBuy(Commodity c, int qty) {
        double cost = Math.ceil(c.buyPrice(plugin.settings().spread) * qty);
        return new Result(cost, c.sellPrice(plugin.settings().spread));
    }

    public record Result(double costOrProceeds, double unitSell) {
    }

    public String buy(Player player, Commodity c, int qty) {
        if (qty <= 0 || qty > 2304) {
            return "Quantity must be between 1 and 2304.";
        }
        Material mat = Material.matchMaterial(c.id);
        if (mat == null || !mat.isItem()) {
            return "That commodity is not tradeable as an item.";
        }
        Settings s = plugin.settings();
        double cost = Math.ceil(c.buyPrice(s.spread) * qty);
        if (!plugin.ledger().withdraw(player.getUniqueId(), cost)) {
            return "Insufficient funds. Cost is " + Text.money(cost, s) + ".";
        }
        HashMap<Integer, ItemStack> leftover = player.getInventory()
                .addItem(new ItemStack(mat, qty));
        if (!leftover.isEmpty()) {
            int dropped = leftover.values().stream()
                    .mapToInt(ItemStack::getAmount).sum();
            player.getWorld().dropItemNaturally(player.getLocation(),
                    new ItemStack(mat, dropped));
            if (dropped == qty) {
                plugin.ledger().deposit(player.getUniqueId(), cost);
                c.applyTrade(0, true);
                return "Inventory full - purchase refunded.";
            }
            int kept = qty - dropped;
            double refund = Math.ceil(c.buyPrice(s.spread) * dropped);
            c.applyTrade(kept, true);
            return "Bought " + kept + ", dropped " + dropped
                    + " at your feet. Paid " + Text.money(cost - refund, s) + ".";
        }
        c.applyTrade(qty, true);
        return "Bought " + Text.qty(qty) + " " + Text.title(c.id)
                + " for " + Text.money(cost, s) + ". New price: "
                + Text.money(c.buyPrice(s.spread), s) + ".";
    }

    public String sell(Player player, Commodity c, int qty) {
        if (qty <= 0 || qty > 2304) {
            return "Quantity must be between 1 and 2304.";
        }
        Material mat = Material.matchMaterial(c.id);
        if (mat == null || !mat.isItem()) {
            return "That commodity is not tradeable as an item.";
        }
        Settings s = plugin.settings();
        ItemStack stack = new ItemStack(mat, qty);
        HashMap<Integer, ItemStack> notRemoved = player.getInventory().removeItem(stack);
        int sold = qty - notRemoved.values().stream()
                .mapToInt(ItemStack::getAmount).sum();
        if (sold <= 0) {
            return "You have no " + Text.title(c.id) + " to sell.";
        }
        double proceeds = Math.floor(c.sellPrice(s.spread) * sold);
        plugin.ledger().deposit(player.getUniqueId(), proceeds);
        c.applyTrade(sold, false);
        return "Sold " + Text.qty(sold) + " " + Text.title(c.id)
                + " for " + Text.money(proceeds, s) + ". New sell price: "
                + Text.money(c.sellPrice(s.spread), s) + ".";
    }

    public List<String> browsePage(int page, int perPage) {
        List<Commodity> list = new ArrayList<>(commodities());
        list.sort((a, b) -> a.id.compareTo(b.id));
        List<String> out = new ArrayList<>();
        int pages = Math.max(1, (list.size() + perPage - 1) / perPage);
        page = Math.max(1, Math.min(pages, page));
        Settings s = plugin.settings();
        out.add("Market page " + page + "/" + pages
                + " - CPI " + String.format("%.3f", cpi())
                + " (" + Text.pct(inflationSinceReference()) + ")");
        for (int i = (page - 1) * perPage; i < list.size() && i < page * perPage; i++) {
            Commodity c = list.get(i);
            String trend = c.mult > c.referenceMult * 1.02 ? "+" :
                    c.mult < c.referenceMult * 0.98 ? "-" : "=";
            out.add(String.format(" %-16s buy %9s  sell %9s  [%s]",
                    Text.title(c.id),
                    Text.money(c.buyPrice(s.spread), s),
                    Text.money(c.sellPrice(s.spread), s),
                    trend));
        }
        out.add("Use /market info <item> for details.");
        return out;
    }

    public List<String> info(Commodity c) {
        Settings s = plugin.settings();
        List<String> out = new ArrayList<>();
        double change = c.referenceMult > 0 ? c.mult / c.referenceMult - 1 : 0;
        out.add(Text.title(c.id) + " - base " + Text.money(c.base, s));
        out.add(" Buy:  " + Text.money(c.buyPrice(s.spread), s));
        out.add(" Sell: " + Text.money(c.sellPrice(s.spread), s));
        out.add(" Index vs baseline: " + String.format("%.1f%%", c.mult * 100)
                + "  (day change " + Text.pct(change) + ")");
        out.add(" Liquidity depth: " + Text.qty((int) c.depth));
        return out;
    }

    public Map<String, Double> multSnapshot() {
        Map<String, Double> m = new HashMap<>();
        for (Commodity c : commodities()) {
            m.put(c.id, c.mult);
        }
        return m;
    }

    public void loadMults(Map<String, Double> mults) {
        for (Commodity c : commodities()) {
            Double v = mults.get(c.id);
            if (v != null && v > 0) {
                c.mult = Math.max(0.20, Math.min(5.0, v));
                c.referenceMult = c.mult;
            }
        }
    }
}
