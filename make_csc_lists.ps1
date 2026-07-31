$custom = 'C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom'
$files = Get-ChildItem $custom -Filter '*.cs' -Recurse | Select -ExpandProperty FullName | Sort
$fso = New-Object -ComObject Scripting.FileSystemObject
$shortFiles = $files | ForEach { $fso.GetFile($_).ShortPath }
Out-File -FilePath 'run_csc_sources.txt' -InputObject ($shortFiles -join "`r`n") -Encoding ASCII

$refs = @(
'C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\bin\Debug\NinjaTrader.Core.dll',
'C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\NinjaTrader.Custom.dll',
'C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\NinjaTrader.Vendor.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_64\mscorlib\v4.0_4.0.0.0__b77a5c561934e089\mscorlib.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System\v4.0_4.0.0.0__b77a5c561934e089\System.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Core\v4.0_4.0.0.0__b77a5c561934e089\System.Core.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_64\System.Data\v4.0_4.0.0.0__b77a5c561934e089\System.Data.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Drawing\v4.0_4.0.0.0__b03f5f7f11d50a3a\System.Drawing.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Windows.Forms\v4.0_4.0.0.0__b77a5c561934e089\System.Windows.Forms.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Xml\v4.0_4.0.0.0__b77a5c561934e089\System.Xml.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\WindowsBase\v4.0_4.0.0.0__31bf3856ad364e35\WindowsBase.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_64\PresentationCore\v4.0_4.0.0.0__31bf3856ad364e35\PresentationCore.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\PresentationFramework\v4.0_4.0.0.0__31bf3856ad364e35\PresentationFramework.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Xaml\v4.0_4.0.0.0__b77a5c561934e089\System.Xaml.dll',
'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\WindowsFormsIntegration\v4.0_4.0.0.0__31bf3856ad364e35\WindowsFormsIntegration.dll'
)
$shortRefs = $refs | ForEach { $fso.GetFile($_).ShortPath }
Out-File -FilePath 'run_csc_refs.txt' -InputObject ($shortRefs -join "`r`n") -Encoding ASCII

Write-Output ('Sources=' + $shortFiles.Count + ' Refs=' + $shortRefs.Count)
