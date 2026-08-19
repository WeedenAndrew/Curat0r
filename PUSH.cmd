@echo off
REM Curat0r - first push. Read each step; nothing here contacts the network
REM except the final line, which is left for you to run yourself.
setlocal
cd /d "%~dp0"

echo(
echo ==== 1. clear a stale index lock, only if no git process is running ====
tasklist /FI "IMAGENAME eq git.exe" 2>nul | find /I "git.exe" >nul
if not errorlevel 1 (
  echo    A git process is running. Close it and re-run. Nothing was changed.
  goto :end
)
if exist ".git\index.lock" (
  del ".git\index.lock"
  echo    removed stale .git\index.lock
) else (
  echo    no lock present
)

echo(
echo ==== 2. refuse anything sensitive ====
git add -A
git diff --cached --name-only > "%TEMP%\curat0r_staged.txt"
findstr /I /R "\.env secret credential \.key$ \.pem$ token" "%TEMP%\curat0r_staged.txt" >nul
if not errorlevel 1 (
  echo    STOPPING. A staged path looks sensitive:
  findstr /I /R "\.env secret credential \.key$ \.pem$ token" "%TEMP%\curat0r_staged.txt"
  git reset >nul
  echo    Nothing was committed. Unstaged everything.
  goto :end
)
echo    clean

echo(
echo ==== 3. what is staged ====
git diff --cached --stat

echo(
echo ==== 4. commit ====
git commit -m "Phase 0: corpus foundation, guards, adjacency, gaps, dedupe" ^
 -m "1,425 lines, 101 tests, no runtime dependencies. Source ingestion sits behind a fetcher protocol with no live implementation yet - every source runs on fixtures. See ROADMAP.md."
if errorlevel 1 (
  echo    commit failed or nothing to commit
  goto :end
)

echo(
echo ==== 5. remote ====
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin https://github.com/WeedenAndrew/Curat0r.git
  echo    added origin
) else (
  echo    origin already set:
  git remote -v
)

echo(
echo ==== DONE. Nothing has been pushed. ====
echo(
echo Run this yourself when you have read the diff above:
echo(
echo     git push -u origin main
echo(

:end
endlocal
pause
