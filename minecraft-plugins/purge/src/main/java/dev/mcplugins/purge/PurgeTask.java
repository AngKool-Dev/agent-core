package dev.mcplugins.purge;

import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntitySpawnEvent;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.Material;

import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

public class PurgeTask extends BukkitRunnable implements Listener {

    private final PurgePlugin plugin;
    private final Random random = new Random();
    private long ticksElapsed = 0;

    public PurgeTask(PurgePlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public void run() {
        PurgeConfig config = plugin.settings();
        if (!config.isEnabled()) return;

        ticksElapsed++;
        long intervalTicks = config.getIntervalTicks();
        long warnBeforeTicks = config.getWarnBeforeTicks();

        if (warnBeforeTicks > 0 && ticksElapsed == intervalTicks - warnBeforeTicks) {
            int seconds = (int) (warnBeforeTicks / 20);
            Bukkit.broadcastMessage(PurgePlugin.colorize(
                    config.messages.warn.replace("{seconds}", String.valueOf(seconds))));
        }

        if (ticksElapsed >= intervalTicks) {
            ticksElapsed = 0;
            PurgePlugin.PurgeResult result = clearNow();

            if (config.broadcastSummary) {
                Bukkit.broadcastMessage(PurgePlugin.colorize(
                        config.messages.summary
                                .replace("{items}", String.valueOf(result.itemsCleared))
                                .replace("{hostiles}", String.valueOf(result.hostilesCleared))
                                .replace("{passives}", String.valueOf(result.passivesCleared))));
            }
        }
    }

    public PurgePlugin.PurgeResult clearNow() {
        PurgeConfig config = plugin.settings();
        int itemsCleared = 0;
        int hostilesCleared = 0;
        int passivesCleared = 0;
        Set<String> protectedTypes = new HashSet<>(config.clearing.mobs.protectedEntityTypes);

        if (config.clearing.items) {
            for (World world : Bukkit.getWorlds()) {
                if (config.clearing.mobs.disabledWorlds.contains(world.getName())) continue;
                for (Item item : world.getEntitiesByClass(Item.class)) {
                    if (!item.isDead() && shouldRemove(item, config)) {
                        item.remove();
                        itemsCleared++;
                    }
                }
                if (config.clearing.mobs.clearFallingBlocks) {
                    for (FallingBlock fb : world.getEntitiesByClass(FallingBlock.class)) {
                        if (!fb.isDead()) {
                            fb.remove();
                            itemsCleared++;
                        }
                    }
                }
            }
        }

        if (config.clearing.mobs.enabled) {
            for (World world : Bukkit.getWorlds()) {
                if (config.clearing.mobs.disabledWorlds.contains(world.getName())) continue;
                List<LivingEntity> hostiles = new ArrayList<>();
                List<LivingEntity> passives = new ArrayList<>();
                int passiveCap = config.clearing.mobs.passiveCapPerWorld;

                for (Entity entity : world.getEntities()) {
                    if (!(entity instanceof LivingEntity le)) continue;
                    if (le instanceof Player) continue;
                    if (le.isDead()) continue;

                    if (config.clearing.mobs.protectNamed && le.isCustomNameVisible()) continue;

                    String typeName = le.getType().name();
                    if (protectedTypes.contains(typeName)) continue;

                    boolean isHostile = isHostileMob(le);
                    if (isHostile && config.clearing.mobs.hostiles) {
                        hostiles.add(le);
                    } else if (!isHostile && config.clearing.mobs.passives && passiveCap > 0) {
                        passives.add(le);
                    }
                }

                Collections.shuffle(hostiles, random);
                Collections.shuffle(passives, random);

                for (LivingEntity le : hostiles) {
                    if (!le.isDead()) {
                        le.remove();
                        hostilesCleared++;
                    }
                }

                if (passives.size() > passiveCap) {
                    int toRemove = passives.size() - passiveCap;
                    for (int i = 0; i < toRemove && i < passives.size(); i++) {
                        LivingEntity le = passives.get(i);
                        if (!le.isDead()) {
                            le.remove();
                            passivesCleared++;
                        }
                    }
                }
            }
        }

        plugin.getLogger().info(String.format("Purge: removed %d items, %d hostiles, %d excess passives",
                itemsCleared, hostilesCleared, passivesCleared));

        return new PurgePlugin.PurgeResult(itemsCleared, hostilesCleared, passivesCleared);
    }

    boolean shouldRemove(Item item, PurgeConfig config) {
        Material type = item.getItemStack().getType();
        if (config.clearing.itemsSettings.whitelist.contains(type)) return false;
        long ageTicks = item.getTicksLived();
        long graceTicks = config.clearing.itemsSettings.gracePeriodSeconds * 20L;
        if (graceTicks > 0 && ageTicks < graceTicks) return false;
        return true;
    }

    private boolean isHostileMob(LivingEntity le) {
        if (le instanceof Monster) return true;
        if (le instanceof Slime slime && slime.getSize() > 1) return true;
        if (le instanceof Ghast) return true;
        if (le instanceof Phantom) return true;
        if (le instanceof Shulker) return true;
        if (le instanceof Enderman) return true;
        if (le instanceof Warden) return true;
        if (le instanceof Wither) return true;
        return false;
    }

    private boolean isTamed(LivingEntity le) {
        if (le instanceof Tameable tameable) {
            return tameable.isTamed();
        }
        if (le instanceof Horse horse) {
            return horse.isTamed();
        }
        return false;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onEntitySpawn(EntitySpawnEvent event) {
    }
}
