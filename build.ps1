# 是飞鱼随机图API - Docker构建脚本(PowerShell版)
Write-Host "🚀 开始构建是飞鱼随机图API Docker镜像" -ForegroundColor Green

# 检查Docker是否运行
try {
    $dockerInfo = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker未运行或未安装，请先启动Docker Desktop" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Docker未运行或未安装，请先启动Docker Desktop" -ForegroundColor Red
    exit 1
}

# 检查是否有正在运行的容器
$runningContainer = docker ps -q --filter "name=Random-Pictures"
if ($runningContainer) {
    Write-Host "⚠️  检测到正在运行的容器，正在停止..." -ForegroundColor Yellow
    docker stop Random-Pictures
    docker rm Random-Pictures
}

# 构建镜像
Write-Host "📦 构建Docker..." -ForegroundColor Cyan
docker build -t random-pictures-api:latest .

# 检查构建是否成功
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Docker镜像构建成功" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 可用命令:" -ForegroundColor Cyan
    Write-Host "docker run -d -p 8081:8081 -v ${PWD}/images:/app/images --name Random-Pictures random-pictures-api:latest" -ForegroundColor White
    Write-Host "docker-compose up -d" -ForegroundColor White
    Write-Host ""
    Write-Host "🌐 访问地址: http://localhost:8081" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "💡 提示: 使用 'docker-compose up -d' 启动服务" -ForegroundColor Yellow
} else {
    Write-Host "❌ Docker镜像构建失败" -ForegroundColor Red
    exit 1
}
