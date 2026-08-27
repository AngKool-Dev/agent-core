package dev.mcplugins.echorealms;

import org.bukkit.World;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public final class EchoRegion {

    public final String world;
    public final int rx;
    public final int rz;
    public final Map<UUID, BuilderSite> sites = new HashMap<>();

    public EchoRegion(String world, int rx, int rz) {
        this.world = world;
        this.rx = rx;
        this.rz = rz;
    }

    public static EchoRegion of(World w, int chunkX, int chunkZ, int regionChunks) {
        return new EchoRegion(w.getName(),
                Math.floorDiv(chunkX, regionChunks), Math.floorDiv(chunkZ, regionChunks));
    }

    public BuilderSite site(UUID builder) {
        return sites.computeIfAbsent(builder, k -> new BuilderSite());
    }

    public String key(UUID builder) {
        return world + "|" + rx + "|" + rz + "|" + builder;
    }
}
