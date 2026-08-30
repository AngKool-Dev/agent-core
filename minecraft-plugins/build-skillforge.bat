@echo off
cd /d D:\agent-core\minecraft-plugins
call D:\agent-core\maven\apache-maven-3.9.6\bin\mvn.cmd clean install -pl skillforge -am -Dmaven.compiler.proc=none -Dmaven.compiler.argument=-XDuseUnsharedTable=false
echo.
echo === EXIT CODE: %ERRORLEVEL% ===
