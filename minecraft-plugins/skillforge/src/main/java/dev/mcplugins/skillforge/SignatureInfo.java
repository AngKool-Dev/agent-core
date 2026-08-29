package dev.mcplugins.skillforge;

import java.util.UUID;

public final class SignatureInfo {

    public final String spec;
    public final String tier;
    public final int xp;
    public final UUID crafter;
    public final int count;
    public final String forgeName;

    public SignatureInfo(String spec, String tier, int xp, UUID crafter,
                         int count, String forgeName) {
        this.spec = spec;
        this.tier = tier;
        this.xp = xp;
        this.crafter = crafter;
        this.count = count;
        this.forgeName = forgeName;
    }
}
