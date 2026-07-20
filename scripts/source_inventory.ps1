[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputPath = Join-Path $workspaceRoot "data\inventory\source-inventory.csv"
$outputDirectory = Split-Path -Parent $outputPath

$repositories = @{
    aerial = @{
        commit = "29f5870fd84b0176df48b40667c1b8f1740e6d09"
        raw_base = "https://raw.githubusercontent.com/NVIDIA/aerial-cuda-accelerated-ran"
    }
    oai = @{
        commit = "31ffb21a8204ae9706a88eb08606a80fc8eafb3e"
        raw_base = "https://raw.githubusercontent.com/duranta-project/openairinterface5g"
    }
    ocudu = @{
        commit = "6d44c2a5e5b2a81a4c67460b460ef99e789943cf"
        raw_base = "https://gitlab.com/ocudu/ocudu/-/raw"
    }
}

$evidenceFiles = @(
    @{ project = "aerial"; path = "cuPHY-CP/aerial-fh-driver/lib/fronthaul.cpp" },
    @{ project = "aerial"; path = "cuPHY-CP/cuphycontroller/src/cuphydriver.cpp" },
    @{ project = "aerial"; path = "cuPHY-CP/cuphydriver/src/downlink/phypdsch_aggr.cpp" },
    @{ project = "aerial"; path = "cuPHY-CP/cuphydriver/src/uplink/phypusch_aggr.cpp" },
    @{ project = "aerial"; path = "cuPHY/src/cuphy/crc/crc.cu" },
    @{ project = "aerial"; path = "cuMAC/src/4T4R/multiCellScheduler.cu" },
    @{ project = "aerial"; path = "cuMAC/src/64T64R/multiCellMuUeGrp.cu" },
    @{ project = "aerial"; path = "cuMAC-CP/src/cumac_cp_handler.cpp" },

    @{ project = "oai"; path = "executables/nr-softmodem.c" },
    @{ project = "oai"; path = "executables/nr-gnb.c" },
    @{ project = "oai"; path = "radio/fhi_72/oaioran.c" },
    @{ project = "oai"; path = "openair1/PHY/INIT/nr_init.c" },
    @{ project = "oai"; path = "openair1/SCHED_NR/phy_procedures_nr_gNB.c" },
    @{ project = "oai"; path = "openair2/LAYER2/NR_MAC_gNB/gNB_scheduler.c" },
    @{ project = "oai"; path = "openair2/F1AP/f1ap_du_task.c" },
    @{ project = "oai"; path = "openair2/RRC/NR/rrc_gNB.c" },

    @{ project = "ocudu"; path = "apps/gnb/gnb.cpp" },
    @{ project = "ocudu"; path = "lib/du/du_high/du_high_impl.cpp" },
    @{ project = "ocudu"; path = "lib/du/du_low/du_low_impl.cpp" },
    @{ project = "ocudu"; path = "lib/phy/upper/upper_phy_impl.cpp" },
    @{ project = "ocudu"; path = "lib/fapi_adaptor/mac/p7/mac_to_fapi_fastpath_translator.cpp" },
    @{ project = "ocudu"; path = "lib/fapi_adaptor/phy/p7/fapi_to_phy_fastpath_translator.cpp" },
    @{ project = "ocudu"; path = "lib/scheduler/cell_scheduler.cpp" },
    @{ project = "ocudu"; path = "lib/cu_cp/cu_cp_impl.cpp" }
)

function Get-Language([string] $extension) {
    switch ($extension.ToLowerInvariant()) {
        ".c" { return "C" }
        ".cc" { return "C++" }
        ".cpp" { return "C++" }
        ".cxx" { return "C++" }
        ".h" { return "C/C++ Header" }
        ".hpp" { return "C++ Header" }
        ".cu" { return "CUDA C++" }
        ".cuh" { return "CUDA C++ Header" }
        ".py" { return "Python" }
        ".m" { return "MATLAB" }
        default { return "Other" }
    }
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$headers = @{ "User-Agent" = "nr-aerial-research" }
$rows = foreach ($entry in $evidenceFiles) {
    $repository = $repositories[$entry.project]
    $commit = $repository.commit
    $sourceUrl = "$($repository.raw_base)/$commit/$($entry.path)"
    $temporaryFile = [System.IO.Path]::GetTempFileName()

    try {
        Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri $sourceUrl -OutFile $temporaryFile
        $file = Get-Item -LiteralPath $temporaryFile
        $extension = [System.IO.Path]::GetExtension($entry.path).ToLowerInvariant()
        [PSCustomObject]@{
            project = $entry.project
            path = $entry.path
            extension = $extension
            language = Get-Language $extension
            bytes = $file.Length
            sha256 = (Get-FileHash -LiteralPath $temporaryFile -Algorithm SHA256).Hash.ToLowerInvariant()
            commit = $commit
            source_url = $sourceUrl
            inventory_scope = "curated_architecture_evidence"
            retrieved_at = "2026-07-20"
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporaryFile) {
            Remove-Item -LiteralPath $temporaryFile -Force
        }
    }
}

$rows | Export-Csv -LiteralPath $outputPath -NoTypeInformation -Encoding UTF8
Write-Output "INVENTORY_OK $($rows.Count) files -> $outputPath"
