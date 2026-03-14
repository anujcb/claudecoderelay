# Start SSH tunnel for OpenClaw control panel + ClaudeBridge
# Run this before starting any Claude Code session

$keyPath = "F:\work\OpenClaw\Bot1\clawed1.pem"
$ec2Host = "ubuntu@3.101.144.251"

Write-Host "Starting SSH tunnel to EC2..." -ForegroundColor Cyan
Write-Host "  Port 18789 -> OpenClaw control panel" -ForegroundColor Gray
Write-Host "  Port 8400  -> ClaudeBridge relay" -ForegroundColor Gray
Write-Host ""
Write-Host "Keep this window open. Press Ctrl+C to disconnect." -ForegroundColor Yellow

ssh -i $keyPath -N `
    -L 18789:127.0.0.1:18789 `
    -L 8400:127.0.0.1:8400 `
    -o ServerAliveInterval=60 `
    -o ServerAliveCountMax=3 `
    $ec2Host
