[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Invoke-ReadOnlyCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Read-only command failed: $Executable $($Arguments -join ' ')"
    }

    return ($output -join "`n").Trim()
}

$codexCommand = Get-Command codex -ErrorAction Stop
$codexVersion = Invoke-ReadOnlyCommand -Executable 'codex' -Arguments @('--version')
$featureLines = Invoke-ReadOnlyCommand -Executable 'codex' -Arguments @('features', 'list')
$featureNames = @(
    'artifact',
    'goals',
    'multi_agent',
    'multi_agent_v2',
    'plugins',
    'skill_search'
)

$relevantFeatures = foreach ($featureName in $featureNames) {
    $line = $featureLines -split "`r?`n" | Where-Object {
        $_ -match ('^' + [regex]::Escape($featureName) + '\s+')
    } | Select-Object -First 1

    if ($null -eq $line) {
        [ordered]@{
            name = $featureName
            stage = 'unknown'
            enabled = $false
            present = $false
        }
        continue
    }

    $match = [regex]::Match($line, '^\S+\s+(?<stage>.+?)\s+(?<enabled>true|false)$')
    [ordered]@{
        name = $featureName
        stage = $match.Groups['stage'].Value.Trim()
        enabled = $match.Groups['enabled'].Value -eq 'true'
        present = $true
    }
}

$appPackage = Get-AppxPackage | Where-Object { $_.Name -eq 'OpenAI.Codex' } | Select-Object -First 1
if ($null -eq $appPackage) {
    throw 'OpenAI.Codex AppX package was not found.'
}

$repoRoot = Invoke-ReadOnlyCommand -Executable 'git' -Arguments @('rev-parse', '--show-toplevel')
$repoBranch = Invoke-ReadOnlyCommand -Executable 'git' -Arguments @('branch', '--show-current')
$repoHead = Invoke-ReadOnlyCommand -Executable 'git' -Arguments @('rev-parse', 'HEAD')
$statusLines = @(& git status --porcelain=v1 --untracked-files=all 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw 'Read-only command failed: git status --porcelain=v1 --untracked-files=all'
}

$coreAutocrlf = & git config --get core.autocrlf 2>$null
if ($LASTEXITCODE -ne 0) {
    $coreAutocrlf = $null
}

$snapshot = [ordered]@{
    captured_at = [DateTimeOffset]::UtcNow.ToString('o')
    probe = [ordered]@{
        path = 'scripts/probe-codex-capabilities.ps1'
        mode = 'read-only-stdout'
        excluded = @(
            'Codex config content',
            'credential stores',
            'environment variable values',
            'task creation/fork/handoff/archive',
            'filesystem writes'
        )
    }
    os = [ordered]@{
        description = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
        architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    }
    shell = [ordered]@{
        name = 'Windows PowerShell'
        version = $PSVersionTable.PSVersion.ToString()
        edition = $PSVersionTable.PSEdition
    }
    codex = [ordered]@{
        app = [ordered]@{
            package_name = $appPackage.Name
            version = $appPackage.Version.ToString()
            architecture = $appPackage.Architecture.ToString()
        }
        cli = [ordered]@{
            version = $codexVersion
            path = $codexCommand.Source
        }
        relevant_feature_flags = @($relevantFeatures)
    }
    git = [ordered]@{
        version = Invoke-ReadOnlyCommand -Executable 'git' -Arguments @('--version')
        core_autocrlf = $coreAutocrlf
    }
    repository = [ordered]@{
        path = $repoRoot
        branch = $repoBranch
        head = $repoHead
        status = if ($statusLines.Count -eq 0) { 'clean' } else { 'dirty' }
        porcelain = @($statusLines | ForEach-Object { $_.ToString() })
    }
}

$snapshot | ConvertTo-Json -Depth 8
