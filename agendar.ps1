# Registra as duas tarefas no Agendador do Windows. Pode ser executado de novo: atualiza o que já existe.
#   Santos RPA:       roda o robô de hora em hora
#   Santos Dashboard: mantém http://localhost:8765 no ar a partir do login
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$python = Join-Path $raiz '.venv\Scripts\pythonw.exe'   # pythonw: não abre janela a cada execução
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited

$robo = New-ScheduledTaskAction -Execute $python -Argument 'rpa.py' -WorkingDirectory $raiz
$cadaHora = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours((Get-Date).Hour + 1) `
    -RepetitionInterval (New-TimeSpan -Hours 1)
$opcoesRobo = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'Santos RPA' -Action $robo -Trigger $cadaHora -Settings $opcoesRobo `
    -Principal $principal -Description 'Coleta notícias do Santos FC e atualiza o dashboard' -Force | Out-Null

$servidor = New-ScheduledTaskAction -Execute $python -Argument 'servidor.py' -WorkingDirectory $raiz
$noLogin = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$opcoesServidor = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Santos Dashboard' -Action $servidor -Trigger $noLogin -Settings $opcoesServidor `
    -Principal $principal -Description 'Serve o dashboard em http://localhost:8765' -Force | Out-Null
Start-ScheduledTask -TaskName 'Santos Dashboard'

Get-ScheduledTask -TaskName 'Santos RPA', 'Santos Dashboard' | Select-Object TaskName, State
