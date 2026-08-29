package com.questbook.data;

import com.questbook.quest.Quest;
import com.questbook.quest.QuestObjective;

import java.util.*;

import com.questbook.quest.ObjectiveType;
public class PlayerData {
    private String playerId;
    private Map<String, Boolean> completedQuests = new HashMap<>();
    private Map<String, List<QuestObjective>> activeQuestProgress = new HashMap<>();
    private int level;
    private int experience;
    private String rankId;
    
    public PlayerData(String playerId) {
        this.playerId = playerId;
        this.level = 1;
        this.experience = 0;
    }
    
    public void setActiveQuest(Quest quest) {
        if (!activeQuestProgress.containsKey(quest.getId())) {
            List<QuestObjective> copy = new ArrayList<>();
            for (QuestObjective obj : quest.getObjectives()) {
                copy.add(obj.clone());
            }
            activeQuestProgress.put(quest.getId(), copy);
        }
    }
    
    public boolean isActive(String questId) {
        return activeQuestProgress.containsKey(questId);
    }
    
    public boolean hasActiveQuest() {
        return !activeQuestProgress.isEmpty();
    }
    
    public void progressQuest(String questId, ObjectiveType type, String target, int amount) {
        if (!activeQuestProgress.containsKey(questId)) return;
        
        List<QuestObjective> objectives = activeQuestProgress.get(questId);
        for (QuestObjective obj : objectives) {
            if (obj.getType() == type && (target == null || obj.getTargetId().equals(target))) {
                obj.incrementProgress(amount);
            }
        }
    }
    
    public boolean canComplete(String questId) {
        List<QuestObjective> objectives = activeQuestProgress.get(questId);
        if (objectives == null) return false;
        return objectives.stream().allMatch(QuestObjective::isComplete);
    }
    
    public void completeQuest(String questId) {
        completedQuests.put(questId, true);
        activeQuestProgress.remove(questId);
    }
    
    public void restoreActiveQuest(Quest quest, int[] objectiveProgress) {
        List<QuestObjective> copy = new ArrayList<>();
        List<QuestObjective> originals = quest.getObjectives();
        for (int i = 0; i < originals.size(); i++) {
            QuestObjective orig = originals.get(i);
            int completed = (i < objectiveProgress.length) ? objectiveProgress[i] : 0;
            copy.add(new QuestObjective(
                orig.getDescription(),
                orig.getType(),
                orig.getTargetId(),
                orig.getAmountRequired(),
                completed
            ));
        }
        activeQuestProgress.put(quest.getId(), copy);
    }
    
    public List<Integer> getObjectiveProgress(String questId) {
        List<QuestObjective> objectives = activeQuestProgress.get(questId);
        if (objectives == null) return Collections.emptyList();
        List<Integer> progress = new ArrayList<>();
        for (QuestObjective obj : objectives) {
            progress.add(obj.getAmountCompleted());
        }
        return progress;
    }
    
    // Getters/Setters
    public String getPlayerId() { return playerId; }
    public Map<String, Boolean> getCompletedQuests() { return completedQuests; }
    public Map<String, List<QuestObjective>> getActiveQuestProgress() { return activeQuestProgress; }
    public int getLevel() { return level; }
    public int getExperience() { return experience; }
    public void setLevel(int level) { this.level = level; }
    public void setExperience(int experience) { this.experience = experience; }

    public String getRankId() { return rankId; }
    public void setRankId(String rankId) { this.rankId = rankId; }

    public int getCompletedCount() { return completedQuests.size(); }
}
