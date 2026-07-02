$dirs = @('-17cea024','-2848cd38','-30aaf809','-6b75b126','-7fbeca6b','5264be2a','6ad52f56','7b5a7aaf')
foreach ($d in $dirs) {
    $p = "$env:APPDATA\Code\User\History\$d\entries.json"
    $j = Get-Content $p -Raw | ConvertFrom-Json
    Write-Host "=== $d ===" $j.resource
}
