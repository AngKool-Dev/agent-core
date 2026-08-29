package com.questbook;

import com.questbook.command.QuestCommand;
import com.questbook.data.PlayerDataManager;
import com.questbook.data.WorldState;
import com.questbook.economy.VaultEconomy;
import com.questbook.event.DragonKillListener;
import com.questbook.event.QuestBookClickListener;
import com.questbook.event.QuestProgressListener;
import com.questbook.event.RankJoinListener;
import com.questbook.quest.QuestManager;
import com.questbook.rank.RankManager;
import org.bukkit.plugin.java.JavaPlugin;

public class QuestBookPlugin extends JavaPlugin {

    private QuestManager questManager;
    private PlayerDataManager playerDataManager;
    private WorldState worldState;
    private VaultEconomy vaultEconomy;
    private RankManager rankManager;
    
    public java.io.File jarFile() {
        return getFile();
    }

    @Override
    public void onEnable() {
        saveDefaultConfig();

        this.questManager = new QuestManager(this);
        this.playerDataManager = new PlayerDataManager(this);
        this.worldState = new WorldState(this);
        this.vaultEconomy = new VaultEconomy(this);

        questManager.loadQuests();
        this.rankManager = new RankManager(this);
        rankManager.loadRanks();
        playerDataManager.loadAllData();
        rankManager.applyAllRanks(playerDataManager);
        worldState.load();
        vaultEconomy.setup();

        getCommand("quest").setExecutor(new QuestCommand(this));
        getCommand("quest").setTabCompleter((QuestCommand) getCommand("quest").getExecutor());

        getServer().getPluginManager().registerEvents(new QuestProgressListener(this), this);
        getServer().getPluginManager().registerEvents(new QuestBookClickListener(this), this);
        getServer().getPluginManager().registerEvents(new DragonKillListener(this), this);
        getServer().getPluginManager().registerEvents(new RankJoinListener(this), this);

        getLogger().info("QuestBook enabled!");
    }

    @Override
    public void onDisable() {
        playerDataManager.saveAllData();
        worldState.save();
        getLogger().info("QuestBook disabled!");
    }

    public QuestManager getQuestManager() { return questManager; }
    public PlayerDataManager getPlayerDataManager() { return playerDataManager; }
    public WorldState getWorldState() { return worldState; }
    public VaultEconomy getVaultEconomy() { return vaultEconomy; }
    public RankManager getRankManager() { return rankManager; }
}