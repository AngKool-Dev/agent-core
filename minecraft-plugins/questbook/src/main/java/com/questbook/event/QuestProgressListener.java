package com.questbook.event;

import com.questbook.QuestBookPlugin;
import com.questbook.data.PlayerData;
import com.questbook.data.PlayerDataManager;
import com.questbook.quest.ObjectiveType;
import com.questbook.quest.QuestObjective;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.block.Biome;
import org.bukkit.block.Block;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.inventory.ItemStack;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class QuestProgressListener implements Listener {

    private final QuestBookPlugin plugin;
    private final Map<UUID, Long> lastStructureScan = new HashMap<>();
    private final Map<UUID, Long> lastWalkUpdate = new HashMap<>();
    private static final long SCAN_INTERVAL_MS = 1500L;

    public QuestProgressListener(QuestBookPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onEntityDeath(EntityDeathEvent event) {
        Player player = event.getEntity().getKiller();
        if (player == null) return;

        String mobName = event.getEntity().getType().name();
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        for (String questId : data.getActiveQuestProgress().keySet()) {
            List<QuestObjective> objectives = data.getActiveQuestProgress().get(questId);
            for (QuestObjective obj : objectives) {
                if (obj.getType() == ObjectiveType.KILL_MOB && obj.getTargetId().equals(mobName)) {
                    obj.incrementProgress(1);
                    sendProgressUpdate(player, obj);
                    checkQuestCompletion(data, questId, player);
                }
            }
        }
    }

    @EventHandler
    public void onPlayerCraft(org.bukkit.event.inventory.CraftItemEvent event) {
        if (!(event.getWhoClicked() instanceof Player player)) return;

        Material material = event.getCurrentItem() != null ? event.getCurrentItem().getType() : null;
        if (material == null || material == Material.AIR) return;
        int amount = event.getCurrentItem().getAmount();

        trackCollectedItem(player, material, amount);
    }

    @EventHandler
    public void onInventoryExtract(org.bukkit.event.inventory.InventoryClickEvent event) {
        if (!(event.getWhoClicked() instanceof Player player)) return;
        if (event.getClickedInventory() == null) return;
        if (event.getClickedInventory() instanceof org.bukkit.inventory.PlayerInventory) return;

        var type = event.getClickedInventory().getType();
        if (type != org.bukkit.event.inventory.InventoryType.FURNACE
            && type != org.bukkit.event.inventory.InventoryType.BLAST_FURNACE
            && type != org.bukkit.event.inventory.InventoryType.SMOKER) {
            return;
        }
        if (event.getSlot() != 2 || event.getCurrentItem() == null) return;

        trackCollectedItem(player, event.getCurrentItem().getType(), event.getCurrentItem().getAmount());
    }

    private void trackCollectedItem(Player player, Material material, int amount) {
        if (material == null || material == Material.AIR || amount <= 0) return;
        String itemName = material.name();
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        for (String questId : data.getActiveQuestProgress().keySet()) {
            List<QuestObjective> objectives = data.getActiveQuestProgress().get(questId);
            for (QuestObjective obj : objectives) {
                if (obj.getType() == ObjectiveType.COLLECT_ITEM && !obj.isComplete() && obj.getTargetId().equals(itemName)) {
                    obj.incrementProgress(amount);
                    sendProgressUpdate(player, obj);
                    checkQuestCompletion(data, questId, player);
                }
            }
        }
    }

    @EventHandler
    public void onItemPickup(EntityPickupItemEvent event) {
        if (!(event.getEntity() instanceof Player player)) return;

        Material material = event.getItem().getItemStack().getType();
        String itemName = material.name();
        int amount = event.getItem().getItemStack().getAmount();

        trackCollectedItem(player, material, amount);
    }

    @EventHandler
    public void onPlayerMove(PlayerMoveEvent event) {
        Player player = event.getPlayer();
        Location from = event.getFrom();
        Location to = event.getTo();
        if (to == null) return;

        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());
        if (data.getActiveQuestProgress().isEmpty()) return;

        Biome biome = to.getBlock().getBiome();
        String biomeName = biome.name();
        boolean biomeChanged = !from.getBlock().getBiome().equals(biome);

        long now = System.currentTimeMillis();
        Long lastScan = lastStructureScan.get(player.getUniqueId());
        boolean scanStructures = lastScan == null || now - lastScan > SCAN_INTERVAL_MS;
        boolean sendWalkUpdate = false;
        Long lastWalk = lastWalkUpdate.get(player.getUniqueId());
        if (lastWalk == null || now - lastWalk > 5000L) sendWalkUpdate = true;

        double stepDistance = from.distance(to);
        boolean walking = stepDistance > 0.05 && stepDistance < 100;

        for (String questId : data.getActiveQuestProgress().keySet()) {
            List<QuestObjective> objectives = data.getActiveQuestProgress().get(questId);
            for (QuestObjective obj : objectives) {
                if (obj.isComplete()) continue;

                if (obj.getType() == ObjectiveType.VISIT_BIOME && biomeName.equals(obj.getTargetId()) && biomeChanged) {
                    obj.incrementProgress(1);
                    sendProgressUpdate(player, obj);
                    checkQuestCompletion(data, questId, player);
                }

                if (obj.getType() == ObjectiveType.WALK_DISTANCE && walking) {
                    obj.incrementProgress((int) Math.round(stepDistance));
                    if (sendWalkUpdate) {
                        lastWalkUpdate.put(player.getUniqueId(), now);
                        sendProgressUpdate(player, obj);
                        checkQuestCompletion(data, questId, player);
                    } else {
                        checkQuestCompletion(data, questId, player);
                    }
                }

                if (obj.getType() == ObjectiveType.FIND_STRUCTURE && scanStructures) {
                    checkStructureObjective(player, data, questId, obj);
                }
            }
        }

        if (scanStructures) lastStructureScan.put(player.getUniqueId(), now);
    }

    private void checkStructureObjective(Player player, PlayerData data, String questId, QuestObjective obj) {
        int cx = player.getLocation().getChunk().getX();
        int cz = player.getLocation().getChunk().getZ();
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                try {
                    var structures = player.getWorld().getChunkAt(cx + dx, cz + dz).getStructures();
                    for (var generated : structures) {
                        if (generated.getBoundingBox().contains(player.getLocation().toVector())) {
                            String key = generated.getStructure().getKey().getKey();
                            if (structureMatches(key, obj.getTargetId())) {
                                if (!obj.isComplete()) {
                                    obj.incrementProgress(1);
                                    sendProgressUpdate(player, obj);
                                    checkQuestCompletion(data, questId, player);
                                }
                                return;
                            }
                        }
                    }
                } catch (Exception ignored) {
                }
            }
        }
    }

    private boolean structureMatches(String structureKey, String target) {
        String normalizedTarget = target.toLowerCase().replace("_", "").replace("structure", "");
        String normalizedKey = structureKey.toLowerCase().replace("_", "");
        if (normalizedKey.equals(normalizedTarget)) return true;
        if (normalizedTarget.equals("village") && normalizedKey.startsWith("village")) return true;
        if (normalizedTarget.equals("mineshaft") && normalizedKey.startsWith("mineshaft")) return true;
        if (normalizedTarget.equals("ruinedportal") && normalizedKey.startsWith("ruinedportal")) return true;
        return false;
    }

    @EventHandler
    public void onBlockPlace(BlockPlaceEvent event) {
        Player player = event.getPlayer();
        String blockName = event.getBlockPlaced().getType().name();
        PlayerData data = plugin.getPlayerDataManager().getPlayerData(player.getUniqueId());

        for (String questId : data.getActiveQuestProgress().keySet()) {
            List<QuestObjective> objectives = data.getActiveQuestProgress().get(questId);
            for (QuestObjective obj : objectives) {
                if (obj.getType() == ObjectiveType.PLACE_BLOCK && obj.getTargetId().equals(blockName)) {
                    obj.incrementProgress(1);
                    sendProgressUpdate(player, obj);
                    checkQuestCompletion(data, questId, player);
                }
            }
        }
    }

    private void sendProgressUpdate(Player player, QuestObjective obj) {
        int completed = obj.getAmountCompleted();
        int required = obj.getAmountRequired();
        player.sendMessage(org.bukkit.ChatColor.GREEN + "Progress: " + obj.getDescription() + " " +
            org.bukkit.ChatColor.WHITE + "(" + completed + "/" + required + ")");
    }

    private void checkQuestCompletion(PlayerData data, String questId, Player player) {
        if (data.canComplete(questId)) {
            com.questbook.quest.Quest quest = plugin.getQuestManager().getQuest(questId);
            if (quest == null) return;

            player.sendMessage(org.bukkit.ChatColor.GOLD + "Quest Complete: " + quest.getTitle() + "!");
            plugin.getPlayerDataManager().giveRewards(player, quest);
            data.completeQuest(questId);
            plugin.getRankManager().onQuestCompleted(player, data);
        } else {
            plugin.getPlayerDataManager().saveData(player.getUniqueId());
        }
    }
}