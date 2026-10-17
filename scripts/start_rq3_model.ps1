param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("qwen3-8b-q4km","ministral3-8b-q4km","gemma3-4b-q4km")]
    [string]$Model,
    [int]$Port = 8080,
    [int]$ContextSize = 16384,
    [string]$ModelDir = (Join-Path $PSScriptRoot "..\models\rq3")
)

$ErrorActionPreference = "Stop"

$config = @{
    "qwen3-8b-q4km" = @{
        File = "Qwen3-8B-Q4_K_M.gguf"
        Sha256 = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
        ReasoningOff = $true
    }
    "ministral3-8b-q4km" = @{
        File = "Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"
        Sha256 = "33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761"
        ReasoningOff = $false
    }
    "gemma3-4b-q4km" = @{
        File = "gemma-3-4b-it-Q4_K_M.gguf"
        Sha256 = "882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863"
        ReasoningOff = $false
    }
}

$llama = Get-Command llama -ErrorAction SilentlyContinue
if (-not $llama) {
    throw "llama.cpp command 'llama' not found. Install with: winget install llama.cpp"
}

$m = $config[$Model]
$path = Join-Path $ModelDir $m.File
if (-not (Test-Path $path)) { throw "Missing model file: $path. Run scripts\setup_rq3_models.ps1 first." }
$actual = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
if ($actual -ne $m.Sha256) { throw "Model SHA256 mismatch. Expected $($m.Sha256), got $actual" }

Write-Host "Starting $Model"
Write-Host "MODEL_SHA256=$actual"
Write-Host "PORT=$Port CONTEXT=$ContextSize"
Write-Host "Leave this window open while running smoke/generation calls in another PowerShell window."

$argsList = @("serve", "-m", $path, "--host", "127.0.0.1", "--port", "$Port", "--ctx-size", "$ContextSize")
if ($m.ReasoningOff) {
    $argsList += @("--reasoning", "off")
}
& llama @argsList
