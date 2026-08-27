package dev.mcplugins.mobecology;

import java.util.HashMap;
import java.util.Map;

public final class EcologyRegion {

    public final Map<String, Double> pop = new HashMap<>();
    public final Map<String, Long> lastSeen = new HashMap<>();
    public final Map<String, Double> pressure = new HashMap<>();
    public long lastCensus;

    public double total(Map<String, String> speciesCategory, MobEcologyPlugin.Category category) {
        double sum = 0;
        for (Map.Entry<String, Double> e : pop.entrySet()) {
            String cat = speciesCategory.get(e.getKey());
            if (cat != null && cat.equals(category.name())) {
                sum += e.getValue();
            }
        }
        return sum;
    }
}
