package dev.mcplugins.sovereigneconomy;

public final class Commodity {

    public final String id;
    public final double base;
    public final double depth;
    public double mult = 1.0;
    public double referenceMult = 1.0;

    public Commodity(String id, double base, double depth) {
        this.id = id;
        this.base = base;
        this.depth = Math.max(1.0, depth);
    }

    public double buyPrice(double spread) {
        return base * mult * (1.0 + spread);
    }

    public double sellPrice(double spread) {
        return base * mult * (1.0 - spread);
    }

    public void applyTrade(int qty, boolean buying) {
        double signed = buying ? qty : -qty;
        mult *= Math.exp(signed / depth);
        mult = Math.max(0.20, Math.min(5.0, mult));
    }

    public void revert(double factor) {
        mult += (1.0 - mult) * factor;
    }
}
