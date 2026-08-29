/*
 * MIT License
 *
 * Copyright (c) 2026 Sentinel Audit Contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
package dev.sentinel.audit.models;

/**
 * Enumeration of supported database backends.
 *
 * <p>Determines the JDBC driver, connection URL format, and SQL
 * dialect used by the plugin.</p>
 */
public enum DatabaseType {

    /** PostgreSQL database backend. */
    POSTGRESQL("org.postgresql.Driver", "jdbc:postgresql://%s:%d/%s"),

    /** SQLite database backend. */
    SQLITE("org.sqlite.JDBC", "jdbc:sqlite:%s");

    private final String driverClass;
    private final String urlTemplate;

    /**
     * Constructs a database type.
     *
     * @param driverClass the JDBC driver class name
     * @param urlTemplate the JDBC URL template
     */
    DatabaseType(String driverClass, String urlTemplate) {
        this.driverClass = driverClass;
        this.urlTemplate = urlTemplate;
    }

    /**
     * Gets the JDBC driver class name.
     *
     * @return the driver class
     */
    public String getDriverClass() {
        return driverClass;
    }

    /**
     * Gets the JDBC URL template.
     *
     * @return the URL template
     */
    public String getUrlTemplate() {
        return urlTemplate;
    }
}
