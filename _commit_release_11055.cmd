@echo off
cd /d "%~dp0"
git reset HEAD -- _release_1.10.54.log _release_1.10.54_run.log _release_1.10.55_run.log 2>nul
git add -A
git reset HEAD -- _release_1.10.54.log _release_1.10.54_run.log _release_1.10.55_run.log 2>nul
git commit -m "release: v1.10.55"
if errorlevel 1 exit /b 1
git status -sb
git push
if errorlevel 1 exit /b 1
echo PUSH_OK
