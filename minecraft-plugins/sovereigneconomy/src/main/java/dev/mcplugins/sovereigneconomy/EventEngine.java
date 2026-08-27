package dev.mcplugins.sovereigneconomy;

import org.bukkit.Bukkit;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

public final class EventEngine {

    private record EventKind(String label, double weight) {
    }

    private static final List<EventKind> KINDS = List.of(
            new EventKind("BOOM", 0.30),
            new EventKind("RECESSION", 0.25),
            new EventKind("SHORTAGE", 0.25),
            new EventKind("GLUT", 0.20));

    private final SovereignEconomyPlugin plugin;

    public EventEngine(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
    }

    public void fireRandom() {
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        List<Commodity> pool = new ArrayList<>(plugin.market().commodities());
        if (pool.isEmpty()) {
            return;
        }
        double roll = rnd.nextDouble();
        double acc = 0;
        EventKind kind = KINDS.get(KINDS.size() - 1);
        for (EventKind k : KINDS) {
            acc += k.weight();
            if (roll <= acc) {
                kind = k;
                break;
            }
        }
        switch (kind.label()) {
            case "BOOM" -> {
                shufflePick(pool, 2 + rnd.nextInt(5)).forEach(c ->
                        c.mult *= 1.10 + rnd.nextDouble() * 0.25);
                broadcast("A trade BOOM sweeps the market - several goods are in high demand. Sell while it lasts!");
            }
            case "RECESSION" -> {
                shufflePick(pool, pool.size() / 2 + 1).forEach(c ->
                        c.mult *= 0.85 + rnd.nextDouble() * 0.08);
                broadcast("Recession hits the realm. Prices sag across half the market - buyers hold the advantage.");
            }
            case "SHORTAGE" -> {
                Commodity c = pool.get(rnd.nextInt(pool.size()));
                c.mult *= 1.5 + rnd.nextDouble() * 0.6;
                broadcast("SHORTAGE! " + Text.title(c.id) + " prices spike as supply dries up.");
            }
            default -> {
                Commodity c = pool.get(rnd.nextInt(pool.size()));
                c.mult *= 0.55 + rnd.nextDouble() * 0.15;
                broadcast("GLUT! Markets flood with cheap " + Text.title(c.id) + ". A buying opportunity?");
            }
        }
        plugin.markDirty();
    }

    private List<Commodity> shufflePick(List<Commodity> pool, int n) {
        List<Commodity> copy = new ArrayList<>(pool);
        java.util.Collections.shuffle(copy);
        return copy.subList(0, Math.min(n, copy.size()));
    }

    private void broadcast(String msg) {
        Bukkit.broadcast(net.kyori.adventure.text.Component.text(msg,
                net.kyori.adventure.text.format.NamedTextColor.GOLD));
    }
}
