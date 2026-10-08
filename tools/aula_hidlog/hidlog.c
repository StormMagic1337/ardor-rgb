/* Logging proxy for hid.dll, dropped next to OemDrv.exe (32-bit).
 *
 * Every hid.dll export is forwarded to the real system hid.dll. Feature/input/output report calls are
 * logged with their buffers, and OemDrv's own CreateFile/ReadFile/WriteFile on AULA HID handles
 * (VID 258A / 3554) are logged via an IAT patch, so each record carries the collection it went to.
 * Log: %LOCALAPPDATA%\AULA-F75\hid_log.txt (append; the helper tool writes step markers into the same file).
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>
#include <stdio.h>
#include <string.h>

/* ------------------------------------------------------------------ log */

static HANDLE g_log = INVALID_HANDLE_VALUE;
static CRITICAL_SECTION g_cs;

static void open_log(void)
{
    wchar_t path[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", path, MAX_PATH);
    if (!n || n > MAX_PATH - 40) return;
    wcscat_s(path, MAX_PATH, L"\\AULA-F75");
    CreateDirectoryW(path, NULL);
    wcscat_s(path, MAX_PATH, L"\\hid_log.txt");
    g_log = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                        NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
}

static void log_line(const char *op, const char *tag, BOOL ok, const void *buf, DWORD len, const char *extra)
{
    static char line[8192];
    SYSTEMTIME t;
    DWORD i, w;
    int p;
    if (g_log == INVALID_HANDLE_VALUE) return;
    EnterCriticalSection(&g_cs);
    GetLocalTime(&t);
    p = sprintf_s(line, sizeof line, "%02d:%02d:%02d.%03d %-14s %-22s %s len=%-4lu %s",
                  t.wHour, t.wMinute, t.wSecond, t.wMilliseconds, op, tag ? tag : "?",
                  ok ? "ok " : "ERR", (unsigned long)len, extra ? extra : "");
    for (i = 0; buf && i < len && p < (int)sizeof line - 8; i++)
        p += sprintf_s(line + p, sizeof line - p, "%02x ", ((const unsigned char *)buf)[i]);
    line[p++] = '\r';
    line[p++] = '\n';
    WriteFile(g_log, line, p, &w, NULL);
    LeaveCriticalSection(&g_cs);
}

/* ------------------------------------------------------------------ handle -> collection tag */

#define MAX_H 128
static struct { HANDLE h; char tag[32]; } g_handles[MAX_H];

static const char *tag_of(HANDLE h)
{
    int i;
    for (i = 0; i < MAX_H; i++)
        if (g_handles[i].h == h && h) return g_handles[i].tag;
    return NULL;
}

static void make_tag(const wchar_t *path, char *tag, size_t n)
{
    wchar_t low[512];
    const wchar_t *v, *p, *mi, *col;
    size_t i;
    for (i = 0; path[i] && i < 511; i++) low[i] = towlower(path[i]);
    low[i] = 0;
    v = wcsstr(low, L"vid_");
    p = wcsstr(low, L"pid_");
    mi = wcsstr(low, L"mi_");
    col = wcsstr(low, L"col");
    sprintf_s(tag, n, "%.4ls:%.4ls", v ? v + 4 : L"????", p ? p + 4 : L"????");
    if (mi) sprintf_s(tag + strlen(tag), n - strlen(tag), " mi%.2ls", mi + 3);
    if (col) sprintf_s(tag + strlen(tag), n - strlen(tag), " col%.2ls", col + 3);
}

static void remember(HANDLE h, const wchar_t *path)
{
    wchar_t low[512];
    size_t i;
    int k;
    if (h == INVALID_HANDLE_VALUE || !path) return;
    for (i = 0; path[i] && i < 511; i++) low[i] = towlower(path[i]);
    low[i] = 0;
    if (!wcsstr(low, L"vid_258a") && !wcsstr(low, L"vid_3554")) return;
    EnterCriticalSection(&g_cs);
    for (k = 0; k < MAX_H; k++)
        if (!g_handles[k].h) {
            g_handles[k].h = h;
            make_tag(path, g_handles[k].tag, sizeof g_handles[k].tag);
            break;
        }
    LeaveCriticalSection(&g_cs);
    log_line("open", tag_of(h), TRUE, NULL, 0, "");
}

static void forget(HANDLE h)
{
    int k;
    EnterCriticalSection(&g_cs);
    for (k = 0; k < MAX_H; k++)
        if (g_handles[k].h == h) g_handles[k].h = NULL;
    LeaveCriticalSection(&g_cs);
}

/* pending overlapped reads, completed through GetOverlappedResult */
#define MAX_P 32
static struct { HANDLE h; LPOVERLAPPED o; const void *buf; } g_pend[MAX_P];

/* ------------------------------------------------------------------ kernel32 hooks (OemDrv IAT) */

static HANDLE WINAPI my_CreateFileW(LPCWSTR p, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    HANDLE h = CreateFileW(p, a, s, sa, c, f, t);
    remember(h, p);
    return h;
}

static HANDLE WINAPI my_CreateFileA(LPCSTR p, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    HANDLE h = CreateFileA(p, a, s, sa, c, f, t);
    wchar_t w[512];
    if (p && MultiByteToWideChar(CP_ACP, 0, p, -1, w, 512)) remember(h, w);
    return h;
}

static BOOL WINAPI my_CloseHandle(HANDLE h)
{
    if (tag_of(h)) {
        log_line("close", tag_of(h), TRUE, NULL, 0, "");
        forget(h);
    }
    return CloseHandle(h);
}

static BOOL WINAPI my_WriteFile(HANDLE h, LPCVOID b, DWORD n, LPDWORD w, LPOVERLAPPED o)
{
    BOOL r = WriteFile(h, b, n, w, o);
    const char *tag = tag_of(h);
    if (tag) log_line("WriteFile", tag, r || GetLastError() == ERROR_IO_PENDING, b, n, "");
    return r;
}

static BOOL WINAPI my_ReadFile(HANDLE h, LPVOID b, DWORD n, LPDWORD rd, LPOVERLAPPED o)
{
    BOOL r = ReadFile(h, b, n, rd, o);
    DWORD err = GetLastError();
    const char *tag = tag_of(h);
    int k;
    if (tag) {
        if (r) {
            log_line("ReadFile", tag, TRUE, b, rd ? *rd : (o ? (DWORD)o->InternalHigh : n), "");
        } else if (err == ERROR_IO_PENDING && o) {
            EnterCriticalSection(&g_cs);
            for (k = 0; k < MAX_P; k++)
                if (!g_pend[k].o || g_pend[k].o == o) {
                    g_pend[k].h = h; g_pend[k].o = o; g_pend[k].buf = b;
                    break;
                }
            LeaveCriticalSection(&g_cs);
        } else {
            log_line("ReadFile", tag, FALSE, NULL, 0, "");
        }
    }
    SetLastError(err);
    return r;
}

static BOOL WINAPI my_GetOverlappedResult(HANDLE h, LPOVERLAPPED o, LPDWORD n, BOOL wait)
{
    BOOL r = GetOverlappedResult(h, o, n, wait);
    DWORD err = GetLastError();
    int k;
    if (r && tag_of(h)) {
        for (k = 0; k < MAX_P; k++)
            if (g_pend[k].o == o && g_pend[k].h == h) {
                log_line("ReadFile", tag_of(h), TRUE, g_pend[k].buf, n ? *n : 0, "");
                g_pend[k].o = NULL;
                break;
            }
    }
    SetLastError(err);
    return r;
}

static void patch_iat(void)
{
    static const struct { const char *name; void *fn; } hooks[] = {
        {"CreateFileW", my_CreateFileW}, {"CreateFileA", my_CreateFileA}, {"CloseHandle", my_CloseHandle},
        {"WriteFile", my_WriteFile}, {"ReadFile", my_ReadFile}, {"GetOverlappedResult", my_GetOverlappedResult},
    };
    BYTE *base = (BYTE *)GetModuleHandleW(NULL);
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *d;
    int patched = 0;
    char msg[64];
    if (!dir.VirtualAddress) return;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir.VirtualAddress); d->Name; d++) {
        const char *dll = (const char *)(base + d->Name);
        IMAGE_THUNK_DATA *names, *iat;
        if (_stricmp(dll, "kernel32.dll") && _strnicmp(dll, "api-ms-win-core-file", 20)) continue;
        if (!d->OriginalFirstThunk) continue;
        names = (IMAGE_THUNK_DATA *)(base + d->OriginalFirstThunk);
        iat = (IMAGE_THUNK_DATA *)(base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, iat++) {
            size_t k;
            const char *fn;
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            fn = (const char *)((IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData))->Name;
            for (k = 0; k < sizeof hooks / sizeof hooks[0]; k++)
                if (!strcmp(fn, hooks[k].name)) {
                    DWORD old;
                    if (VirtualProtect(&iat->u1.Function, sizeof(void *), PAGE_READWRITE, &old)) {
                        iat->u1.Function = (ULONG_PTR)hooks[k].fn;
                        VirtualProtect(&iat->u1.Function, sizeof(void *), old, &old);
                        patched++;
                    }
                }
        }
    }
    sprintf_s(msg, sizeof msg, "kernel32 hooks installed: %d", patched);
    log_line("init", "-", TRUE, NULL, 0, msg);
}

