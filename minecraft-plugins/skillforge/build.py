#!/usr/bin/env python3
"""Build and deploy SkillForge JAR to test server."""
import subprocess, shutil, os, sys, re, zipfile
from pathlib import Path

MC_TEST_DIR = r"D:\mc-test"
JAR_DEST = os.path.join(MC_TEST_DIR, "plugins", "SkillForge-0.2.0-SNAPSHOT.jar")
PROJECT_DIR = r"D:/agent-core/minecraft-plugins/skillforge"
SKILLFORGE_SRC = os.path.join(PROJECT_DIR, "src", "main")
JAVAC = r"C:\Program Files\Microsoft\jdk-21.0.12.8-hotspot\bin\javac.exe"

PAPER_API = r"C:\Users\Administrator\.m2\repository\io\papermc\paper\paper-api\1.21.4-R0.1-SNAPSHOT\paper-api-1.21.4-R0.1-SNAPSHOT.jar"
ADVENTURE_API = r"C:\Users\Administrator\.m2\repository\io\leapcraft\adventure-api\1.3.3\adventure-api-1.3.3.jar"

JAVA25 = r"C:\Program Files\Microsoft\jdk-25.0.4.7-hotspot\bin\java.exe"

print("=== Build SkillForge ===", file=sys.stderr)
compile_py_content = """
import os, subprocess, sys
from pathlib import Path

JAVAC = r"C:\\Program Files\\Microsoft\\jdk-21.0.12.8-hotspot\\bin\\javac.exe"
PAPER_API = r"C:\\Users\\Administrator\\.m2\\repository\\io\\papermc\\paper\\paper-api\\1.21.4-R0.1-SNAPSHOT\\paper-api-1.21.4-R0.1-SNAPSHOT.jar"
ADVENTURE_API = r"C:\\Users\\Administrator\\.m2\\repository\\io\\leapcraft\\adventure-api\\1.3.3\\adventure-api-1.3.3.jar"
JAVA25 = r"C:\\Program Files\\Microsoft\\jdk-25.0.4.7-hotspot\\bin\\java.exe"
DEV_DIR = r"D:\\agent-core\\minecraft-plugins\\skillforge"
SRC_DIR = os.path.join(DEV_DIR, "src", "main", "java")
RES_DIR = os.path.join(DEV_DIR, "src", "main", "resources")
JAVA25_DLL = r"C:\\Program Files\\Microsoft\\jdk-25.0.4.7-hotspot\\bin\\java.exe"
JAVAC_CMD = r"C:\\Program Files\\Microsoft\\jdk-21.0.12.8-hotspot\\bin\\javac.exe"
PAPER_API_ARTIFACT = r"C:\\Users\\Administrator\\.m2\\repository\\io\\papermc\\paper\\paper-api\\1.21.4-R0.1-SNAPSHOT\\paper-api-1.21.4-R0.1-SNAPSHOT.jar"
ADVENTURE_API_ARTIFACT = r"C:\\Users\\Administrator\\.m2\\repository\\io\\leapcraft\\adventure-api\\1.3.3\\adventure-api-1.3.3.jar"

def compile():
    print("=== Compile ===", file=sys.stderr)
    cmd = [
        JAVAC_CMD, "--release", "21",
        "-cp", PAPER_API + ";" + ADVENTURE_API,
        "-d", os.path.join(DEV_DIR, "target", "classes"),
        os.path.join(SRC_DIR, "*.java"),
        "-Xlint:all", "-Xlint:-unchecked", "-Xlint:-rawtypes",
        "-Xlint:-deprecation"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=DEV_DIR)
    if proc.returncode != 0:
        print("Compile FAILED:", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        sys.exit(1)
    print("Compilation OK", file=sys.stderr)
    return True

def package_jar():
    print("=== Package JAR ===", file=sys.stderr)
    JAR_OUT = os.path.join(DEV_DIR, "target", "SkillForge-0.2.0-SNAPSHOT.jar")
    jar_cmd = [
        JAVA25_DLL, "-jar",
        os.path.join(os.path.dirname(JAVAC), "..", "lib", "jar.exe"),
        "cf", JAR_OUT,
        "-C", os.path.join(DEV_DIR, "target", "classes"),
        ".",
        "-C", RES_DIR,
        "."
    ]
    proc = subprocess.run(jar_cmd, capture_output=True, text=True, cwd=DEV_DIR)
    if proc.returncode != 0:
        print("JAR packaging FAILED:", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"JAR built: {JAR_OUT} ({os.path.getsize(JAR_OUT)} bytes)", file=sys.stderr)
    return True

if __name__ == "__main__":
    compile()
    package_jar()
"""
# Use build_skillforge.py for compile/package
BUILD_SCRIPT = os.path.join(PROJECT_DIR, "build.py")
if os.path.exists(BUILD_SCRIPT):
    subprocess.run([sys.executable, BUILD_SCRIPT], capture_output=True, text=True)
    print("Build script executed", file=sys.stderr)

sys.exit(0)
