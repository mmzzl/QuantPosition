<#
.SYNOPSIS
    Nginx management script (NSSM-based)
.DESCRIPTION
    Manage nginx as a Windows service via NSSM
.EXAMPLE
    .\nginx-service.ps1 install
    .\nginx-service.ps1 start
    .\nginx-service.ps1 stop
    .\nginx-service.ps1 restart
    .\nginx-service.ps1 status
    .\nginx-service.ps1 remove
#>

param(
    [ValidateSet('install', 'start', 'stop', 'restart', 'status', 'remove')]
    [string]$Action = 'status'
)

$ServiceName = 'nginx'
$NginxDir = 'C:\nginx-1.30.3'
$NginxExe = $NginxDir + '\nginx.exe'
$NginxConf = $NginxDir + '\conf\nginx.conf'

function Check-Prereqs {
    if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-Host '[ERR] nssm not found'
        exit 1
    }
    if (-not (Test-Path $NginxExe)) {
        Write-Host '[ERR] nginx not found:' $NginxExe
        exit 1
    }
}

function Service-Install {
    Check-Prereqs
    if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
        Write-Host '[WARN] service already exists:' $ServiceName
        return
    }
    Write-Host '[INFO] installing service...'
    nssm install $ServiceName $NginxExe
    nssm set $ServiceName AppParameters "-p `"$NginxDir`""
    nssm set $ServiceName Start SERVICE_AUTO_START
    nssm set $ServiceName DisplayName 'Nginx HTTP Server'
    nssm set $ServiceName Description 'Nginx web server'
    nssm set $ServiceName AppStdout ($NginxDir + '\logs\nssm_stdout.log')
    nssm set $ServiceName AppStderr ($NginxDir + '\logs\nssm_stderr.log')
    nssm set $ServiceName AppStopMethodSkip 0
    nssm set $ServiceName AppStopMethodConsole 3000
    nssm set $ServiceName AppStopMethodWindow 3000
    nssm set $ServiceName AppStopMethodThreads 3000
    Write-Host '[OK] service installed'
    Service-Start
}

function Service-Start {
    Check-Prereqs
    $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host '[ERR] service not installed'
        return
    }
    if ($svc.Status -eq 'Running') {
        Write-Host '[WARN] nginx already running'
        return
    }
    Write-Host '[INFO] starting nginx...'
    Start-Service $ServiceName
    Start-Sleep 1
    $svc.Refresh()
    if ($svc.Status -eq 'Running') {
        Write-Host '[OK] nginx started'
    } else {
        Write-Host '[ERR] start failed, check:' ($NginxDir + '\logs\error.log')
    }
}

function Service-Stop {
    $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc -or $svc.Status -ne 'Running') {
        Write-Host '[WARN] nginx not running'
        return
    }
    Write-Host '[INFO] stopping nginx...'
    Stop-Service $ServiceName -Force
    $svc.Refresh()
    if ($svc.Status -eq 'Stopped') {
        Write-Host '[OK] nginx stopped'
    } else {
        Write-Host '[ERR] nginx stop failed'
    }
}

function Service-Restart {
    Service-Stop
    Start-Sleep 1
    Service-Start
}

function Service-Status {
    $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host '[WARN] service not installed'
        return
    }
    Write-Host 'Name:    ' $ServiceName
    Write-Host 'Status:  ' $svc.Status
    Write-Host 'Path:    ' $NginxExe
    Write-Host 'Config:  ' $NginxConf
    Write-Host 'Start:   ' $svc.StartType
    if ($svc.Status -eq 'Running') {
        $procs = Get-Process -Name nginx -ErrorAction SilentlyContinue
        if ($procs) {
            Write-Host 'Process: ' $procs.Count
        }
    }
}

function Service-Remove {
    $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host '[WARN] service not installed'
        return
    }
    if ($svc.Status -eq 'Running') {
        Service-Stop
        Start-Sleep 1
    }
    Write-Host '[INFO] removing service...'
    nssm remove $ServiceName confirm
    Write-Host '[OK] service removed'
}

if ($Action -eq 'install') { Service-Install }
elseif ($Action -eq 'start')   { Service-Start }
elseif ($Action -eq 'stop')    { Service-Stop }
elseif ($Action -eq 'restart') { Service-Restart }
elseif ($Action -eq 'status')  { Service-Status }
elseif ($Action -eq 'remove')  { Service-Remove }
