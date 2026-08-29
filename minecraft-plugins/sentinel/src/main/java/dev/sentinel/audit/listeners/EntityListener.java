/*
 * MIT License
 *
 * Copyright (c) 2026 Sentinel Audit Contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
package dev.sentinel.audit.listeners;

import dev.sentinel.audit.api.AuditEvent;
import dev.sentinel.audit.api.AuditService;
import dev.sentinel.audit.config.SentinelConfig;
import dev.sentinel.audit.models.AuditAction;
import dev.sentinel.audit.models.AuditSource;
import java.util.Map;
import java.util.UUID;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Tameable;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityTameEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.jetbrains.annotations.NotNull;

/**
 * Listens to entity-related events and records them to the audit log.
 *
 * <p>Tracks entity spawns, deaths, damage, and taming for comprehensive
 * entity activity auditing.</p>
 */
public final class EntityListener implements Listener {

    private final AuditService auditService;
    private final SentinelConfig config;

    /**
     * Constructs a new entity listener.
     *
     * @param auditService the audit service
     * @param config the plugin configuration
     */
    public EntityListener(@NotNull AuditService auditService, @NotNull SentinelConfig config) {
        this.auditService = auditService;
        this.config = config;
    }

    /**
     * Handles entity death events.
     *
     * @param event the entity death event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onEntityDeath(EntityDeathEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Entity entity = event.getEntity();
        if (!config.isWorldEnabled(entity.getWorld().getName())) {
            return;
        }
        Player killer = event.getEntity().getKiller();
        java.util.Map<String, String> metadata = new java.util.LinkedHashMap<>();
        metadata.put("entityType", entity.getType().name());
        metadata.put("entityUuid", entity.getUniqueId().toString());
        AuditSource source = AuditSource.NATURAL;
        UUID actorId = entity.getUniqueId();
        String actorName = entity.getType().name();
        if (killer != null) {
            source = AuditSource.PLAYER;
            actorId = killer.getUniqueId();
            actorName = killer.getName();
            metadata.put("killerName", killer.getName());
            metadata.put("killerUuid", killer.getUniqueId().toString());
        }

        AuditEvent auditEvent = new AuditEvent(
                java.util.UUID.randomUUID(),
                AuditAction.ENTITY_DEATH,
                source,
                actorId,
                actorName,
                entity.getUniqueId(),
                entity.getType().name(),
                entity.getLocation(),
                entity.getWorld().getName(),
                java.time.Instant.now(),
                metadata);
        auditService.record(auditEvent);
    }

    /**
     * Handles player death events.
     *
     * @param event the player death event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlayerDeath(PlayerDeathEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Player player = event.getPlayer();
        if (!config.isWorldEnabled(player.getWorld().getName())) {
            return;
        }
        Map<String, String> metadata =
                Map.of("cause", event.getDeathMessage() != null ? event.getDeathMessage() : "unknown");

        AuditEvent auditEvent = AuditEvent.ofPlayer(AuditAction.PLAYER_DEATH, player, player.getLocation(), metadata);
        auditService.record(auditEvent);
    }

    /**
     * Handles entity damage events.
     *
     * <p>Only player-caused damage is recorded. Ambient sources (falling,
     * fire, suffocation, mob fights) generate a large amount of noise on busy
     * servers, so they are filtered out here to keep the database lean.</p>
     *
     * @param event the entity damage event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onEntityDamage(EntityDamageEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Entity entity = event.getEntity();
        if (!config.isWorldEnabled(entity.getWorld().getName())) {
            return;
        }
        Entity attacker = event.getDamageSource().getCausingEntity();
        if (!(attacker instanceof Player player)) {
            return;
        }
        Map<String, String> metadata = Map.of(
                "entityType", entity.getType().name(),
                "damage", String.valueOf(event.getFinalDamage()),
                "cause", event.getCause().name());

        AuditEvent auditEvent = new AuditEvent(
                java.util.UUID.randomUUID(),
                AuditAction.ENTITY_DAMAGE,
                AuditSource.NATURAL,
                entity.getUniqueId(),
                entity.getType().name(),
                null,
                null,
                entity.getLocation(),
                entity.getWorld().getName(),
                java.time.Instant.now(),
                metadata);
        auditService.record(auditEvent);
    }

    /**
     * Handles entity tame events.
     *
     * @param event the entity tame event
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onEntityTame(EntityTameEvent event) {
        if (config == null || auditService == null) {
            return;
        }
        Entity entity = event.getEntity();
        if (!config.isWorldEnabled(entity.getWorld().getName())) {
            return;
        }
        if (!config.isActionEnabled(AuditAction.ENTITY_TAME.name())) {
            return;
        }
        String ownerName = null;
        UUID ownerUuid = null;
        if (entity instanceof Tameable tameable && tameable.getOwner() instanceof Player owner) {
            ownerName = owner.getName();
            ownerUuid = owner.getUniqueId();
        }
        Map<String, String> metadata =
                Map.of("entityType", entity.getType().name(), "ownerName", ownerName != null ? ownerName : "unknown");

        AuditEvent auditEvent = new AuditEvent(
                java.util.UUID.randomUUID(),
                AuditAction.ENTITY_TAME,
                AuditSource.PLAYER,
                ownerUuid != null ? ownerUuid : entity.getUniqueId(),
                ownerName != null ? ownerName : "WORLD",
                null,
                null,
                entity.getLocation(),
                entity.getWorld().getName(),
                java.time.Instant.now(),
                metadata);
        auditService.record(auditEvent);
    }
}
