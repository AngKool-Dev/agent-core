package com.questbook.quest;

public class QuestObjective {
    private String description;
    private ObjectiveType type;
    private String targetId;
    private int amountRequired;
    private int amountCompleted;
    
    public QuestObjective(String description, ObjectiveType type, String targetId, int amountRequired) {
        this(description, type, targetId, amountRequired, 0);
    }
    
    public QuestObjective(String description, ObjectiveType type, String targetId, int amountRequired, int amountCompleted) {
        this.description = description;
        this.type = type;
        this.targetId = targetId;
        this.amountRequired = amountRequired;
        this.amountCompleted = amountCompleted;
    }
    
    public boolean isComplete() {
        return amountCompleted >= amountRequired;
    }
    
    public void incrementProgress(int amount) {
        this.amountCompleted = Math.min(this.amountCompleted + amount, amountRequired);
    }
    
    // Getters and setters
    public String getDescription() { return description; }
    public ObjectiveType getType() { return type; }
    public String getTargetId() { return targetId; }
    public int getAmountRequired() { return amountRequired; }
    public int getAmountCompleted() { return amountCompleted; }
    public void setAmountCompleted(int amountCompleted) { this.amountCompleted = amountCompleted; }
    
    public QuestObjective clone() {
        return new QuestObjective(description, type, targetId, amountRequired, amountCompleted);
    }
}
