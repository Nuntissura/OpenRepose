@echo off
rem Forwarder for OpenRepose startup script.
rem Run from anywhere inside the repo with:  .\orstart
rem Options:  -Brief, -NoLive
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\orstart.ps1" %*
