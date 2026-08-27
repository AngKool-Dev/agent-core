package dev.mcplugins.mobecology;

import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Locale;

public final class Compat {

    private Compat() {
    }

    /**
     * Resolves an Attribute across Bukkit builds where constants were renamed
     * (pre/post 1.21.2) without referencing any constant statically.
     */
    public static Attribute attribute(String... candidates) {
        Object resolved = viaRegistry(candidates);
        if (resolved == null) {
            resolved = viaEnum(candidates);
        }
        return resolved == null ? null : (Attribute) resolved;
    }

    private static Object viaRegistry(String... keys) {
        try {
            Class<?> registryClass = Class.forName("org.bukkit.Registry");
            Field field = null;
            for (Field f : registryClass.getFields()) {
                if (f.getName().equalsIgnoreCase("ATTRIBUTE")) {
                    field = f;
                    break;
                }
            }
            if (field == null) {
                return null;
            }
            Object registry = field.get(null);
            Method get = null;
            for (Method m : registry.getClass().getMethods()) {
                if (m.getName().equals("get") && m.getParameterCount() == 1
                        && m.getParameterTypes()[0] == NamespacedKey.class) {
                    get = m;
                    break;
                }
            }
            if (get == null) {
                return null;
            }
            for (String k : keys) {
                Object res = get.invoke(registry, NamespacedKey.minecraft(k));
                if (res != null) {
                    return res;
                }
            }
        } catch (Throwable ignored) {
        }
        return null;
    }

    private static Object viaEnum(String... names) {
        try {
            Class<?> attr = Class.forName("org.bukkit.attribute.Attribute");
            Object[] constants = attr.getEnumConstants();
            if (constants == null) {
                return null;
            }
            for (String n : names) {
                for (Object c : constants) {
                    String cn = ((Enum<?>) c).name();
                    if (cn.equalsIgnoreCase(n) || cn.equalsIgnoreCase("GENERIC_" + n.toUpperCase(Locale.ROOT))) {
                        return c;
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        return null;
    }
}
