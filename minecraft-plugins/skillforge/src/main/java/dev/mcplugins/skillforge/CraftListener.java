package dev.mcplugins.skillforge;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.CraftItemEvent;
import org.bukkit.inventory.ItemStack;
import java.util.Set;
import java.util.UUID;

public class CraftListener implements Listener {
    private final SkillEngine engine;
    private final SkillForgePlugin plugin;
    private final Settings settings;

    public CraftListener(SkillForgePlugin plugin) {
        this.plugin = plugin;
        this.engine = plugin.engine();
        this.settings = plugin.settings();
        Bukkit.getPluginManager().registerEvents(this, plugin);
    }

    @EventHandler
    public void onCraft(CraftItemEvent event) {
        if (!(event.getWhoClicked() instanceof Player player)) return;
        ItemStack crafted = event.getInventory().getItem(event.getSlot());
        if (crafted == null || crafted.getType().isAir()) return;
        UUID uuid = player.getUniqueId();
        String specId = engine.activeSpec(uuid);
        if (specId == null) return;
        int xpGain = engine.awardCraftXP(uuid, specId, crafted);
        String msg = settings.colored(
            "&a[SkillForge] &fCrafted in &f" + settings.getSpecialization(specId).name +
            "&f. Gained &f" + xpGain + " XP&f."
        );
        player.sendMessage(msg);
        if (engine.getApprenticeCount(uuid) > 0) {
            Set<UUID> apprentices = engine.apprenticeships().get(uuid);
            if (apprentices != null) {
                for (UUID apprU : apprentices) {
                    Player appr = Bukkit.getPlayer(apprU);
                    if (appr != null && appr.getWorld().equals(player.getWorld())
                            && appr.getLocation().distanceSquared(player.getLocation()) <= 256) {
                        appr.sendMessage(settings.colored(
                            "&7[SkillForge] &fYour master &f" + player.getName() +
                            "&7 crafted and gained XP!"
                        ));
                    }
                }
            }
        }
    }
}
