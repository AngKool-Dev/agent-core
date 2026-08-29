#!/usr/bin/env python3
"""Build and deploy SkillForge to test server — robust, Adventure API aware."""
import subprocess, os, sys, shutil, time

JAVA_21 = r"C:\Program Files\Microsoft\jdk-21.0.12.8-hotspot\bin\javac.exe"
JAVA_25 = r"C:\Program Files\Microsoft\jdk-25.0.4.7-hotspot\bin\java.exe"

# Classpath jars
PAPER_API = r"C:\Users\Administrator\.m2\repository\io\papermc\paper\paper-api\1.21.4-R0.1-SNAPSHOT\paper-api-1.21.4-R0.1-SNAPSHOT.jar"
ADVENTURE_420 = r"C:\Users\Administrator\.m2\repository\net\kyori\adventure-api\4.20.0\adventure-api-4.20.0.jar"
ADVENTURE_KEY = r"C:\Users\Administrator\.m2\repository\net\kyori\adventure-key\4.20.0\adventure-key-4.20.0.jar"
BUNGEE_CHAT = r"C:\Users\Administrator\.m2\repository\net\md-5\bungeecord-chat\1.21-R0.4\bungeecord-chat-1.21-R0.4.jar"

PROJECT = r"D:/agent-core/minecraft-plugins/skillforge"
SRC = os.path.join(PROJECT, "src", "main", "java")
RES = os.path.join(PROJECT, "src", "main", "resources")
CLASSES = os.path.join(PROJECT, "target", "classes")
JAR_OUT = os.path.join(PROJECT, "target", "SkillForge-0.2.0-SNAPSHOT.jar")
MC_TEST = r"D:\mc-test"
MC_JAR_DEST = os.path.join(MC_TEST, "plugins", "SkillForge-0.2.0-SNAPSHOT.jar")
SERVER_JAR = os.path.join(MC_TEST, "purpur-26.2-2622.jar")

def clean_java():
    result = subprocess.run(["taskkill", "/F", "/IM", "java.exe"], capture_output=True, text=True)
    print(f"kill result: {result.returncode}")
    time.sleep(3)

def compile():
    print("=== Compile ===")
    if os.path.exists(CLASSES):
        shutil.rmtree(CLASSES)
    os.makedirs(CLASSES, exist_ok=True)
    
    # Adventure API (4.20.0) + Adventure Key module FIRST (provides net.kyori.adventure.* types),
    # then Paper API (org.bukkit.Keyed extends net.kyori.adventure.key.Keyed but doesn't bundle it),
    # then BungeeChat (for BaseComponent in Player.sendMessage)
    cp = f"{ADVENTURE_420};{ADVENTURE_KEY};{PAPER_API};{BUNGEE_CHAT}"
    print(f"Classpath: Adventure API + Adventure-Key -> Paper API -> BungeeChat")
    
    # Collect Java files
    java_files = []
    for root, dirs, files in os.walk(SRC):
        for f in files:
            if f.endswith(".java"):
                java_files.append(os.path.join(root, f))
    if not java_files:
        print("No Java files found!")
        return False
    print(f"Compiling {len(java_files)} files...")
    
    cmd = [JAVA_21, "--release", "21", "-cp", cp, "-d", CLASSES,
           "-Xlint:all", "-Xlint:-unchecked", "-Xlint:-deprecation"]
    cmd.extend(java_files)
    
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT, timeout=120)
    print(f"javac exit code: {r.returncode}")
    
    # Show real errors only (not warnings about missing annotations)
    real_errors = 0
    for line in r.stderr.split('\n'):
        if ': error:' in line:
            real_errors += 1
            print(f"  ERROR: {line.strip()}")
    
    if real_errors > 0:
        print(f"\nCompilation FAILED: {real_errors} error(s)")
        return False
    
    # Count .class files
    class_count = 0
    for root, dirs, files in os.walk(CLASSES):
        for f in files:
            if f.endswith(".class"):
                class_count += 1
    
    print(f"Compiled {len(java_files)} Java files -> {class_count} .class files")
    
    if class_count == 0:
        print("ERROR: No .class files produced!")
        print("STDERR:", r.stderr[:2000])
        return False
    
    print("Compilation OK")
    return True

def package_jar():
    print("=== Package JAR ===")
    if os.path.exists(JAR_OUT):
        os.remove(JAR_OUT)
    
    for root, dirs, files in os.walk(RES):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, RES)
            dst = os.path.join(CLASSES, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    
    jar_tool = os.path.join(os.path.dirname(JAVA_21), "jar.exe")
    if not os.path.exists(jar_tool):
        print(f"jar.exe not found at {jar_tool}")
        return False
    
    cmd = [jar_tool, "cf", JAR_OUT, "-C", CLASSES, "."]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT, timeout=30)
    if r.returncode != 0:
        print("JAR tool STDERR:", r.stderr[:1000])
        return False
    
    size = os.path.getsize(JAR_OUT)
    print(f"JAR built: {JAR_OUT} ({size} bytes)")
    return True

def deploy():
    print("=== Deploy ===")
    if not os.path.exists(JAR_OUT):
        print("ERROR: JAR not found")
        return False
    if os.path.exists(MC_JAR_DEST):
        try:
            os.remove(MC_JAR_DEST)
        except PermissionError:
            print("Cannot replace JAR - server may be running")
            return False
    shutil.copy2(JAR_OUT, MC_JAR_DEST)
    print(f"Copied to: {MC_JAR_DEST} ({os.path.getsize(MC_JAR_DEST)} bytes)")
    return True

if __name__ == "__main__":
    clean_java()
    if compile():
        package_jar()
        deploy()
        print("\n=== Build complete ===")
        print(f"JAR at: {JAR_OUT}")
        print(f"Deployed to: {MC_JAR_DEST}")
        print("Run start-server.cmd to launch (Java 25 required)")
    else:
        print("\nBuild FAILED")
        sys.exit(1)
