---
name: powershell-windows
description: PowerShell Windows patterns. Critical pitfalls, operator syntax, error handling.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# PowerShell Windows Patterns

> Critical patterns and pitfalls for Windows PowerShell.

---

## 1. Operator Syntax Rules

### CRITICAL: Parentheses Required

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `if (Test-Path "a" -or Test-Path "b")` | `if ((Test-Path "a") -or (Test-Path "b"))` |
| `if (Get-Item $x -and $y -eq 5)` | `if ((Get-Item $x) -and ($y -eq 5))` |

**Rule:** Each cmdlet call MUST be in parentheses when using logical operators.

---

## 2. Unicode/Emoji Restriction

### CRITICAL: No Unicode in Scripts

| Purpose | ❌ Don't Use | ✅ Use |
|---------|-------------|--------|
| Success | ✅ ✓ | [OK] [+] |
| Error | ❌ ✗ 🔴 | [!] [X] |
| Warning | ⚠️ 🟡 | [*] [WARN] |
| Info | ℹ️ 🔵 | [i] [INFO] |
| Progress | ⏳ | [...] |

**Rule:** Use ASCII characters only in PowerShell scripts.

---

## 3. Null Check Patterns

### Always Check Before Access

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `$array.Count -gt 0` | `$array -and $array.Count -gt 0` |
| `$text.Length` | `if ($text) { $text.Length }` |

---

## 4. String Interpolation

### Complex Expressions

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `"Value: $($obj.prop.sub)"` | Store in variable first |

**Pattern:**
```
$value = $obj.prop.sub
Write-Output "Value: $value"
```

---

## 5. Error Handling

### ErrorActionPreference

| Value | Use |
|-------|-----|
| Stop | Development (fail fast) |
| Continue | Production scripts |
| SilentlyContinue | When errors expected |

### Try/Catch Pattern

- Don't return inside try block
- Use finally for cleanup
- Return after try/catch

---

## 6. File Paths

### Windows Path Rules

| Pattern | Use |
|---------|-----|
| Literal path | `C:\Users\User\file.txt` |
| Variable path | `Join-Path $env:USERPROFILE "file.txt"` |
| Relative | `Join-Path $ScriptDir "data"` |

**Rule:** Use Join-Path for cross-platform safety.

---

## 7. Array Operations

### Correct Patterns

| Operation | Syntax |
|-----------|--------|
| Empty array | `$array = @()` |
| Add item | `$array += $item` |
| ArrayList add | `$list.Add($item) | Out-Null` |

---

## 8. JSON Operations

### CRITICAL: Depth Parameter

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `ConvertTo-Json` | `ConvertTo-Json -Depth 10` |

**Rule:** Always specify `-Depth` for nested objects.

### File Operations

| Operation | Pattern |
|-----------|---------|
| Read | `Get-Content "file.json" -Raw | ConvertFrom-Json` |
| Write | `$data | ConvertTo-Json -Depth 10 | Out-File "file.json" -Encoding UTF8` |

---

## 9. Common Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| "parameter 'or'" | Missing parentheses | Wrap cmdlets in () |
| "Unexpected token" | Unicode character | Use ASCII only |
| "Cannot find property" | Null object | Check null first |
| "Cannot convert" | Type mismatch | Use .ToString() |

---

## 10. Script Template

```powershell
# Strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# Paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Main
try {
    # Logic here
    Write-Output "[OK] Done"
    exit 0
}
catch {
    Write-Warning "Error: $_"
    exit 1
}
```

---

## 11. Command Syntax Pitfalls

### Deleting Multiple Files

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `del file1 file2` | `del file1, file2` |
| `Remove-Item file1 file2` | `Remove-Item "file1", "file2"` |

**Rule:** `Remove-Item` (alias `del`) accepts a list of strings for `-Path`, BUT they must be comma-separated. Space-separated arguments are interpreted as distinct parameters.

### 11.2 Unix-to-PowerShell Translation

| Bash/Unix | ❌ PowerShell Wrong | ✅ PowerShell Correct |
|-----------|---------------------|-----------------------|
| `command1 && command2` | `cmd1 && cmd2` (PS 5.1 fails) | `cmd1; if ($?) { cmd2 }` |
| `command &` (Background) | `cmd &` | `Start-Process cmd` or `Start-Job` |
| `export VAR=VAL` | `export VAR=VAL` | `$env:VAR = "VAL"` |
| `touch file.txt` | `touch file.txt` | `New-Item file.txt` or `"" > file.txt` |
| `cp -r src dest` | `cp -r src dest` | `Copy-Item -Recurse src dest` |

### 11.3 Output Encoding Trap

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `echo "text" > file.json` | `Set-Content file.json "text"` |

**Rule:** The `>` redirection operator in Windows PowerShell often creates **UTF-16LE** (BOM) files, which breaks JSON parsers and Node.js tools. Always use `Set-Content` or `Out-File -Encoding UTF8`.

### 11.4 The Stop-Parsing Token (--%)

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `npx arg "complex string"` | `npx --% arg "complex string"` |

**Rule:** When calling external CLIs (`npx`, `python`, `az`) with quoted arguments, PowerShell's parser often strips or garbles them. Use `--%` after the command to stop PowerShell parsing and pass the rest literal to the arbitrary program.

### 11.5 Noisy Commands

| ❌ "Silent" | ✅ Truly Silent |
|-------------|-----------------|
| `mkdir newdir` | `mkdir newdir > $null` or `null` |
| `New-Item ...` | `New-Item ... | Out-Null` |

**Rule:** Commands like `mkdir` (New-Item) return the created object. In automation, this "success output" can be mistaken for data. Always silence side-effects.

### 11.6 Reading Files (Array vs String)

| ❌ Risky | ✅ Robust |
|----------|-----------|
| `cat file.json` | `Get-Content file.json -Raw` |
| `$content = Get-Content file.txt` | `$content = Get-Content file.txt -Raw` |

**Rule:** `Get-Content` (alias `cat`) returns an **array of lines** by default. If you try to parse this as JSON or a single block of text without `-Raw`, it will fail or produce unexpected results.

---

> **Remember:** PowerShell has unique syntax rules. Parentheses, ASCII-only, commma-separated lists, and null checks are non-negotiable.
