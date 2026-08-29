package dev.mcplugins.bazaar;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.*;
import java.util.stream.Collectors;

public class BazaarGUI implements Listener, InventoryHolder {

    private final BazaarPlugin plugin;
    private final BazaarManager manager;
    private Inventory inventory;
    private int currentPage = 0;
    private List<BazaarManager.BazaarItem> currentList = new ArrayList<>();
    private boolean myListingsOnly = false;
    private UUID viewingPlayer = null;

    public BazaarGUI(BazaarPlugin plugin, BazaarManager manager) {
        this.plugin = plugin;
        this.manager = manager;
    }

    public void open(Player player) {
        this.viewingPlayer = player.getUniqueId();
        this.myListingsOnly = false;
        this.currentPage = 0;
        refreshInventory();
        player.openInventory(inventory);
    }

    public void openMyListings(Player player) {
        this.viewingPlayer = player.getUniqueId();
        this.myListingsOnly = true;
        this.currentPage = 0;
        refreshInventory();
        player.openInventory(inventory);
    }

    public void refreshInventory() {
        int size = plugin.getConfig().getInt("gui.size", 54);
        String title = myListingsOnly ? "§6My Listings" : plugin.getConfig().getString("gui.title", "Bazaar");
        inventory = Bukkit.createInventory(this, size, title);
        
        if (myListingsOnly && viewingPlayer != null) {
            currentList = manager.getPlayerAuctions(viewingPlayer);
        } else {
            currentList = manager.getActiveAuctions();
        }
        
        int requestedPageSize = plugin.getConfig().getInt("gui.page-size", 36);
        int pageSize = Math.min(requestedPageSize, 36);
        int totalPages = (int) Math.ceil((double) currentList.size() / pageSize);
        if (currentPage >= totalPages) currentPage = Math.max(0, totalPages - 1);
        int start = currentPage * pageSize;
        int end = Math.min(start + pageSize, currentList.size());

        fillBorders();

        for (int i = start; i < end; i++) {
            BazaarManager.BazaarItem auction = currentList.get(i);
            ItemStack display = auction.itemStack.clone();
            ItemMeta meta = display.getItemMeta();
            if (meta != null) {
                List<String> lore = meta.getLore();
                if (lore == null) lore = new ArrayList<>();
                lore.add(" ");
                lore.add("§8§m------------------------");
                lore.add("§f§lPRICE");
                lore.add("§a§l$" + String.format("%.2f", auction.price));
                lore.add("§8");
                lore.add("§f§lSELLER");
                String sellerName = Bukkit.getOfflinePlayer(auction.seller).getName();
                if (sellerName == null) sellerName = auction.seller.toString();
                lore.add("§e§l" + sellerName);
                lore.add("§8");
                lore.add("§f§lITEM");
                lore.add("§7" + auction.itemStack.getType().name() + " x" + auction.itemStack.getAmount());
                lore.add("§8§m------------------------");
                meta.setLore(lore);
                display.setItemMeta(meta);
            }
            inventory.setItem(i - start + 9, display);
        }

        if (currentPage > 0) {
            inventory.setItem(45, createItem(Material.ARROW, "§a§l◀ PREVIOUS PAGE"));
        }
        if (myListingsOnly) {
            inventory.setItem(46, createItem(Material.ARROW, "§e§lBACK TO BAZAAR"));
        } else {
            inventory.setItem(46, createItem(Material.CHEST, "§e§lMY LISTINGS"));
        }
        inventory.setItem(48, createItem(Material.COMPOSTER, "§b§lREFRESH"));
        inventory.setItem(50, createItem(Material.BARRIER, "§c§lCLOSE"));
        if (totalPages > 1 && currentPage < totalPages - 1) {
            inventory.setItem(52, createItem(Material.ARROW, "§a§lNEXT PAGE ▶"));
        }
        
        if (totalPages > 0) {
            inventory.setItem(4, createItem(Material.MAP, "§e§lPage §f" + (currentPage + 1) + " §7/ §f" + totalPages));
        }
    }

