param(
    [Parameter(Mandatory=$true)][string]$PiAddress,
    [switch]$Install
)
$ErrorActionPreference = 'Stop'
if ($PiAddress -notmatch '^[A-Za-z0-9][A-Za-z0-9_.@:-]*$') { throw 'Use an SSH user@host address without shell characters.' }
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$revision = (& git -C $repoRoot rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -notmatch '^[a-f0-9]{12}$') { throw 'Cannot resolve committed revision.' }
$dirty = & git -C $repoRoot status --porcelain
if ($dirty) { throw 'Commit or preserve local changes first; the archive contains HEAD only.' }
$archive = Join-Path ([IO.Path]::GetTempPath()) "canesight-lidar-$revision.tar"
& git -C $repoRoot archive --format=tar --output=$archive HEAD
if ($LASTEXITCODE -ne 0) { throw 'Archive creation failed.' }
& scp $archive "${PiAddress}:canesight-lidar-$revision.tar"
if ($LASTEXITCODE -ne 0) { throw 'Copy failed; no installation attempted.' }
& ssh $PiAddress "mkdir -p canesight-releases/$revision"
if ($LASTEXITCODE -ne 0) { throw 'Remote release folder failed.' }
& ssh $PiAddress "tar -xf canesight-lidar-$revision.tar -C canesight-releases/$revision"
if ($LASTEXITCODE -ne 0) { throw 'Remote extraction failed.' }
if ($Install) {
    & ssh -t $PiAddress "cd canesight-releases/$revision && python3 -m edge.install_lidar_service"
    if ($LASTEXITCODE -ne 0) { throw 'Installation failed; do not start the service until resolved.' }
}
Write-Output "Copied commit $revision without touching another checkout or any credentials."
Write-Output "Pi folder: ~/canesight-releases/$revision"
Write-Output 'No automated tests, service startup or hardware checks were requested by this copy.'
