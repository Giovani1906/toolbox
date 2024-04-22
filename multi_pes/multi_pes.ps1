#Requires -RunAsAdministrator
Write-Output "A PowerShell script that allows a version of PES to be ran multiple times.`nPES can be launched again after a new line appears down bellow."
while (1){
    ForEach($pes_process in Get-Process -Name "PES*") {
        if($pes_process.mainWindowTitle -like "Pro Evolution Soccer*" -or "eFootball PES*") {
            $handle = .\handle\handle.exe -p $pes_process.Id -a -nobanner "boot"
            if($handle -ne "No matching handles found.") {
                if($handle -match ".*Mutant\s*(\w{2,}): \\.*\sBoot") {
                    $mutex = .\handle\handle.exe -p $pes_process.Id -nobanner -c $Matches.Item(1) -y
                    if($mutex -eq "Handle closed.") {
                        Write-Output "`"$($pes_process.Name).exe (PID: $($pes_process.Id))`" has been modified to allow another window to be launched."
                    }
                    else {
                        Write-Output "Something happened.`n`nError:`n$mutex"
                    }
                }
            }
        }
    }
    Start-Sleep 5
}
