param(
    [switch]$Force,
    [switch]$Refresh,
    [switch]$ShowVersion,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$REPO_ZIP_URL = "https://github.com/awslabs/aidlc-workflows/archive/refs/heads/main.zip"
$PATCH_URL = "https://raw.githubusercontent.com/ashisha7i/homebrew-formulae/refs/heads/main/aidlc-setup-patch/custom-patch.md"
$ScriptVersion = "1.0.16"

if ($ShowVersion) {
    Write-Output $ScriptVersion
    exit 0
}

if ($Help) {
    Write-Output @"
aidlc-setup: install AI-DLC rules for Cline in the current directory

Creates:
  .clinerules/core-workflow.md
  .aidlc-rule-details/*

Options:
  -Refresh       re-download latest rules
  -Force         overwrite existing files
  -ShowVersion   show version
  -Help          show help
"@
    exit 0
}

# Cache dir
$CACHE_DIR = if ($env:XDG_CACHE_HOME) {
    Join-Path $env:XDG_CACHE_HOME "aidlc-workflows"
} else {
    Join-Path $HOME ".cache/aidlc-workflows"
}

$ZIP_PATH = Join-Path $CACHE_DIR "main.zip"
$EXTRACT_DIR = Join-Path $CACHE_DIR "main"
$PATCH_PATH = Join-Path $CACHE_DIR "custom-patch.md"

New-Item -ItemType Directory -Force -Path $CACHE_DIR | Out-Null

function Download-If-Needed {
    if ($Refresh -or !(Test-Path $ZIP_PATH)) {
        Write-Output "Downloading aidlc workflows..."
        Invoke-WebRequest $REPO_ZIP_URL -OutFile $ZIP_PATH
    }
}

function Download-Patch-If-Needed {
    if ($Refresh -or !(Test-Path $PATCH_PATH)) {
        Write-Output "Downloading custom patch..."
        Invoke-WebRequest $PATCH_URL -OutFile $PATCH_PATH
    }
}

function Extract-If-Needed {
    if ($Refresh -or !(Test-Path $EXTRACT_DIR)) {
        Write-Output "Extracting rules..."
        Remove-Item $EXTRACT_DIR -Recurse -Force -ErrorAction SilentlyContinue
        Expand-Archive -Path $ZIP_PATH -DestinationPath $EXTRACT_DIR -Force
    }
}

Download-If-Needed
Download-Patch-If-Needed
Extract-If-Needed

# Find root
$ROOT = Get-ChildItem $EXTRACT_DIR -Directory -Filter "aidlc-workflows-*" | Select-Object -First 1
if (-not $ROOT) {
    Write-Error "ERROR: extraction failed"
}

$RULES_ROOT = Join-Path $ROOT.FullName "aidlc-rules"
$RULES_DIR = Join-Path $RULES_ROOT "aws-aidlc-rules"
$DETAILS_DIR = Join-Path $RULES_ROOT "aws-aidlc-rule-details"
$CORE = Join-Path $RULES_DIR "core-workflow.md"

if (!(Test-Path $CORE)) {
    Write-Error "ERROR: core-workflow.md missing"
}

if (!(Test-Path $PATCH_PATH)) {
    Write-Error "ERROR: custom patch missing"
}

New-Item -ItemType Directory -Force -Path ".clinerules" | Out-Null
New-Item -ItemType Directory -Force -Path ".aidlc-rule-details" | Out-Null

if ((Test-Path ".clinerules/core-workflow.md") -and -not $Force) {
    Write-Error "ERROR: .clinerules/core-workflow.md exists (use -Force)"
}

if ((Get-ChildItem ".aidlc-rule-details" -ErrorAction SilentlyContinue) -and -not $Force) {
    Write-Error "ERROR: .aidlc-rule-details not empty (use -Force)"
}

Write-Output "Applying patch and creating core-workflow.md..."

$coreLines = Get-Content $CORE
$patchLines = Get-Content $PATCH_PATH

$out = @()
for ($i = 0; $i -lt $coreLines.Length; $i++) {
    if ($i -eq 2) { $out += $patchLines }
    $out += $coreLines[$i]
}

$out | Set-Content ".clinerules/core-workflow.md"

Remove-Item ".aidlc-rule-details\*" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$DETAILS_DIR\*" ".aidlc-rule-details\" -Recurse

Write-Output ""
Write-Output "AI-DLC Cline rules installed:"
Write-Output "  .clinerules/core-workflow.md (patched)"
Write-Output "  .aidlc-rule-details/*"
