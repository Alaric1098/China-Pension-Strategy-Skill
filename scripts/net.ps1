#Requires -Version 7.0
<#
.SYNOPSIS
    DSH 沙箱内可用的 HTTPS 请求包装器。

.DESCRIPTION
    DSH Windows 沙箱用受限令牌（ACL restricted-token runner）运行命令，受限令牌下
    Schannel（pwsh Invoke-WebRequest / curl.exe / .NET HttpClient）在 TLS 握手时
    报 SEC_E_NO_CREDENTIALS (0x8009030e)。OpenSSL 客户端（Python）不受影响。

    本模块优先尝试 Invoke-WebRequest；检测到 Schannel 凭据失败时自动回退到
    scripts/webget.py（Python/OpenSSL），使 pwsh 内的 HTTPS 请求在沙箱内可用。

.EXAMPLE
    . .\scripts\net.ps1
    $resp = Invoke-DshWebRequest "https://www.gov.cn"
    $markdown = Invoke-DshWebRequest "https://r.jina.ai/https://example.gov.cn" -Jina
#>

function Test-SchannelCredentialFailure {
    param([string]$Message)
    return $Message -match "SEC_E_NO_CREDENTIALS|0x8009030e|SSL connection could not be established|Authentication failed"
}

function Invoke-DshWebRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Uri,
        [switch]$Jina,
        [int]$TimeoutSec = 30
    )
    $scriptRoot = $PSScriptRoot
    $webget = Join-Path $scriptRoot "webget.py"

    # 1) Try native Invoke-WebRequest first (works under danger-full-access).
    try {
        $resp = Invoke-WebRequest -Uri $Uri -TimeoutSec $TimeoutSec -UseBasicParsing
        return $resp.Content
    } catch {
        $msg = $_.Exception.Message
        if ($_.Exception.InnerException) { $msg += " | " + $_.Exception.InnerException.Message }
        if (-not (Test-SchannelCredentialFailure $msg)) {
            # A non-Schannel failure is a real error, not the sandbox signature.
            throw $_
        }
        Write-Verbose "Schannel blocked ($msg); falling back to webget.py"
    }

    # 2) Fallback: OpenSSL-based fetch via Python (works under the restricted token).
    $cmd = @("$webget", $Uri, "--timeout", "$TimeoutSec")
    if ($Jina) { $cmd += "--jina" }
    $output = & python @cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "webget fallback failed (exit $LASTEXITCODE): $output"
    }
    return ($output -join "`n")
}

Export-ModuleMember -Function Invoke-DshWebRequest
