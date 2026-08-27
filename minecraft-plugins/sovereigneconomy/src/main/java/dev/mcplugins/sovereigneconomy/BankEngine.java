package dev.mcplugins.sovereigneconomy;

public final class BankEngine {

    private final SovereignEconomyPlugin plugin;
    private double annualRate;

    public BankEngine(SovereignEconomyPlugin plugin) {
        this.plugin = plugin;
        this.annualRate = plugin.settings().baseAnnualRate;
    }

    public double annualRate() {
        return annualRate;
    }

    public void setAnnualRate(double rate) {
        Settings s = plugin.settings();
        annualRate = Math.max(s.minAnnualRate, Math.min(s.maxAnnualRate, rate));
    }

    /** Taylor-rule-lite: raise rates when inflation runs hot, cut when cold. */
    public void adaptRate() {
        Settings s = plugin.settings();
        double inflation = plugin.market().inflationSinceReference();
        double gap = inflation - s.inflationTarget;
        if (gap > 0.01) {
            setAnnualRate(annualRate - s.rateStep);
        } else if (gap < -0.01 && inflation < s.inflationTarget) {
            setAnnualRate(annualRate + s.rateStep * 0.5);
        }
    }

    public void applyInterest() {
        double hourlyFactor = Math.pow(1.0 + annualRate, 1.0 / (365.0 * 24.0));
        plugin.ledger().applyInterestToAll(hourlyFactor);
    }
}
