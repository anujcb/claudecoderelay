# Auto-reconnecting SSH tunnel
$keyPath = "F:\work\OpenClaw\Bot1\clawed1.pem"
$ec2Host = "ubuntu@3.101.144.251"

while ($true) {
    Write-Host "[$(Get-Date)] Connecting SSH tunnel..." -ForegroundColor Cyan

    ssh -i $keyPath -N `
        -L 18789:127.0.0.1:18789 `
        -L 8400:127.0.0.1:8400 `
        -o ServerAliveInterval=60 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        $ec2Host

    Write-Host "[$(Get-Date)] Tunnel disconnected. Reconnecting in 5 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
