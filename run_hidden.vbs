Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "pythonw """ & sh.CurrentDirectory & "\kbu_wifi_keeper.py""", 0, False
