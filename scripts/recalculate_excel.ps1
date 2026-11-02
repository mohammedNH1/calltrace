# Recalculates a workbook with Microsoft Excel so that formula results are stored in the file.
# Usage: powershell -File scripts/recalculate_excel.ps1 -Path reports/research_survey.xlsx
param([Parameter(Mandatory = $true)][string]$Path)

$full = (Resolve-Path $Path).Path
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {
    $book = $excel.Workbooks.Open($full)
    $excel.CalculateFull()
    $book.Save()
    $book.Close($false)
    Write-Output "Recalculated $full"
}
finally {
    $excel.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}
