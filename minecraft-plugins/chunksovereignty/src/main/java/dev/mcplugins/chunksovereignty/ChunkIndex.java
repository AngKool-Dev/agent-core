package dev.mcplugins.chunksovereignty;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public final class ChunkIndex {

    public record Claim(String world, int x, int z) {
        public String id() {
            return world + "|" + x + "|" + z;
        }

        public static Claim parse(String id) {
            String[] p = id.split("\\|", 3);
            return new Claim(p[0], Integer.parseInt(p[1]), Integer.parseInt(p[2]));
        }
    }

    public static final class ClaimData {
        public UUID owner;
        public long claimedAt;

        public ClaimData(UUID owner, long claimedAt) {
            this.owner = owner;
            this.claimedAt = claimedAt;
        }
    }

    private final Map<String, ClaimData> claims = new ConcurrentHashMap<>();
    private final Map<UUID, Double> influence = new ConcurrentHashMap<>();
    private final Map<UUID, Set<UUID>> trusted = new HashMap<>();
    private final Object lock = new Object();

    public ClaimData claimAt(Claim c) {
        return claims.get(c.id());
    }

    public UUID ownerAt(Claim c) {
        ClaimData d = claims.get(c.id());
        return d == null ? null : d.owner;
    }

    public boolean isClaimed(Claim c) {
        return claims.containsKey(c.id());
    }

    public void putClaim(Claim c, UUID owner, long at) {
        claims.put(c.id(), new ClaimData(owner, at));
    }

    public boolean remove(Claim c) {
        return claims.remove(c.id()) != null;
    }

    public int countOwned(UUID owner) {
        int n = 0;
        for (ClaimData d : claims.values()) {
            if (d.owner.equals(owner)) {
                n++;
            }
        }
        return n;
    }

    /** Newest-claimed chunk of the owner's domain, for upkeep eviction. */
    public Claim newestOf(UUID owner) {
        Claim best = null;
        long bestAt = Long.MIN_VALUE;
        for (Map.Entry<String, ClaimData> e : claims.entrySet()) {
            if (e.getValue().owner.equals(owner) && e.getValue().claimedAt > bestAt) {
                bestAt = e.getValue().claimedAt;
                best = Claim.parse(e.getKey());
            }
        }
        return best;
    }

    public java.util.List<Claim> chunksOf(UUID owner) {
        java.util.List<Claim> out = new java.util.ArrayList<>();
        for (Map.Entry<String, ClaimData> e : claims.entrySet()) {
            if (e.getValue().owner.equals(owner)) {
                out.add(Claim.parse(e.getKey()));
            }
        }
        return out;
    }

    public double influence(UUID owner) {
        return influence.getOrDefault(owner, 0.0);
    }

    public void addInfluence(UUID owner, double amount) {
        if (amount == 0) {
            return;
        }
        synchronized (lock) {
            influence.merge(owner, amount, Double::sum);
        }
    }

    public boolean spendInfluence(UUID owner, double amount) {
        synchronized (lock) {
            double cur = influence.getOrDefault(owner, 0.0);
            if (cur < amount) {
                return false;
            }
            influence.put(owner, cur - amount);
            return true;
        }
    }

    public void setInfluence(UUID owner, double value) {
        influence.put(owner, Math.max(0, value));
    }

    public Map<UUID, Double> influenceSnapshot() {
        synchronized (lock) {
            return new HashMap<>(influence);
        }
    }

    public void loadInfluence(Map<UUID, Double> loaded) {
        synchronized (lock) {
            influence.clear();
            influence.putAll(loaded);
        }
    }

    public void trust(UUID owner, UUID guest) {
        trusted.computeIfAbsent(owner, k -> new HashSet<>()).add(guest);
    }

    public void untrust(UUID owner, UUID guest) {
        Set<UUID> set = trusted.get(owner);
        if (set != null) {
            set.remove(guest);
        }
    }

    public boolean isTrusted(UUID owner, UUID guest) {
        Set<UUID> set = trusted.get(owner);
        return set != null && set.contains(guest);
    }

    public Set<UUID> trustsOf(UUID owner) {
        return trusted.getOrDefault(owner, Set.of());
    }

    public void loadTrusts(Map<UUID, Set<UUID>> loaded) {
        trusted.putAll(loaded);
    }

    public Map<UUID, Set<UUID>> trustSnapshot() {
        Map<UUID, Set<UUID>> out = new HashMap<>();
        for (Map.Entry<UUID, Set<UUID>> e : trusted.entrySet()) {
            out.put(e.getKey(), new HashSet<>(e.getValue()));
        }
        return out;
    }

    public Iterable<Map.Entry<String, ClaimData>> allClaims() {
        return claims.entrySet();
    }

    public int totalClaims() {
        return claims.size();
    }
}
