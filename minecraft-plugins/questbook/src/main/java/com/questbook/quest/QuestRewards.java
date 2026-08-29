package com.questbook.quest;

import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;

public class QuestRewards {
    private Map<String, Integer> items;  // item_id -> amount
    private int experience;
    private int money;
    private List<RareReward> rareRewards; // chance-based rare drops
    
    public QuestRewards(Map<String, Integer> items, int experience, int money) {
        this(items, experience, money, new ArrayList<>());
    }
    
    public QuestRewards(Map<String, Integer> items, int experience, int money, List<RareReward> rareRewards) {
        this.items = items != null ? items : new HashMap<>();
        this.experience = experience;
        this.money = money;
        this.rareRewards = rareRewards != null ? rareRewards : new ArrayList<>();
    }
    
    public Map<String, Integer> getItems() { return items; }
    public int getExperience() { return experience; }
    public int getMoney() { return money; }
    public List<RareReward> getRareRewards() { return rareRewards; }
}
