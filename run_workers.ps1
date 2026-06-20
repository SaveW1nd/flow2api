# 在 Windows 宿主机原生运行出图/出视频 Worker(无头 Chrome broker 获取 reCAPTCHA token,纯 HTTP 兜底)。
# 前提:postgres/redis/minio/backend 已用 docker compose 启动;已执行 setup_workers.ps1 建好 venv。
#
# 用法:  .\run_workers.ps1
# 说明:  会打开两个窗口,分别消费 image 与 video 队列(Windows 下用 solo 池最稳)。

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Error "未找到 venv,请先运行 .\setup_workers.ps1"
}

function Get-ConfigValue($Name, $Default) {
    $current = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($current)) {
        return $current
    }
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
        if ($line) {
            return ($line -replace "^\s*$Name\s*=", "").Trim()
        }
    }
    return $Default
}

# 连接 docker 暴露在 localhost 的服务(覆盖 .env 里的容器内主机名)
$envVars = @{
    POSTGRES_HOST       = "127.0.0.1"
    POSTGRES_PORT       = "15432"
    POSTGRES_USER       = "flow"
    POSTGRES_PASSWORD   = "flow_pass"
    POSTGRES_DB         = "flow2api"
    REDIS_HOST          = "127.0.0.1"
    REDIS_PORT          = "6379"
    REDIS_DB            = "0"
    S3_ENDPOINT         = "http://127.0.0.1:9000"
    S3_PUBLIC_ENDPOINT  = "http://localhost:9000"
    S3_ACCESS_KEY       = "minioadmin"
    S3_SECRET_KEY       = "minioadmin"
    S3_BUCKET           = "flow2api"
    FLOW_PROFILES_DIR   = (Join-Path $root "flow_profiles")
    FLOW_HEADLESS       = "true"
    FLOW_USE_CURL       = "true"
    # 本机 curl_cffi 支持的指纹版本(实测 chrome136 不支持)
    FLOW_IMPERSONATE    = "chrome124"
    # 全局默认代理:reCAPTCHA broker/协议请求与 HTTP 提交走同一代理->同一出口 IP(账号可在后台单独覆盖)。
    # 留空=直连。例:http://root:lichao@64.83.17.68:3002 或 socks5://root:lichao@64.83.17.68:3001
    FLOW_PROXY          = (Get-ConfigValue "FLOW_PROXY" "")
}
foreach ($k in $envVars.Keys) { [Environment]::SetEnvironmentVariable($k, $envVars[$k], "Process") }
New-Item -ItemType Directory -Force -Path $envVars["FLOW_PROFILES_DIR"] | Out-Null

$backend = Join-Path $root "backend"

Write-Host "[*] 启动 video 队列 Worker(新窗口)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backend'; & '$venvPy' -m celery -A app.workers.celery_app worker -Q video -P solo -n video@%computername% -l info"
)

Write-Host "[*] 启动 image 队列 Worker(当前窗口)..." -ForegroundColor Cyan
Set-Location $backend
& $venvPy -m celery -A app.workers.celery_app worker -Q image -P solo -n image@$env:COMPUTERNAME -l info
