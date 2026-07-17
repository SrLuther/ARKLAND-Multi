@echo off
cd /d "c:\Users\Ciano\Documents\arkland-multi"
git add -A
git reset HEAD -- _release_1.10.54.log _release_1.10.54_ship.log _release_1.10.54_ship.err.log _release_1.10.54_run.log 2>nul
echo release: v1.10.54> .git\COMMIT_MSG_TMP.txt
git commit -F .git\COMMIT_MSG_TMP.txt
if errorlevel 1 exit /b 1
del .git\COMMIT_MSG_TMP.txt 2>nul
git push
if errorlevel 1 exit /b 1
git log -1 --oneline
exit /b 0
