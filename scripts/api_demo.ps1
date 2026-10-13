<#
.SYNOPSIS
    Zeigt die REST-API des Rechnungs-Assistenten in vier Schritten (GET, POST, PUT).

.DESCRIPTION
    Der Server muss laufen (start_windows.bat). Das Skript liest die Rechnungen,
    versucht eine fehlerhafte Rechnung freizugeben (die API lehnt mit 409 ab),
    korrigiert sie per PUT und gibt sie danach frei. Jeder Aufruf wird mit Methode,
    Adresse und HTTP-Status angezeigt.

.PARAMETER Neu
    Leert vorher die Liste und verarbeitet die Musterrechnungen neu (für eine saubere Vorführung).

.EXAMPLE
    pwsh -File scripts\api_demo.ps1 -Neu
#>
param(
    [string]$Basis = 'http://localhost:8000/api',
    [switch]$Neu
)

$ErrorActionPreference = 'Stop'

function Invoke-Api {
    param([string]$Methode, [string]$Pfad, $Json, $Formular)
    $parameter = @{ Uri = "$Basis$Pfad"; Method = $Methode; UseBasicParsing = $true }
    if ($null -ne $Json) {
        $parameter.ContentType = 'application/json; charset=utf-8'
        $parameter.Body = [Text.Encoding]::UTF8.GetBytes(($Json | ConvertTo-Json -Depth 5))
    }
    if ($null -ne $Formular) { $parameter.Body = $Formular }
    try {
        $antwort = Invoke-WebRequest @parameter
        $text = [Text.Encoding]::UTF8.GetString($antwort.RawContentStream.ToArray())
        Write-Host ("  {0,-6} {1,-34} -> {2}" -f $Methode, $Pfad, [int]$antwort.StatusCode) -ForegroundColor Green
        return ($text | ConvertFrom-Json)
    }
    catch {
        $code = [int]$_.Exception.Response.StatusCode
        if (-not $code) {
            Write-Host "  Server nicht erreichbar unter $Basis. Bitte zuerst start_windows.bat starten." -ForegroundColor Red
            exit 1
        }
        $detail = try { ($_.ErrorDetails.Message | ConvertFrom-Json).detail } catch { $_.ErrorDetails.Message }
        Write-Host ("  {0,-6} {1,-34} -> {2}" -f $Methode, $Pfad, $code) -ForegroundColor Red
        Write-Host "         Antwort: $detail" -ForegroundColor Red
        return $null
    }
}

Write-Host "`nREST-API des Rechnungs-Assistenten ($Basis)`n" -ForegroundColor White

if ($Neu) {
    $null = Invoke-Api DELETE '/rechnungen'
    $null = Invoke-Api POST '/beispiele' -Formular @{ modus = 'regeln' }
}

Write-Host "`n1. Rechnungen lesen (GET)" -ForegroundColor Cyan
$liste = @(Invoke-Api GET '/rechnungen')
$liste | Select-Object id, lieferant, brutto, status | Format-Table -AutoSize | Out-String -Width 120 | Write-Host

$ziel = $liste | Where-Object { $_.status -eq 'fehler' -and ($_.pruefung | Where-Object { $_.regel -eq 'Summe' -and $_.status -eq 'fehler' }) } | Select-Object -First 1
if (-not $ziel) {
    Write-Host 'Keine Rechnung mit Rechenfehler gefunden. Mit -Neu starten, um die Musterrechnungen neu zu laden.' -ForegroundColor Yellow
    return
}

Write-Host "2. Fehlerhafte Rechnung $($ziel.rechnungsnummer) freigeben (POST): die API muss ablehnen" -ForegroundColor Cyan
$null = Invoke-Api POST "/rechnungen/$($ziel.id)/freigabe" -Json @{ freigegeben = $true }

Write-Host "`n3. Bruttobetrag korrigieren (PUT): alle Prüfregeln laufen erneut" -ForegroundColor Cyan
$korrektur = [ordered]@{}
foreach ($feld in 'lieferant', 'rechnungsnummer', 'rechnungsdatum', 'netto', 'mwst_satz', 'mwst_betrag', 'iban') { $korrektur[$feld] = $ziel.$feld }
$korrektur.brutto = [math]::Round($ziel.netto + $ziel.mwst_betrag, 2)
Write-Host "         Brutto $($ziel.brutto) -> $($korrektur.brutto)"
$korrigiert = Invoke-Api PUT "/rechnungen/$($ziel.id)" -Json $korrektur
Write-Host "         Neuer Status: $($korrigiert.status)"

Write-Host "`n4. Erneut freigeben (POST)" -ForegroundColor Cyan
$frei = Invoke-Api POST "/rechnungen/$($ziel.id)/freigabe" -Json @{ freigegeben = $true }
Write-Host "         Freigegeben: $($frei.freigegeben)"
Write-Host "`nDie Oberfläche im Browser zeigt die Änderung nach dem Neuladen (F5).`n" -ForegroundColor Gray