/* ------------------------------------------------------------------ hid.dll forwarding */

#define EXPORTS(X) \
    X(0, HidD_FlushQueue) X(1, HidD_FreePreparsedData) X(2, HidD_GetAttributes) X(3, HidD_GetConfiguration) \
    X(4, HidD_GetFeature) X(5, HidD_GetHidGuid) X(6, HidD_GetIndexedString) X(7, HidD_GetInputReport) \
    X(8, HidD_GetManufacturerString) X(9, HidD_GetMsGenreDescriptor) X(10, HidD_GetNumInputBuffers) \
    X(11, HidD_GetPhysicalDescriptor) X(12, HidD_GetPreparsedData) X(13, HidD_GetProductString) \
    X(14, HidD_GetSerialNumberString) X(15, HidD_Hello) X(16, HidD_SetConfiguration) X(17, HidD_SetFeature) \
    X(18, HidD_SetNumInputBuffers) X(19, HidD_SetOutputReport) X(20, HidP_GetButtonArray) \
    X(21, HidP_GetButtonCaps) X(22, HidP_GetCaps) X(23, HidP_GetData) X(24, HidP_GetExtendedAttributes) \
    X(25, HidP_GetLinkCollectionNodes) X(26, HidP_GetScaledUsageValue) X(27, HidP_GetSpecificButtonCaps) \
    X(28, HidP_GetSpecificValueCaps) X(29, HidP_GetUsageValue) X(30, HidP_GetUsageValueArray) \
    X(31, HidP_GetUsages) X(32, HidP_GetUsagesEx) X(33, HidP_GetValueCaps) X(34, HidP_GetVersionInternal) \
    X(35, HidP_InitializeReportForID) X(36, HidP_MaxDataListLength) X(37, HidP_MaxUsageListLength) \
    X(38, HidP_SetButtonArray) X(39, HidP_SetData) X(40, HidP_SetScaledUsageValue) X(41, HidP_SetUsageValue) \
    X(42, HidP_SetUsageValueArray) X(43, HidP_SetUsages) X(44, HidP_TranslateUsagesToI8042ScanCodes) \
    X(45, HidP_UnsetUsages) X(46, HidP_UsageListDifference)

