$base = 'http://localhost:25580'
$checks = @(
  @{Name='api_root';Method='GET';Path='/api/'},
  @{Name='schema_catalog';Method='GET';Path='/api/schema'},
  @{Name='schema_endpoints';Method='GET';Path='/api/schema/endpoints'},
  @{Name='schema_realtime';Method='GET';Path='/api/schema/realtime_data'},
  @{Name='schema_planning_file';Method='GET';Path='/api/schema/planning_file'},
  @{Name='schema_update';Method='GET';Path='/api/schema/update'},
  @{Name='health';Method='GET';Path='/api/health'},
  @{Name='realtime';Method='GET';Path='/api/realtime/data'},
  @{Name='planning_files';Method='GET';Path='/api/planningdata/files'},
  @{Name='planning_index';Method='GET';Path='/api/planningdata/data'},
  @{Name='planning_stops';Method='GET';Path='/api/planningdata/stops?limit=5'},
  @{Name='planning_routes';Method='GET';Path='/api/planningdata/routes?limit=5'},
  @{Name='planning_calendar';Method='GET';Path='/api/planningdata/calendar?limit=5'},
  @{Name='planning_trips';Method='GET';Path='/api/planningdata/trips?limit=5'},
  @{Name='planning_stop_times';Method='GET';Path='/api/planningdata/stop_times?limit=5'},
  @{Name='planning_calendar_dates';Method='GET';Path='/api/planningdata/calendar_dates?limit=5'},
  @{Name='planning_agency';Method='GET';Path='/api/planningdata/agency?limit=5'},
  @{Name='planning_translations';Method='GET';Path='/api/planningdata/translations?limit=5'},
  @{Name='cache_index';Method='GET';Path='/api/cache'},
  @{Name='cache_realtime';Method='GET';Path='/api/cache/realtime'},
  @{Name='deprecated_data';Method='GET';Path='/api/data'},
  @{Name='security_audit';Method='GET';Path='/api/security/audit'},
  @{Name='trajectories';Method='GET';Path='/api/trajectories?limit=5'},
  @{Name='update';Method='POST';Path='/api/update';Body='{"force":true,"update_type":"realtime"}';ContentType='application/json'},
  @{Name='metrics';Method='GET';Path='/metrics';ExpectJson=$false}
)

function Invoke-EndpointCheck($check) {
  $url = "$base$($check.Path)"
  $method = $check.Method
  $status = $null
  $content = ''

  try {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = $method
    $req.Timeout = 45000

    if ($check.ContainsKey('ContentType')) { $req.ContentType = $check.ContentType }
    if ($check.ContainsKey('Body')) {
      $bytes = [System.Text.Encoding]::UTF8.GetBytes($check.Body)
      $req.ContentLength = $bytes.Length
      $stream = $req.GetRequestStream()
      $stream.Write($bytes, 0, $bytes.Length)
      $stream.Close()
    }

    $resp = $req.GetResponse()
    $status = [int]$resp.StatusCode
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $content = $reader.ReadToEnd()
    $reader.Close()
    $resp.Close()
  }
  catch [System.Net.WebException] {
    if ($null -ne $_.Exception.Response) {
      $resp = $_.Exception.Response
      $status = [int]$resp.StatusCode
      $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $content = $reader.ReadToEnd()
      $reader.Close()
      $resp.Close()
    }
    else {
      $status = -1
      $content = $_.Exception.Message
    }
  }

  $jsonValid = $false
  if ($check.ContainsKey('ExpectJson') -and ($check.ExpectJson -eq $false)) {
    $jsonValid = 'n/a'
  }
  else {
    try {
      $null = $content | ConvertFrom-Json -ErrorAction Stop
      $jsonValid = $true
    }
    catch {
      $jsonValid = $false
    }
  }

  [PSCustomObject]@{
    Name = $check.Name
    Method = $method
    Status = $status
    Json = $jsonValid
  }
}

$results = foreach ($c in $checks) { Invoke-EndpointCheck $c }
$results | Format-Table -AutoSize
