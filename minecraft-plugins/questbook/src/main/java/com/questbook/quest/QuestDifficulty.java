package com.questbook.quest;

public enum QuestDifficulty {
    NORMAL("Normal", 1, 1.0),
    HARD("Hard", 2, 10.0),
    SUPER_HARD("Superhard", 3, 100.0);

    private final String displayName;
    private final int tier;
    private final double moneyMultiplier;

    QuestDifficulty(String displayName, int tier, double moneyMultiplier) {
        this.displayName = displayName;
        this.tier = tier;
        this.moneyMultiplier = moneyMultiplier;
    }

    public String getDisplayName() { return displayName; }
    public int getTier() { return tier; }
    public double getMoneyMultiplier() { return moneyMultiplier; }

    public static QuestDifficulty fromString(String value) {
        if (value == null) return NORMAL;
        try {
            return QuestDifficulty.valueOf(value.toUpperCase());
        } catch (IllegalArgumentException e) {
            try {
                return QuestDifficulty.valueOf(value.toUpperCase().replace("-", "_").replace(" ", "_"));
            } catch (IllegalArgumentException ex) {
                return NORMAL;
            }
        }
    }
}
