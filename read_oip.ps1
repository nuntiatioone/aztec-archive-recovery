$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$lib=Join-Path $root '.local/sqlce/lib/net40'
$native=Join-Path $root '.local/sqlce/NativeBinaries/amd64'
$env:PATH="$native;$(Join-Path $native 'Microsoft.VC90.CRT');$env:PATH"
if(-not (Test-Path -LiteralPath (Join-Path $lib 'amd64/sqlceme40.dll'))) {
    Copy-Item -LiteralPath $native -Destination (Join-Path $lib 'amd64') -Recurse -Force
}
Add-Type -Path (Join-Path $lib 'System.Data.SqlServerCe.dll')
$source=Join-Path $root '.local/NbTaTi_EDX_Data.oip'
$copy=Join-Path $root '.local/working.sdf'
Copy-Item -LiteralPath $source -Destination $copy -Force
$engine=New-Object System.Data.SqlServerCe.SqlCeEngine("Data Source=$copy")
$engine.Upgrade()
$engine.Dispose()
$conn=New-Object System.Data.SqlServerCe.SqlCeConnection("Data Source=$copy;Mode=Read Only;Temp Path=$(Join-Path $root '.local')")
$conn.Open()
$cmd=$conn.CreateCommand()
$cmd.CommandText='SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS'
$r=$cmd.ExecuteReader()
$schema=@()
while($r.Read()) { $schema += [ordered]@{table=$r.GetString(0);column=$r.GetString(1);type=$r.GetString(2)} }
$r.Close()
$schema | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $root 'database-schema.json') -Encoding UTF8
$export=Join-Path $root '.local/tables'; New-Item -ItemType Directory -Path $export -Force | Out-Null
Add-Type -AssemblyName System.Runtime.Serialization
foreach($table in ($schema.table | Select-Object -Unique)) {
  $cmd.CommandText="SELECT * FROM [$table]"
  $r=$cmd.ExecuteReader(); $rows=@(); $rownum=0
  while($r.Read()) {
    $row=[ordered]@{}; $rownum++
    for($i=0;$i -lt $r.FieldCount;$i++) {
      $name=$r.GetName($i); $v=$r.GetValue($i)
      if($v -is [DBNull]) {$row[$name]=$null}
      elseif($v -is [byte[]]) {
        $stem="$table-$rownum-$name"
        [IO.File]::WriteAllBytes((Join-Path $export "$stem.bin"),$v)
        $row[$name]=[ordered]@{file="$stem.bin";bytes=$v.Length}
        try {
          $xr=[System.Xml.XmlDictionaryReader]::CreateBinaryReader($v,[System.Xml.XmlDictionaryReaderQuotas]::Max)
          $xml=New-Object System.Xml.XmlDocument; $xml.XmlResolver=$null; $xml.Load($xr); $xr.Close()
          $xml.Save((Join-Path $export "$stem.xml"));$row[$name]['xml']="$stem.xml"
        } catch { $row[$name]['xml_error']=$_.Exception.Message }
      } elseif($v -is [Guid]) {$row[$name]=$v.ToString()}
      else {$row[$name]=$v}
    }
    $rows+=,$row
  }
  $r.Close()
  ConvertTo-Json -InputObject @($rows) -Depth 20 | Set-Content (Join-Path $export "$table.json") -Encoding UTF8
  Write-Output "$table rows=$rownum"
}
$conn.Close()
