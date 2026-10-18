param(
    [string]$ModelDir = (Join-Path $PSScriptRoot "..\models\rq3")
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

$models = @(
    @{
        Key = "qwen3-8b-q4km"
        File = "Qwen3-8B-Q4_K_M.gguf"
        Url = "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf"
        Sha256 = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
    },
    @{
        Key = "ministral3-8b-q4km"
        File = "Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"
        Url = "https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF/resolve/main/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"
        Sha256 = "33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761"
    },
    @{
        Key = "gemma3-4b-q4km"
        File = "gemma-3-4b-it-Q4_K_M.gguf"
        Url = "https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf"
        Sha256 = "882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863"
    }
)

Write-Host "RQ3 model directory: $ModelDir"
foreach ($m in $models) {
    $path = Join-Path $ModelDir $m.File
    $needDownload = $true
    if (Test-Path $path) {
        $actual = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
        if ($actual -eq $m.Sha256) {
            Write-Host "OK existing: $($m.Key)  SHA256=$actual"
            $needDownload = $false
        } else {
            Write-Warning "Hash mismatch for existing $path; deleting and downloading frozen file."
            Remove-Item -Force $path
        }
    }
    if ($needDownload) {
        Write-Host "Downloading $($m.Key) ..."
        & curl.exe -L --fail --retry 3 --retry-delay 3 -o $path $m.Url
        if ($LASTEXITCODE -ne 0) { throw "Download failed for $($m.Key)" }
        $actual = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
        if ($actual -ne $m.Sha256) {
            Remove-Item -Force $path
            throw "SHA256 mismatch for $($m.Key). Expected $($m.Sha256), got $actual"
        }
        Write-Host "VERIFIED: $($m.Key)  SHA256=$actual"
    }
}

$hashFile = Join-Path $ModelDir "MODEL_HASHES.txt"
$lines = foreach ($m in $models) {
    $path = Join-Path $ModelDir $m.File
    $actual = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
    "$actual  $($m.File)"
}
$lines | Set-Content -Encoding ascii $hashFile
Write-Host ""
Write-Host "RQ3_MODELS_READY"
Write-Host "Hashes written to $hashFile"
