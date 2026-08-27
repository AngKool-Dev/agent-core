package dev.mcplugins.chunksovereignty;

import org.bukkit.Bukkit;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

public final class DomainEngine {

    public record Expansion(UUID owner, ChunkIndex.Claim from, ChunkIndex.Claim to,
                            boolean blockedByRival, UUID rival) {
    }

    private final SovereigntyPlugin plugin;

    public DomainEngine(SovereigntyPlugin plugin) {
        this.plugin = plugin;
    }

    /** Hourly pass: pay upkeep, shed unpaid chunks, expand into neighbours. */
    public List<String> runPass() {
        List<String> log = new ArrayList<>();
        ChunkIndex idx = plugin.index();
        Settings s = plugin.settings();

        for (Map.Entry<UUID, Double> e : idx.influenceSnapshot().entrySet()) {
            UUID owner = e.getKey();
            int chunks = idx.countOwned(owner);
            if (chunks == 0) {
                continue;
            }
            double upkeep = chunks * s.upkeepPerChunkHour;
            idx.addInfluence(owner, -upkeep);
            if (idx.influence(owner) < 0) {
                idx.setInfluence(owner, 0);
                ChunkIndex.Claim evicted = idx.newestOf(owner);
                if (evicted != null) {
                    idx.remove(evicted);
                    log.add(name(owner) + " failed upkeep - released "
                            + evicted.x() + "," + evicted.z() + " (" + evicted.world() + ")");
                }
            }
        }

        for (Map.Entry<UUID, Double> e : idx.influenceSnapshot().entrySet()) {
            UUID owner = e.getKey();
            int chunks = idx.countOwned(owner);
            if (chunks == 0 || chunks >= s.maxChunks) {
                continue;
            }
            while (chunks < s.maxChunks
                    && idx.influence(owner) >= s.costPerChunk) {
                Expansion exp = findExpansion(owner);
                if (exp == null) {
                    break;
                }
                if (!exp.blockedByRival()) {
                    idx.spendInfluence(owner, s.costPerChunk);
                    idx.putClaim(exp.to(), owner, System.currentTimeMillis());
                    chunks++;
                    log.add(name(owner) + " expanded to " + exp.to().x() + ","
                            + exp.to().z() + " (" + exp.to().world() + ") for "
                            + String.format("%.0f", s.costPerChunk) + " influence");
                } else {
                    tensionUp(exp.owner(), exp.rival());
                    break;
                }
            }
        }
        plugin.markDirty();
        return log;
    }

    private Expansion findExpansion(UUID owner) {
        ChunkIndex idx = plugin.index();
        List<ChunkIndex.Claim> mine = idx.chunksOf(owner);
        if (mine.isEmpty()) {
            return null;
        }
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        ChunkIndex.Claim start = mine.get(rnd.nextInt(mine.size()));
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int[] d : dirs) {
            ChunkIndex.Claim target = new ChunkIndex.Claim(start.world(),
                    start.x() + d[0], start.z() + d[1]);
            if (idx.isClaimed(target)) {
                continue;
            }
            UUID rival = rivalAdjacent(target, owner);
            return new Expansion(owner, start, target, rival != null, rival);
        }
        return null;
    }

    private UUID rivalAdjacent(ChunkIndex.Claim c, UUID self) {
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int[] d : dirs) {
            UUID other = plugin.index().ownerAt(new ChunkIndex.Claim(
                    c.world(), c.x() + d[0], c.z() + d[1]));
            if (other != null && !other.equals(self)) {
                return other;
            }
        }
        return null;
    }

    private final Map<Long, Double> tension = new HashMap<>();

    private void tensionUp(UUID a, UUID b) {
        long pair = a.getLeastSignificantBits() ^ b.getMostSignificantBits();
        tension.merge(pair, 10.0, Double::sum);
    }

    public double tensionBetween(UUID a, UUID b) {
        return tension.getOrDefault(a.getLeastSignificantBits() ^ b.getMostSignificantBits(), 0.0);
    }

    public List<Map.Entry<Long, Double>> topTensions(int n) {
        List<Map.Entry<Long, Double>> rows = new ArrayList<>(tension.entrySet());
        rows.sort((x, y) -> Double.compare(y.getValue(), x.getValue()));
        return rows.size() > n ? rows.subList(0, n) : rows;
    }

    public void decayTension(double factor) {
        tension.replaceAll((k, v) -> v * factor);
    }

    public int cropBonusFor(ChunkIndex.Claim c) {
        UUID owner = plugin.index().ownerAt(c);
        if (owner == null) {
            return 0;
        }
        return plugin.settings().tierFor(plugin.index().countOwned(owner)).cropBonus();
    }

    private String name(UUID id) {
        String n = Bukkit.getOfflinePlayer(id).getName();
        return n == null ? id.toString().substring(0, 8) : n;
    }
}
