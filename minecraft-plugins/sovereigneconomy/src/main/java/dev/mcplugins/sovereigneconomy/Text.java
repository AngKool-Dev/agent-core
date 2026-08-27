package dev.mcplugins.sovereigneconomy;

import java.text.DecimalFormat;
import java.util.Locale;

public final class Text {

    private static final DecimalFormat MONEY = new DecimalFormat("#,##0.00");
    private static final DecimalFormat INT = new DecimalFormat("#,##0");

    private Text() {
    }

    public static String money(double amount, Settings s) {
        return s.currencySymbol + " " + MONEY.format(amount);
    }

    public static String qty(int amount) {
        return INT.format(amount);
    }

    public static String pct(double fraction) {
        return String.format(Locale.US, "%+.2f%%", fraction * 100.0);
    }

    public static String title(String s) {
        String[] parts = s.replace('_', ' ').split(" ");
        StringBuilder sb = new StringBuilder();
        for (String p : parts) {
            if (!p.isEmpty()) {
                if (sb.length() > 0) {
                    sb.append(' ');
                }
                sb.append(Character.toUpperCase(p.charAt(0))).append(p.substring(1));
            }
        }
        return sb.toString();
    }
}
