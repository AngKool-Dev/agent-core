package dev.mcplugins.echorealms;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public final class BuilderSite {

    public long count;
    public long sumX;
    public long sumZ;
    public int minY = Integer.MAX_VALUE;
    public int maxY = Integer.MIN_VALUE;
    public long lastActivity;
    public final Map<UUID, Long> attunedAt = new HashMap<>();

    public void record(int x, int y, int z, long now) {
        count++;
        sumX += x;
        sumZ += z;
        minY = Math.min(minY, y);
        maxY = Math.max(maxY, y);
        lastActivity = now;
    }

    public double centroidX() {
        return count == 0 ? 0 : (double) sumX / count;
    }

    public double centroidZ() {
        return count == 0 ? 0 : (double) sumZ / count;
    }

    public double radius() {
        double r = 6.0 + Math.sqrt(Math.max(0, count)) * 1.1;
        return Math.max(12, Math.min(48, r));
    }
}
