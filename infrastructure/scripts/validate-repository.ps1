[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-ProhibitedTrackedPath {
    param([string[]]$Paths)

    $directoryPattern = '(^|/)(node_modules|\.venv|venv|env|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|htmlcov|coverage|dist|build|target)(/|$)'
    $filePattern = '(^|/)(\.DS_Store|Thumbs\.db|desktop\.ini|.*\.py[co]|.*\.log|.*\.sqlite3?)$'
    $environmentPattern = '(^|/)\.env($|\.)'

    foreach ($path in $Paths) {
        $normalised = $path.Replace('\', '/')
        $isEnvironmentExample = $normalised -match '(^|/)\.env(\.[^/]*)?\.example$' -or $normalised -match '(^|/)\.env\.example$'

        if (
            $normalised -match $directoryPattern -or
            $normalised -match $filePattern -or
            ($normalised -match $environmentPattern -and -not $isEnvironmentExample)
        ) {
            $normalised
        }
    }
}

function Get-UnpinnedActionReference {
    param([string[]]$WorkflowPaths)

    foreach ($workflowPath in $WorkflowPaths) {
        $lineNumber = 0
        foreach ($line in Get-Content -LiteralPath $workflowPath) {
            $lineNumber++
            if ($line -notmatch '^\s*uses:\s*([^\s#]+)') {
                continue
            }

            $reference = $Matches[1]
            if ($reference.StartsWith('./')) {
                continue
            }

            if ($reference -notmatch '@[0-9a-fA-F]{40}$') {
                "${workflowPath}:${lineNumber}: $reference"
            }
        }
    }
}

function Assert-ControlledFailureTests {
    $prohibitedExamples = @(
        'node_modules/example/package.json',
        'backend/__pycache__/module.pyc',
        '.env',
        'frontend/dist/index.html'
    )
    $allowedExamples = @(
        '.env.example',
        'README.md',
        'frontend/src/example.ts'
    )

    $detected = @(Get-ProhibitedTrackedPath -Paths ($prohibitedExamples + $allowedExamples))
    foreach ($expected in $prohibitedExamples) {
        if ($expected -notin $detected) {
            throw "Repository-policy self-test did not reject: $expected"
        }
    }
    foreach ($allowed in $allowedExamples) {
        if ($allowed -in $detected) {
            throw "Repository-policy self-test incorrectly rejected: $allowed"
        }
    }

    $temporaryWorkflow = Join-Path ([System.IO.Path]::GetTempPath()) 'f2s-action-pin-self-test.yml'
    try {
        Set-Content -LiteralPath $temporaryWorkflow -Value '      uses: actions/checkout@v7'
        $unpinned = @(Get-UnpinnedActionReference -WorkflowPaths @($temporaryWorkflow))
        if ($unpinned.Count -ne 1) {
            throw 'Action-pin self-test did not reject a floating tag.'
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporaryWorkflow) {
            Remove-Item -LiteralPath $temporaryWorkflow -Force
        }
    }
}

Assert-ControlledFailureTests

$trackedPaths = @(git ls-files)
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to list tracked repository files.'
}

$prohibitedPaths = @(Get-ProhibitedTrackedPath -Paths $trackedPaths)
if ($prohibitedPaths.Count -gt 0) {
    Write-Error "Prohibited generated, environment, or local artifact files are tracked:`n$($prohibitedPaths -join "`n")"
}

$workflowPaths = @($trackedPaths | Where-Object { $_ -match '^\.github/workflows/.+\.ya?ml$' })
$unpinnedActions = @(Get-UnpinnedActionReference -WorkflowPaths $workflowPaths)
if ($unpinnedActions.Count -gt 0) {
    Write-Error "GitHub Actions must use full 40-character commit SHAs:`n$($unpinnedActions -join "`n")"
}

git check-ignore --quiet .env
if ($LASTEXITCODE -ne 0) {
    throw '.env must remain ignored by Git.'
}

Write-Output 'Repository policy: PASS'
