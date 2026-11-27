param(
    [Parameter(Mandatory=$true)][string]$NativeStateFile,
    [Parameter(Mandatory=$true)][string]$SaveFile,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$ExpectedInstance
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

# SaveWorld must have completed before invoking this read-only capture. This
# script never sends game commands, changes a save or activates enforcement.
function Read-NativeCheckpoint {
    $state=Get-Content -LiteralPath $NativeStateFile -Raw -Encoding UTF8|ConvertFrom-Json
    if($state.instance -ne $ExpectedInstance){throw 'Native state belongs to another instance'}
    $runGuid=[guid]::Empty
    if(![guid]::TryParse([string]$state.run_id,[ref]$runGuid) -or $runGuid -eq [guid]::Empty){throw 'Native run identity unavailable; requires 0.9.4+'}
    if(!$state.runtime_healthy -or !$state.journal_healthy -or !$state.journal_state_revision_match -or
       $null -eq $state.inventory_revision -or $state.inventory_revision -ne $state.journal_applied_revision -or
       !$state.reconciliation.live_checkpoint_consistent){throw 'Native ledger is not a consistent checkpoint'}
    $age=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[long]$state.updated_at_unix
    if($age -lt 0 -or $age -gt 90){throw 'Native state timestamp is stale or in the future'}
    return $state
}

$savePath=[IO.Path]::GetFullPath($SaveFile)
$outputPath=[IO.Path]::GetFullPath($OutputDirectory)
if([IO.Path]::GetExtension($savePath) -ne '.ark'){throw 'An ASE world .ark file is required'}
if(Test-Path -LiteralPath $outputPath){throw 'Output directory must be new; existing checkpoints are never overwritten'}
$before=Read-NativeCheckpoint
$savedRoot=Join-Path ([IO.Path]::GetFullPath([string]$before.canonical_instance_path)) 'ShooterGame\Saved'
if(!$savePath.StartsWith($savedRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Save path is outside the native instance Saved directory'}
if($outputPath.StartsWith($savedRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Checkpoint output must be outside the live Saved directory'}
$beforeFile=Get-Item -LiteralPath $savePath
$beforeHash=(Get-FileHash -LiteralPath $savePath -Algorithm SHA256).Hash
New-Item -ItemType Directory -Path $outputPath|Out-Null
$copyPath=Join-Path $outputPath 'world.ark'
Copy-Item -LiteralPath $savePath -Destination $copyPath
$copyHash=(Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash
$afterHash=(Get-FileHash -LiteralPath $savePath -Algorithm SHA256).Hash
$afterFile=Get-Item -LiteralPath $savePath
$after=Read-NativeCheckpoint
if($beforeHash -ne $copyHash -or $beforeHash -ne $afterHash -or
   $beforeFile.Length -ne $afterFile.Length -or $beforeFile.LastWriteTimeUtc -ne $afterFile.LastWriteTimeUtc){
    throw 'Save changed during capture; partial output is not a verified checkpoint'
}
if($before.run_id -ne $after.run_id -or $before.inventory_revision -ne $after.inventory_revision){
    throw 'Native run/revision changed during capture; partial output is not verified'
}
# The JSON written is exactly the verified state, never a fresh unverified read.
$encoding=[Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $outputPath 'live.json'),($after|ConvertTo-Json -Depth 30),$encoding)
$manifest=[ordered]@{
    source=$savePath;instance=$after.instance;run_id=$after.run_id;inventory_revision=$after.inventory_revision
    sha256=$copyHash.ToLowerInvariant();save_bytes=$afterFile.Length
    save_modified_utc=$afterFile.LastWriteTimeUtc.ToString('o');copied_at_utc=[DateTime]::UtcNow.ToString('o')
    collection_state='hash_and_native_revision_verified_live_copy'
}
[IO.File]::WriteAllText((Join-Path $outputPath 'manifest.json'),($manifest|ConvertTo-Json -Depth 5),$encoding)
[pscustomobject]@{verified_copy=$true;instance=$after.instance;run_id=$after.run_id
    inventory_revision=$after.inventory_revision;observed_structures=$after.observed_structures
    save_bytes=$afterFile.Length;complete_inventory=$false;enforcement=$false}|ConvertTo-Json -Compress
