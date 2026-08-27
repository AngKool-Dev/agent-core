package dev.mcplugins.mobecology;

import org.bukkit.World;

public record RegionKey(String world, int rx, int rz) {

    public static RegionKey of(World world, int chunkX, int chunkZ, int regionChunks) {
        return new RegionKey(world.getName(), Math.floorDiv(chunkX, regionChunks), Math.floorDiv(chunkZ, regionChunks));
    }

    public static RegionKey parse(String serialized) {
        String[] parts = serialized.split("\\|", 3);
        return new RegionKey(parts[0], Integer.parseInt(parts[1]), Integer.parseInt(parts[2]));
    }

    public String serialize() {
        return world + "|" + rx + "|" + rz;
    }
}
