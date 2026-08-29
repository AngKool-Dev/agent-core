package com.questbook.quest;

import java.util.List;
import java.util.ArrayList;

public class Quest {
    private String id;
    private String title;
    private String description;
    private QuestType type;
    private List<QuestObjective> objectives;
    private QuestRewards rewards;
    private int requiredLevel;
    private boolean repeatable;
    private String requiredQuestId;
    private boolean requiresDragonKilled;
    private boolean onlyWhenDragonAlive;
    private QuestDifficulty difficulty;
    
    public Quest(String id, String title, String description, QuestType type,
                 List<QuestObjective> objectives, QuestRewards rewards,
                 int requiredLevel, boolean repeatable, String requiredQuestId,
                 boolean requiresDragonKilled, boolean onlyWhenDragonAlive,
                 QuestDifficulty difficulty) {
        this.id = id;
        this.title = title;
        this.description = description;
        this.type = type;
        this.objectives = objectives;
        this.rewards = rewards;
        this.requiredLevel = requiredLevel;
        this.repeatable = repeatable;
        this.requiredQuestId = requiredQuestId;
        this.requiresDragonKilled = requiresDragonKilled;
        this.onlyWhenDragonAlive = onlyWhenDragonAlive;
        this.difficulty = difficulty != null ? difficulty : QuestDifficulty.NORMAL;
    }
    
    public boolean isComplete() {
        for (QuestObjective obj : objectives) {
            if (!obj.isComplete()) return false;
        }
        return true;
    }
    
    public double getProgressPercent() {
        if (objectives.isEmpty()) return 0;
        int total = 0, completed = 0;
        for (QuestObjective obj : objectives) {
            total += obj.getAmountRequired();
            completed += obj.getAmountCompleted();
        }
        return total > 0 ? (double) completed / total * 100 : 0;
    }
    
    // Getters
    public String getId() { return id; }
    public String getTitle() { return title; }
    public String getDescription() { return description; }
    public QuestType getType() { return type; }
    public List<QuestObjective> getObjectives() { return objectives; }
    public QuestRewards getRewards() { return rewards; }
    public int getRequiredLevel() { return requiredLevel; }
    public boolean isRepeatable() { return repeatable; }
    public String getRequiredQuestId() { return requiredQuestId; }
    public boolean requiresDragonKilled() { return requiresDragonKilled; }
    public boolean onlyWhenDragonAlive() { return onlyWhenDragonAlive; }
    public QuestDifficulty getDifficulty() { return difficulty; }
}
