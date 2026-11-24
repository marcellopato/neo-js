' Inicia o Neo Assistente (backend + escuta "Ei Neo") silenciosamente no Windows sem abrir tela preta
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)
pythonw = projectDir & "\venv\Scripts\pythonw.exe"

shell.CurrentDirectory = projectDir
shell.Run """" & pythonw & """ """ & projectDir & "\agent.py""", 0, False
WScript.Sleep 3000
shell.Run """" & pythonw & """ """ & projectDir & "\voice_listener.py""", 0, False
