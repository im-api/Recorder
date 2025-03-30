#Requires AutoHotkey v2.0+
;#NoTrayIcon
#SingleInstance Off
Thread("NoTimers")
CoordMode("ToolTip")
SetTitleMatchMode(2)
DetectHiddenWindows(true)
;--------------------------

; Get the script's directory
ScriptDir := A_ScriptDir

; Find the next available file number
NextFileNumber := 1
Loop {
  if (!FileExist(ScriptDir "\" NextFileNumber ".txt"))
    break
  NextFileNumber++
}

if (A_Args.Length < 1) {
  A_Args.Push(NextFileNumber ".txt")
}

if (A_Args.Length < 2) {
  A_Args.Push("F6")
}

; Use script directory instead of temp folder
LogFile := ScriptDir "\" A_Args[1]
; Initialize LogArr as an array at the global scope
global LogArr := []
UpdateSettings
Recording := false
Playing := false
ActionKey := A_Args[2]
MouseMoveTimer := 0  ; Initialize the timer variable

Hotkey(ActionKey, KeyAction)
return

ShowTip(s := "", pos := "y35", color := "Red|00FFFF") {
  static bak := "", idx := 0, ShowTip := Gui(), RecordingControl
  if (bak = color "," pos "," s)
    return
  bak := color "," pos "," s
  SetTimer(ShowTip_ChangeColor, 0)
  ShowTip.Destroy()
  if (s = "")
    return

  ShowTip := Gui("+LastFound +AlwaysOnTop +ToolWindow -Caption +E0x08000020", "ShowTip")
  WinSetTransColor("FFFFF0 150")
  ShowTip.BackColor := "cFFFFF0"
  ShowTip.MarginX := 10
  ShowTip.MarginY := 5
  ShowTip.SetFont("q3 s20 bold cRed")
  RecordingControl := ShowTip.Add("Text", , s)
  ShowTip.Show("NA " . pos)
  SetTimer(ShowTip_ChangeColor, 1000)

  ShowTip_ChangeColor() {
    r := StrSplit(SubStr(bak, 1, InStr(bak, ",") - 1), "|")
    RecordingControl.SetFont("q3 c" r[idx := Mod(Round(idx), r.Length) + 1])
    return
  }
}

;============ Hotkey =============

KeyAction(HotkeyName) {
  if (Recording) {
    Stop
    return
  }

  KeyDown := A_TickCount
  loop {
    Duration := A_TickCount - KeyDown
    if (Duration < 400) {
      ShowTip
      if (!GetKeyState(ActionKey)) {
        ShowTip
        RecordKeyAction
        break
      }
    } else if (Duration < 1400) {
      ShowTip("RECORD")
      if (!GetKeyState(ActionKey)) {
        ShowTip
        RecordKeyAction
        break
      }
    } else {
      ShowTip("SHOW SOURCE")
      if (!GetKeyState(ActionKey)) {
        ShowTip
        EditKeyAction
        break
      }
    }
  }
}

RecordKeyAction() {
  if (Recording) {
    Stop()
    return
  }
  #SuspendExempt
  RecordScreen()
}

RecordScreen() {
  global LogArr, oldid, Recording, RelativeX, RelativeY, LastMouseX, LastMouseY, MouseMoveTimer

  if (Recording || Playing)
    return
  UpdateSettings()
  ; Reset LogArr to an empty array
  LogArr := []
  oldid := ""
  Recording := false
  LastMouseX := 0
  LastMouseY := 0
  
  ; Call Log without parameters to initialize
  Log()
  Recording := true
  SetHotkey(1)
  CoordMode("Mouse", "Screen")
  MouseGetPos(&RelativeX, &RelativeY)
  LastMouseX := RelativeX
  LastMouseY := RelativeY
  
  ; Set up a timer to track mouse movements
  MouseMoveTimer := SetTimer(TrackMouseMovement, 50)
  
  ShowTip("Recording")
  return
}

; Function to track mouse movements
TrackMouseMovement() {
  global LastMouseX, LastMouseY, MouseMode
  
  CoordMode("Mouse", "Screen")
  MouseGetPos(&CurrentX, &CurrentY)
  
  ; Only log if mouse has moved significantly
  if (Abs(CurrentX - LastMouseX) > 5 || Abs(CurrentY - LastMouseY) > 5) {
    ; Log mouse movement as simple string without Format()
    if (MouseMode == "screen") {
      Log("MouseMove " CurrentX " " CurrentY " screen")
    }
    else if (MouseMode == "window") {
      Log("MouseMove " CurrentX " " CurrentY " window")
    }
    else if (MouseMode == "relative") {
      Log("MouseMove " (CurrentX - RelativeX) " " (CurrentY - RelativeY) " relative")
    }
    
    LastMouseX := CurrentX
    LastMouseY := CurrentY
  }
}

UpdateSettings() {
  global MouseMode, RecordSleep
  if (FileExist(LogFile)) {
    LogFileObject := FileOpen(LogFile, "r")

    Loop 3 {
      LogFileObject.ReadLine()
    }
    MouseMode := RegExReplace(LogFileObject.ReadLine(), ".*=")

    LogFileObject.ReadLine()
    RecordSleep := RegExReplace(LogFileObject.ReadLine(), ".*=")

    LogFileObject.Close()
  } else {
    MouseMode := "screen"
    RecordSleep := "true" ; Changed default to true to record all sleeps
  }

  if (MouseMode != "screen" && MouseMode != "window" && MouseMode != "relative")
    MouseMode := "screen"

  if (RecordSleep != "true" && RecordSleep != "false")
    RecordSleep := "true" ; Changed default to true
}

Stop() {
  global LogArr, Recording, isPaused, NextFileNumber, ScriptDir, MouseMode, MouseMoveTimer
  #SuspendExempt
  if (Recording) {
    ; Stop the mouse movement tracking timer - check if it's valid first
    if (MouseMoveTimer) {
      SetTimer(MouseMoveTimer, 0)
    }
    
    if (IsObject(LogArr) && LogArr.Length > 0) {
      UpdateSettings()
      
      ; New format for saving recordings
      s := ""
      
      For k, v in LogArr {
        ; Convert the AHK v2 format to the requested format
        if (InStr(v, "Sleep(")) {
          ; Convert Sleep(123) to Sleep, 123
          sleepTime := RegExReplace(v, "Sleep\((\d+)\)", "$1")
          s .= "Sleep, " sleepTime "`n"
        } 
        else if (InStr(v, "MouseClick(")) {
          ; Convert MouseClick("L", 123, 456,,, "D") to Click, 123, 456 Left, , Down
          if (InStr(v, "screen") && MouseMode == "screen") {
            ; Fixed regex pattern to properly extract button and state
            if (InStr(v, "`"D`"")) {
              upDown := "Down"
            } else if (InStr(v, "`"U`"")) {
              upDown := "Up"
            } else {
              upDown := ""
            }
            
            ; Extract button type and coordinates
            mouseCmd := RegExReplace(v, ".*MouseClick\(`"(.)`", (\d+), (\d+).*", "$1,$2,$3")
            parts := StrSplit(mouseCmd, ",")
            button := parts[1] == "L" ? "Left" : (parts[1] == "R" ? "Right" : (parts[1] == "M" ? "Middle" : parts[1]))
            x := parts[2]
            y := parts[3]
            
            s .= "Click, " x ", " y " " button ", , " upDown "`n"
          }
          else if (InStr(v, "window") && MouseMode == "window") {
            ; Fixed regex pattern for window mode
            if (InStr(v, "`"D`"")) {
              upDown := "Down"
            } else if (InStr(v, "`"U`"")) {
              upDown := "Up"
            } else {
              upDown := ""
            }
            
            mouseCmd := RegExReplace(v, ".*MouseClick\(`"(.)`", (\d+), (\d+).*", "$1,$2,$3")
            parts := StrSplit(mouseCmd, ",")
            button := parts[1] == "L" ? "Left" : (parts[1] == "R" ? "Right" : (parts[1] == "M" ? "Middle" : parts[1]))
            x := parts[2]
            y := parts[3]
            
            s .= "Click, " x ", " y " " button ", , " upDown "`n"
          }
          else if (InStr(v, "relative") && MouseMode == "relative") {
            ; Fixed regex pattern for relative mode
            if (InStr(v, "`"D`"")) {
              upDown := "Down"
            } else if (InStr(v, "`"U`"")) {
              upDown := "Up"
            } else {
              upDown := ""
            }
            
            mouseCmd := RegExReplace(v, ".*MouseClick\(`"(.)`", (\d+), (\d+).*", "$1,$2,$3")
            parts := StrSplit(mouseCmd, ",")
            button := parts[1] == "L" ? "Left" : (parts[1] == "R" ? "Right" : (parts[1] == "M" ? "Middle" : parts[1]))
            x := parts[2]
            y := parts[3]
            
            s .= "Click, " x ", " y ", 0`n" ; Relative clicks with 0
          }
        }
        else if (InStr(v, "MouseMove")) {
          ; Convert MouseMove 123 456 screen to Click, 123, 456, 0
          mouseMove := RegExReplace(v, ".*MouseMove (\d+) (\d+).*", "$1,$2")
          parts := StrSplit(mouseMove, ",")
          x := parts[1]
          y := parts[2]
          
          s .= "Click, " x ", " y ", 0`n" ; Format mouse moves as clicks with 0
        }
        else if (InStr(v, "Send")) {
          ; Convert Send("{Blind}{6 Down}") to Send, {6 Down}
          keyCmd := RegExReplace(v, "Send `"\{Blind\}(.*)`"", "$1")
          
          ; Check if it's already a Down/Up command
          if (InStr(keyCmd, " Down}") || InStr(keyCmd, " Up}")) {
            s .= "Send, " keyCmd "`n"
          } 
          else {
            ; For single key presses, convert to Down/Up format
            ; Remove any existing braces
            keyCmd := RegExReplace(keyCmd, "[\{\}]", "")
            
            ; If it's a single character, add Down and Up events
            if (StrLen(keyCmd) == 1) {
              s .= "Send, {" keyCmd " Down}`n"
              s .= "Sleep, 50`n" ; Add a small delay between Down and Up
              s .= "Send, {" keyCmd " Up}`n"
            } else {
              ; For longer strings, keep as is but add braces
              s .= "Send, {" keyCmd "}`n"
            }
          }
        }
        ; Skip window activation and other commands
      }
      
      ; Save to numbered text file in script directory
      NewLogFile := ScriptDir "\" NextFileNumber ".txt"
      
      if (FileExist(NewLogFile))
        FileDelete(NewLogFile)
      
      FileAppend(s, NewLogFile, "UTF-8")
      
      ; Show a brief notification that recording was saved
      ShowTip("Saved to " NextFileNumber ".txt")
      Sleep(1000)
      
      ; Increment the file number for next recording
      NextFileNumber++
    }
    Recording := 0
    ; Reset LogArr to an empty array
    LogArr := []
    SetHotkey(0)
  }

  ShowTip()
  Suspend(false)
  Pause(false)
  isPaused := false
  return
}

PlayKeyAction() {
  #SuspendExempt
  if (Recording || Playing)
    Stop()
  
  ; Since we only want recording functionality, just start recording
  RecordKeyAction()
  return
}

EditKeyAction() {
  #SuspendExempt
  Stop()
  SplitPath(LogFile, &LogFileName)
  try {
    RegDelete("HKEY_CURRENT_USER\SOFTWARE\" LogFileName, "i")
  } catch OSError as err {
    
  }
  Run("`"" EnvGet("LocalAppData") "\Programs\Microsoft VS Code\Code.exe`" `"" LogFile "`"")
  return
}

;============ Functions =============

SetHotkey(f := false) {
  f := f ? "On" : "Off"
  Loop 254
  {
    k := GetKeyName(vk := Format("vk{:X}", A_Index))
    if (!(k ~= "^(?i:|Control|Alt|Shift)$"))
      Hotkey("~*" vk, LogKey, f)
  }
  For i, k in StrSplit("NumpadEnter|Home|End|PgUp" . "|PgDn|Left|Right|Up|Down|Delete|Insert", "|")
  {
    sc := Format("sc{:03X}", GetKeySC(k))
    if (!(k ~= "^(?i:|Control|Alt|Shift)$"))
      Hotkey("~*" sc, LogKey, f)
  }

  if (f = "On") {
    SetTimer(LogWindow)
    LogWindow()
  } else
    SetTimer(LogWindow, 0)
}

LogKey(HotkeyName) {
  Critical()
  k := GetKeyName(vksc := SubStr(A_ThisHotkey, 3))
  k := StrReplace(k, "Control", "Ctrl"), r := SubStr(k, 2)
  if (r ~= "^(?i:Alt|Ctrl|Shift|Win)$")
    LogKey_Control(k)
  else if (k ~= "^(?i:LButton|RButton|MButton)$")
    LogKey_Mouse(k)
  else {
    if (k = "NumpadLeft" || k = "NumpadRight") && !GetKeyState(k, "P")
      return
    k := StrLen(k) > 1 ? k : k ~= "\w" ? k : vksc
    
    ; Always log as Down event
    Log("{" k " Down}", 1)
    
    Critical("Off")
    ErrorLevel := !KeyWait(vksc)
    Critical()
    
    ; Always log as Up event
    Log("{" k " Up}", 1)
  }
}

LogKey_Control(key) {
  global LogArr
  k := InStr(key, "Win") ? key : SubStr(key, 2)
  Log("{" k " Down}", 1)
  Critical("Off")
  ErrorLevel := !KeyWait(key)
  Critical()
  Log("{" k " Up}", 1)
}

LogKey_Mouse(key) {
  global LogArr, RelativeX, RelativeY, MouseMode
  k := SubStr(key, 1, 1)

  ;screen
  CoordMode("Mouse", "Screen")
  MouseGetPos(&X, &Y, &id)
  Log((MouseMode == "window" || MouseMode == "relative" ? ";" : "") "MouseClick(`"" k "`", " X ", " Y ",,, `"D`") `;screen")

  ;window
  CoordMode("Mouse", "Window")
  MouseGetPos(&WindowX, &WindowY, &id)
  Log((MouseMode != "window" ? ";" : "") "MouseClick(`"" k "`", " WindowX ", " WindowY ",,, `"D`") `;window")

  ;relative
  CoordMode("Mouse", "Screen")
  MouseGetPos(&tempRelativeX, &tempRelativeY, &id)
  Log((MouseMode != "relative" ? ";" : "") "MouseClick(`"" k "`", " (tempRelativeX - RelativeX) ", " (tempRelativeY - RelativeY) ",,, `"D`", `"R`") `;relative")
  RelativeX := tempRelativeX
  RelativeY := tempRelativeY

  ;get dif
  CoordMode("Mouse", "Screen")
  MouseGetPos(&X1, &Y1)
  t1 := A_TickCount
  Critical("Off")
  ErrorLevel := !KeyWait(key)
  Critical()
  t2 := A_TickCount
  if (t2 - t1 <= 200)
    X2 := X1, Y2 := Y1
  else
    MouseGetPos(&X2, &Y2)

  ;log screen
  i := LogArr.Length - 2, r := LogArr[i]
  if (InStr(r, ",,, `"D`")") && Abs(X2 - X1) + Abs(Y2 - Y1) < 5)
    LogArr[i] := SubStr(r, 1, -16) ") `;screen", Log()
  else
    Log((MouseMode == "window" || MouseMode == "relative" ? ";" : "") "MouseClick(`"" k "`", " (X + X2 - X1) ", " (Y + Y2 - Y1) ",,, `"U`") `;screen")

  ;log window
  i := LogArr.Length - 1, r := LogArr[i]
  if (InStr(r, ",,, `"D`")") && Abs(X2 - X1) + Abs(Y2 - Y1) < 5)
    LogArr[i] := SubStr(r, 1, -16) ") `;window", Log()
  else
    Log((MouseMode != "window" ? ";" : "") "MouseClick(`"" k "`", " (WindowX + X2 - X1) ", " (WindowY + Y2 - Y1) ",,, `"U`") `;window")

  ;log relative
  i := LogArr.Length, r := LogArr[i]
  if (InStr(r, ",,, `"D`", `"R`")") && Abs(X2 - X1) + Abs(Y2 - Y1) < 5)
    LogArr[i] := SubStr(r, 1, -23) ",,,, `"R`") `;relative", Log()
  else
    Log((MouseMode != "relative" ? ";" : "") "MouseClick(`"" k "`", " (X2 - X1) ", " (Y2 - Y1) ",,, `"U`", `"R`") `;relative")
}

LogWindow() {
  global oldid, LogArr, MouseMode
  static oldtitle
  id := WinExist("A")
  title := WinGetTitle()
  class := WinGetClass()
  if (title = "" && class = "")
    return
  if (id = oldid && title = oldtitle)
    return
  oldid := id, oldtitle := title
  title := SubStr(title, 1, 50)
  title .= class ? " ahk_class " class : ""
  title := RegExReplace(Trim(title), "[``%;]", "``$0")
  CommentString := ""
  if (MouseMode != "window")
    CommentString := ";"
  s := CommentString "tt := `"" title "`"`n" CommentString "WinWait(tt)" . "`n" CommentString "if (!WinActive(tt))`n" CommentString "  WinActivate(tt)"
  i := LogArr.Length
  r := i = 0 ? "" : LogArr[i]
  if (InStr(r, "tt = ") = 1)
    LogArr[i] := s, Log()
  else
    Log(s)
}

Log(str := "", Keyboard := false) {
  global LogArr, RecordSleep
  static LastTime := 0
  
  ; Make sure LogArr is an array
  if (!IsObject(LogArr)) {
    LogArr := []
  }
  
  t := A_TickCount
  Delay := (LastTime ? t - LastTime : 0)
  LastTime := t
  
  if (str = "")
    return
    
  i := LogArr.Length
  r := i = 0 ? "" : LogArr[i]
  
  ; Don't combine Down/Up events with other keys
  if (Keyboard && InStr(r, "Send") && Delay < 1000 && 
      !InStr(str, " Down}") && !InStr(str, " Up}") && 
      !InStr(r, " Down}") && !InStr(r, " Up}")) {
    LogArr[i] := SubStr(r, 1, -1) . str "`""
    return
  }

  if (Delay > 200) 
    LogArr.Push((RecordSleep == "false" ? ";" : "") "Sleep(" (Delay // 2) ")")
  LogArr.Push(Keyboard ? "Send `"{Blind}" str "`"" : str)
}