    private void fillBorders() {
        ItemStack border = createItem(Material.GRAY_STAINED_GLASS_PANE, " ");
        for (int i = 0; i < 9; i++) {
            inventory.setItem(i, border);
        }
        for (int i = 45; i < 54; i++) {
            if (inventory.getItem(i) == null) {
                inventory.setItem(i, border);
            }
        }
    }

    private ItemStack createItem(Material material, String name) {
        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(name);
            item.setItemMeta(meta);
        }
        return item;
    }

    @EventHandler
    public void onInventoryClick(InventoryClickEvent event) {
        if (!(event.getWhoClicked() instanceof Player)) return;
        if (event.getInventory().getHolder() != this) return;
        event.setCancelled(true);

        Player player = (Player) event.getWhoClicked();
        int slot = event.getSlot();

        if (slot == 50) {
            player.closeInventory();
            return;
        }
        if (slot == 48) {
            refreshInventory();
            player.openInventory(inventory);
            return;
        }
        if (slot == 46) {
            if (myListingsOnly) {
                open(player);
            } else {
                openMyListings(player);
            }
            return;
        }
        if (slot == 45 && currentPage > 0) {
            currentPage--;
            refreshInventory();
            player.openInventory(inventory);
            return;
        }
        if (slot == 52) {
            int pageSize = plugin.getConfig().getInt("gui.page-size", 36);
            int totalPages = (int) Math.ceil((double) currentList.size() / pageSize);
            if (currentPage < totalPages - 1) {
                currentPage++;
                refreshInventory();
                player.openInventory(inventory);
            }
            return;
        }

        int pageSize = plugin.getConfig().getInt("gui.page-size", 36);
        int index = currentPage * pageSize + (slot - 9);
        if (index >= 0 && index < currentList.size() && slot >= 9 && slot < 54) {
            BazaarManager.BazaarItem auction = currentList.get(index);
            
            if (auction.seller.equals(player.getUniqueId())) {
                manager.cancelAuction(auction.id);
                ItemStack item = auction.itemStack.clone();
                HashMap<Integer, ItemStack> leftover = player.getInventory().addItem(item);
                if (!leftover.isEmpty()) {
                    player.getWorld().dropItemNaturally(player.getLocation(), leftover.get(0));
                }
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.auction-cancelled", "&aAuction cancelled.")));
                refreshInventory();
                player.openInventory(inventory);
                return;
            }
            
            double price = auction.price;
            double taxPercent = plugin.getConfig().getDouble("settings.tax-percent", 0.0);
            double tax = 0;
            if (taxPercent > 0) {
                tax = Math.floor(price * taxPercent) / 100.0;
            }
            double total = price;
            
            net.milkbowl.vault.economy.EconomyResponse response = plugin.getEconomy().withdrawPlayer(player.getName(), total);
            if (response == null || !response.transactionSuccess()) {
                player.sendMessage(plugin.colorize(plugin.getConfig().getString("messages.no-enough-money", "&cYou don't have enough money.")));
                return;
            }
            
            if (tax > 0) {
                double sellerAmount = price - tax;
                plugin.getEconomy().depositPlayer(Bukkit.getOfflinePlayer(auction.seller), sellerAmount);
            } else {
                plugin.getEconomy().depositPlayer(Bukkit.getOfflinePlayer(auction.seller), price);
            }
            
            ItemStack purchased = auction.itemStack.clone();
            HashMap<Integer, ItemStack> leftover = player.getInventory().addItem(purchased);
            if (!leftover.isEmpty()) {
                player.getWorld().dropItemNaturally(player.getLocation(), leftover.get(0));
            }
            manager.cancelAuction(auction.id);
            
            String msg = plugin.getConfig().getString("messages.purchase-confirm", "&aYou bought &e{item}&a for &e{price}&a!");
            if (tax > 0) {
                msg += " §7(Tax: §c$" + String.format("%.2f", tax) + "§7)";
            }
            player.sendMessage(plugin.colorize(msg
                    .replace("{item}", auction.itemStack.getType().name())
                    .replace("{price}", String.valueOf(price))));
        }
    }

    @Override
    public Inventory getInventory() {
        return inventory;
    }
}
