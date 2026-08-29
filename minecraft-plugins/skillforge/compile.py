#!/usr/bin/env python3
"""Compile SkillForge with all dependencies."""
import subprocess, pathlib, sys

javac = r"C:\Program Files\Microsoft\jdk-21.0.12.8-hotspot\bin\javac.exe"
src_dir = r"D:\agent-core\minecraft-plugins\skillforge\src\main\java"
out_dir = r"D:\agent-core\minecraft-plugins\skillforge\target\classes"
paper_api = r"C:\Users\Administrator\.m2\repository\io\papermc\paper\paper-api\1.21.4-R0.1-SNAPSHOT\paper-api-1.21.4-R0.1-SNAPSHOT.jar"
adventure_api = r"C:\Users\Administrator\.m2\repository\net\kyori\adventure-api\4.20.0\adventure-api-4.20.0.jar"
adventure_key = r"C:\Users\Administrator\.m2\repository\net\kyori\adventure-key\4.20.0\adventure-key-4.20.0.jar"
bungee_chat = r"C:\Users\Administrator\.m2\repository\net\md-5\bungeecord-chat\1.21-R0.4\bungeecord-chat-1.21-R0.4.jar"

java_files = [str(f) for f in pathlib.Path(src_dir).rglob("*.java")]
cp = ";".join([paper_api, adventure_api, adventure_key, bungee_chat])

result = subprocess.run(
    [javac, "--release", "21",
     "-cp", cp,
     "-d", out_dir,
     "-Xlint:all",
     "-Xlint:-deprecation",
     "-Xlint:-unchecked",
     "-sourcepath", src_dir,
     *java_files],
    capture_output=True, text=True
)

print("=== STDOUT ===")
print(result.stdout[-2000:])
print("=== STDERR (errors only) ===")
lines = result.stderr.splitlines()
err_lines = [l for l in lines if "error:" in l or "Error:" in l]
for l in err_lines:
    print(l)
print(f"\nTotal errors: {len(err_lines)}")
print("=== EXIT ===", result.returncode)
