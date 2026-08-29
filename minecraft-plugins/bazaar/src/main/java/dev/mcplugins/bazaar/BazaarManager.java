package dev.mcplugins.bazaar;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.File;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

public class BazaarManager {

    private final BazaarPlugin plugin;
    private final File dataFile;
    private YamlConfiguration config;
    private final Map<String, BazaarItem> auctions = new ConcurrentHashMap<>();

    public BazaarManager(BazaarPlugin plugin) {
        this.plugin = plugin;
        this.dataFile = new File(plugin.getDataFolder(), "auctions.yml");
        load();
    }

    public void load() {
        if (!dataFile.exists()) {
            plugin.saveResource("auctions.yml", false);
        }
        config = YamlConfiguration.loadConfiguration(dataFile);
        auctions.clear();
        ConfigurationSection section = config.getConfigurationSection("auctions");
        if (section != null) {
            for (String key : section.getKeys(false)) {
                BazaarItem auction = new BazaarItem();
                auction.id = key;
                auction.seller = UUID.fromString(section.getString(key + ".seller"));
                auction.itemStack = section.getItemStack(key + ".item");
                auction.price = section.getDouble(key + ".price");
                auction.created = section.getLong(key + ".created");
                auction.expires = section.getLong(key + ".expires");
                auction.claimed = section.getBoolean(key + ".claimed", false);
                auctions.put(key, auction);
            }
        }
    }

    public void save() {
        config.set("auctions", null);
        for (BazaarItem auction : auctions.values()) {
            String path = "auctions." + auction.id;
            config.set(path + ".seller", auction.seller.toString());
            config.set(path + ".item", auction.itemStack);
            config.set(path + ".price", auction.price);
            config.set(path + ".created", auction.created);
            config.set(path + ".expires", auction.expires);
            config.set(path + ".claimed", auction.claimed);
        }
        try {
            config.save(dataFile);
        } catch (IOException e) {
            plugin.getLogger().severe("Could not save auctions.yml: " + e.getMessage());
        }
    }

    public BazaarItem createAuction(UUID seller, org.bukkit.inventory.ItemStack itemStack, double price, long durationSeconds) {
        String id = UUID.randomUUID().toString().substring(0, 8);
        BazaarItem auction = new BazaarItem();
        auction.id = id;
        auction.seller = seller;
        auction.itemStack = itemStack;
        auction.price = price;
        auction.created = System.currentTimeMillis();
        auction.expires = System.currentTimeMillis() + (durationSeconds * 1000L);
        auction.claimed = false;
        auctions.put(id, auction);
        save();
        return auction;
    }

    public Optional<BazaarItem> getAuction(String id) {
        return Optional.ofNullable(auctions.get(id));
    }

    public void cancelAuction(String id) {
        auctions.remove(id);
        save();
    }

    public List<BazaarItem> getActiveAuctions() {
        long now = System.currentTimeMillis();
        List<BazaarItem> active = new ArrayList<>();
        for (BazaarItem auction : auctions.values()) {
            if (!auction.claimed && auction.expires > now) {
                active.add(auction);
            }
        }
        return active;
    }

    public List<BazaarItem> getPlayerAuctions(UUID player) {
        List<BazaarItem> list = new ArrayList<>();
        for (BazaarItem auction : auctions.values()) {
            if (auction.seller.equals(player)) {
                list.add(auction);
            }
        }
        return list;
    }

    public void expireOldAuctions() {
        long now = System.currentTimeMillis();
        Iterator<BazaarItem> it = auctions.values().iterator();
        while (it.hasNext()) {
            BazaarItem auction = it.next();
            if (!auction.claimed && auction.expires <= now) {
                it.remove();
            }
        }
        save();
    }

    public static class BazaarItem {
        public String id;
        public UUID seller;
        public org.bukkit.inventory.ItemStack itemStack;
        public double price;
        public long created;
        public long expires;
        public boolean claimed;
    }
}
