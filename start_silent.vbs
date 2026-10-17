' ═══════════════════════════════════════════════════════
'   تشغيل نظام إدارة العقود - بدون نافذة CMD
' ═══════════════════════════════════════════════════════

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' مسار المجلد الحالي
appDir = fso.GetParentFolderName(WScript.ScriptFullName)

' ═══════════════════════════════════════════════════════
'   تشغيل الخادم في الخلفية (بدون نافذة)
' ═══════════════════════════════════════════════════════

' مسار pythonw.exe (يشغّل Python بدون نافذة)
pythonwPath = appDir & "\.venv\Scripts\pythonw.exe"

' مسار run.py
runPyPath = appDir & "\run.py"

' التحقق من وجود الملفات
If Not fso.FileExists(pythonwPath) Then
    MsgBox "❌ خطأ: لم يتم إيجاد البيئة الافتراضية" & vbCrLf & vbCrLf & _
           "المسار المتوقع:" & vbCrLf & pythonwPath & vbCrLf & vbCrLf & _
           "الحل: شغّل start.bat مرة واحدة أولاً لإنشاء البيئة.", _
           16, "نظام إدارة العقود"
    WScript.Quit
End If

If Not fso.FileExists(runPyPath) Then
    MsgBox "❌ خطأ: لم يتم إيجاد ملف run.py" & vbCrLf & vbCrLf & _
           "المسار المتوقع:" & vbCrLf & runPyPath, _
           16, "نظام إدارة العقود"
    WScript.Quit
End If

' ═══════════════════════════════════════════════════════
'   تشغيل pythonw في الخلفية (0 = مخفي)
' ═══════════════════════════════════════════════════════

WshShell.CurrentDirectory = appDir
WshShell.Run """" & pythonwPath & """ """ & runPyPath & """", 0, False

' ═══════════════════════════════════════════════════════
'   انتظار 4 ثواني ثم فتح المتصفح
' ═══════════════════════════════════════════════════════

WScript.Sleep 4000

' فتح المتصفح
WshShell.Run "http://127.0.0.1:5000", 1, False

' ═══════════════════════════════════════════════════════
'   إشعار للمستخدم (يظهر ويختفي تلقائياً)
' ═══════════════════════════════════════════════════════

MsgBox "✅ تم تشغيل نظام إدارة العقود بنجاح!" & vbCrLf & vbCrLf & _
       "🌐 الرابط: http://127.0.0.1:5000" & vbCrLf & _
       "👤 المستخدم: admin" & vbCrLf & _
       "🔑 كلمة المرور: Admin@2026" & vbCrLf & vbCrLf & _
       "💡 لإيقاف البرنامج:" & vbCrLf & _
       "   - شغّل stop.bat" & vbCrLf & _
       "   - أو من Task Manager → pythonw.exe", _
       64, "نظام إدارة العقود"