#define NAME(i, n) #n,
static const char *g_names[] = { EXPORTS(NAME) };
static FARPROC g_real[sizeof g_names / sizeof g_names[0]];
static HMODULE g_hid;

static FARPROC __stdcall resolve(int i)
{
    if (!g_real[i]) {
        if (!g_hid) {
            wchar_t p[MAX_PATH];
            UINT n = GetSystemDirectoryW(p, MAX_PATH);   /* WOW64 redirects this to SysWOW64 */
            if (n && n < MAX_PATH - 10) {
                wcscat_s(p, MAX_PATH, L"\\hid.dll");
                g_hid = LoadLibraryW(p);
            }
        }
        if (g_hid) g_real[i] = GetProcAddress(g_hid, g_names[i]);
    }
    return g_real[i];
}

/* Plain jump thunks: arguments stay on the stack untouched. */
#define THUNK(i, n) __declspec(naked) void T_##n(void) { __asm { push i } __asm { call resolve } __asm { jmp eax } }
EXPORTS(THUNK)

/* Logged report functions. */
typedef BOOLEAN(__stdcall *report_fn)(HANDLE, PVOID, ULONG);

static BOOLEAN logged(int idx, const char *op, HANDLE h, PVOID b, ULONG n, BOOL is_get)
{
    report_fn f = (report_fn)resolve(idx);
    unsigned char req[8] = {0};
    char extra[48] = "";
    BOOLEAN r;
    if (!f) return FALSE;
    if (is_get && b && n) {
        memcpy(req, b, n < 8 ? n : 8);
        sprintf_s(extra, sizeof extra, "req=%02x ", req[0]);
    }
    r = f(h, b, n);
    log_line(op, tag_of(h), r, b, n, extra);
    return r;
}

BOOLEAN __stdcall W_HidD_SetFeature(HANDLE h, PVOID b, ULONG n) { return logged(17, "SetFeature", h, b, n, FALSE); }
BOOLEAN __stdcall W_HidD_GetFeature(HANDLE h, PVOID b, ULONG n) { return logged(4, "GetFeature", h, b, n, TRUE); }
BOOLEAN __stdcall W_HidD_SetOutputReport(HANDLE h, PVOID b, ULONG n) { return logged(19, "SetOutput", h, b, n, FALSE); }
BOOLEAN __stdcall W_HidD_GetInputReport(HANDLE h, PVOID b, ULONG n) { return logged(7, "GetInput", h, b, n, TRUE); }

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH) {
        wchar_t exe[MAX_PATH];
        char msg[300];
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_cs);
        open_log();
        GetModuleFileNameW(NULL, exe, MAX_PATH);
        sprintf_s(msg, sizeof msg, "=== hid.dll logger loaded into %ls", exe);
        log_line("init", "-", TRUE, NULL, 0, msg);
        patch_iat();
    } else if (reason == DLL_PROCESS_DETACH && g_log != INVALID_HANDLE_VALUE) {
        log_line("exit", "-", TRUE, NULL, 0, "");
        CloseHandle(g_log);
    }
    return TRUE;
}
