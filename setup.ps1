# 随机图API - Windows一键安装脚本 (PowerShell)
Write-Host "🚀 随机图API一键安装脚本" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

# 检查Docker
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

try {
    $composeVersion = docker-compose --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker Compose未安装" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Docker Compose未安装" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Docker环境检查通过" -ForegroundColor Green

# 创建必要的目录
Write-Host "📁 准备项目目录..." -ForegroundColor Cyan
if (-Not (Test-Path "images")) {
    New-Item -ItemType Directory -Path "images" -Force | Out-Null
}

# 检查容器状态
Write-Host "🔄 检查现有容器..." -ForegroundColor Cyan
$runningContainer = docker ps -q --filter "name=Random-Pictures"
if ($runningContainer) {
    Write-Host "⚠️  停止现有容器..." -ForegroundColor Yellow
    docker stop Random-Pictures
    docker rm Random-Pictures
}

# 构建镜像
Write-Host "📦 构建Docker镜像..." -ForegroundColor Cyan
docker build -t random-pictures-api:latest .

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 镜像构建成功" -ForegroundColor Green
} else {
    Write-Host "❌ 镜像构建失败" -ForegroundColor Red
    exit 1
}

# 启动服务
Write-Host "🚀 启动服务..." -ForegroundColor Cyan
docker-compose up -d

# 等待服务启动
Write-Host "⏳ 等待服务启动（最长30秒）..." -ForegroundColor Cyan
$serviceStarted = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8081/" -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ 服务启动成功" -ForegroundColor Green
            $serviceStarted = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 1
}

# 最终验证
try {
    $categories = Invoke-RestMethod -Uri "http://localhost:8081/api/categories" -TimeoutSec 5
    Write-Host "🎉 随机图API安装完成！" -ForegroundColor Green
} catch {
    Write-Host "⚠️  服务启动中，可能需要更多时间..." -ForegroundColor Yellow
}

# 显示访问信息
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🌐 访问地址: http://localhost:8081" -ForegroundColor Green
Write-Host "📁 图片目录: .\images\" -ForegroundColor Green
Write-Host ""
Write-Host "📋 使用说明：" -ForegroundColor White
Write-Host "   1. 将图片放入 .\images\ 目录" -ForegroundColor Gray
Write-Host "   2. 支持格式: jpg, jpeg, png, gif, webp" -ForegroundColor Gray
Write-Host "   3. 每创建一个文件夹就是一个分类" -ForegroundColor Gray
Write-Host ""
Write-Host "🛠️  管理命令：" -ForegroundColor White
Write-Host "   - 重启服务: docker-compose restart" -ForegroundColor Gray
Write-Host "   - 停止服务: docker-compose down" -ForegroundColor Gray
Write-Host "   - 查看日志: docker logs Random-Pictures" -ForegroundColor Gray
Write-Host ""
Write-Host "?? 提示：添加图片后无需重启，网页会自动刷新" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
