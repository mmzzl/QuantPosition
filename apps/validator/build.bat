@echo off
cd /d "%~dp0"
go build -buildmode=c-shared -o validator.dll .
echo Built: validator.dll
