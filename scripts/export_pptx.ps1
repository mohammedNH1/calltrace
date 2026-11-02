# Exports a presentation to PDF and per-slide PNG images with Microsoft PowerPoint.
# Usage: powershell -File scripts/export_pptx.ps1 -Path reports/calltrace_presentation.pptx -ImageDir <folder>
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$ImageDir = ""
)

$full = (Resolve-Path $Path).Path
$pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
$powerpoint = New-Object -ComObject PowerPoint.Application
try {
    $deck = $powerpoint.Presentations.Open($full, $true, $false, $false)
    $deck.SaveAs($pdf, 32)  # 32 = PDF
    if ($ImageDir) {
        New-Item -ItemType Directory -Force -Path $ImageDir | Out-Null
        foreach ($slide in $deck.Slides) {
            $slide.Export((Join-Path (Resolve-Path $ImageDir).Path ("slide-{0:d2}.png" -f $slide.SlideIndex)), "PNG", 1600, 900)
        }
    }
    $deck.Close()
    Write-Output "Exported $pdf"
}
finally {
    $powerpoint.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerpoint) | Out-Null
}
