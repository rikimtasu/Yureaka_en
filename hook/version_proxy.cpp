// yureaka_en x86 version.dll proxy hook for Akatsuki Yureru Koi Akari (SOFTPAL / Pal.dll)
//
// Features:
//  1. Transparently forwards all 17 Windows version.dll exports to %SystemRoot%\System32\version.dll.
//  2. Loads bundled compact Google Font TTF (default: en_fonts\BarlowSemiCondensed-Medium.ttf)
//     via AddFontResourceExA(..., FR_PRIVATE, 0).
//  3. Hooks yureaka.exe Delay-Load of \dll\PAL.dll via LoadLibraryA / LoadLibraryExA / GetProcAddress:
//     - Hooks Pal.dll!CreateFontA (custom Google Font face, nWidth=0, DEFAULT_CHARSET, ANTIALIASED_QUALITY)
//     - Hooks Pal.dll!CreateWindowExA & SetWindowTextA (localized English window title)
//     - Hooks PalFontSetType, PalFontBegin, PalFontSetFontSize (redirects type 4 bitmap font -> type 2 GDI)
//  4. Hooks yureaka.exe TEXT.DAT reader (RVA 0x589f0) using yureaka_en.dat overlay table:
//     - Maps original TEXT.DAT abs_offset -> (u32 text_id, translated CP932 string)
//     - Keeps original data.pac / SCRIPT.SRC 100% untouched (zero shifted-offset crashes, zero length limits!)

#define _CRT_SECURE_NO_WARNINGS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

// ---------------------------------------------------------------------------
// Configuration (yureaka_en.ini next to yureaka.exe)
// ---------------------------------------------------------------------------
struct HookConfig {
    bool enabled = true;
    bool force_gdi_font = true;
    bool override_window_title = true;
    bool enable_text_overlay = true;
    bool enable_log = false;
    char font_file[MAX_PATH] = "en_fonts\\BarlowSemiCondensed-Medium.ttf";
    char font_face[LF_FACESIZE] = "Barlow Semi Condensed Medium";
    char text_overlay_file[MAX_PATH] = "yureaka_en.dat";
    int font_weight = 400;
    int font_size_default = 28;       // replaces default 26px line height -> 28px (spacious 3 lines)
    int height_scale_percent = 104;   // 28 * 104% = 29px -> max descender+outline = 29px <= 30px (zero clipping!)
    int char_spacing_delta = -2;      // removes bloated +3px PalFontGetSize padding -> crisp +1px outline gap
    int space_width_percent = 26;     // proportional ASCII space (~8px instead of giant 16px)
    int charset = DEFAULT_CHARSET;
    int quality = ANTIALIASED_QUALITY;
    char window_title[256] = "Akatsuki Yureru Koi Akari";
};

static HookConfig g_cfg;
static int g_cur_font_height = 32;
static char g_exe_dir[MAX_PATH] = {};
static char g_log_path[MAX_PATH] = {};
static HMODULE g_real_version = nullptr;
static HMODULE g_pal_module = nullptr;
static bool g_pal_iat_hooked = false;
static bool g_hooks_installed = false;

static void log_msg(const char* fmt, ...) {
    if (!g_cfg.enable_log || !g_log_path[0]) return;
    FILE* fp = std::fopen(g_log_path, "a");
    if (!fp) return;
    va_list ap;
    va_start(ap, fmt);
    std::vfprintf(fp, fmt, ap);
    std::fputc('\n', fp);
    va_end(ap);
    std::fclose(fp);
}

// ---------------------------------------------------------------------------
// Real version.dll forwarding trampolines (17 exports)
// ---------------------------------------------------------------------------
static FARPROC g_ver_procs[17] = {};
static const char* g_ver_names[17] = {
    "GetFileVersionInfoA",
    "GetFileVersionInfoByHandle",
    "GetFileVersionInfoExA",
    "GetFileVersionInfoExW",
    "GetFileVersionInfoSizeA",
    "GetFileVersionInfoSizeExA",
    "GetFileVersionInfoSizeExW",
    "GetFileVersionInfoSizeW",
    "GetFileVersionInfoW",
    "VerFindFileA",
    "VerFindFileW",
    "VerInstallFileA",
    "VerInstallFileW",
    "VerLanguageNameA",
    "VerLanguageNameW",
    "VerQueryValueA",
    "VerQueryValueW",
};

static bool load_real_version() {
    if (g_real_version) return true;
    char sysdir[MAX_PATH] = {};
    UINT len = GetSystemDirectoryA(sysdir, MAX_PATH);
    if (len == 0 || len >= MAX_PATH - 16) return false;
    char path[MAX_PATH] = {};
    std::snprintf(path, sizeof(path), "%s\\version.dll", sysdir);
    g_real_version = LoadLibraryA(path);
    if (!g_real_version) return false;
    for (int i = 0; i < 17; ++i) {
        g_ver_procs[i] = GetProcAddress(g_real_version, g_ver_names[i]);
    }
    return true;
}

#define DEF_PROXY(idx, name) \
    extern "C" __declspec(naked) void _proxy_##name() { \
        __asm { jmp dword ptr [g_ver_procs + idx * 4] } \
    }

DEF_PROXY(0,  GetFileVersionInfoA)
DEF_PROXY(1,  GetFileVersionInfoByHandle)
DEF_PROXY(2,  GetFileVersionInfoExA)
DEF_PROXY(3,  GetFileVersionInfoExW)
DEF_PROXY(4,  GetFileVersionInfoSizeA)
DEF_PROXY(5,  GetFileVersionInfoSizeExA)
DEF_PROXY(6,  GetFileVersionInfoSizeExW)
DEF_PROXY(7,  GetFileVersionInfoSizeW)
DEF_PROXY(8,  GetFileVersionInfoW)
DEF_PROXY(9,  VerFindFileA)
DEF_PROXY(10, VerFindFileW)
DEF_PROXY(11, VerInstallFileA)
DEF_PROXY(12, VerInstallFileW)
DEF_PROXY(13, VerLanguageNameA)
DEF_PROXY(14, VerLanguageNameW)
DEF_PROXY(15, VerQueryValueA)
DEF_PROXY(16, VerQueryValueW)

// ---------------------------------------------------------------------------
// Text overlay table (`yureaka_en.dat`, magic "YUR1")
// Format:
//   Header (16 bytes): char magic[4]="YUR1", u32 version=1, u32 count, u32 pool_offset
//   Entries[count] (sorted by orig_abs_off):
//     u32 orig_abs_off, u32 text_id, u32 str_off (from pool_offset), u32 str_len (excl NUL)
//   String pool: null-terminated CP932 strings
// ---------------------------------------------------------------------------
#pragma pack(push, 1)
struct OverlayHeader {
    char magic[4];
    uint32_t version;
    uint32_t count;
    uint32_t pool_offset;
};
struct OverlayEntry {
    uint32_t orig_abs_off;
    uint32_t text_id;
    uint32_t str_off;
    uint32_t str_len;
};
#pragma pack(pop)

static std::vector<uint8_t> g_overlay_blob;
static const OverlayEntry* g_overlay_entries = nullptr;
static uint32_t g_overlay_count = 0;
static const uint8_t* g_overlay_pool = nullptr;
static uint32_t g_overlay_pool_size = 0;

static void load_text_overlay() {
    if (!g_cfg.enable_text_overlay || !g_cfg.text_overlay_file[0]) return;
    char full[MAX_PATH] = {};
    if (g_cfg.text_overlay_file[1] == ':') {
        std::snprintf(full, sizeof(full), "%s", g_cfg.text_overlay_file);
    } else {
        std::snprintf(full, sizeof(full), "%s\\%s", g_exe_dir, g_cfg.text_overlay_file);
    }
    FILE* fp = std::fopen(full, "rb");
    if (!fp) {
        log_msg("[Overlay] not found: %s", full);
        return;
    }
    std::fseek(fp, 0, SEEK_END);
    long sz = std::ftell(fp);
    std::fseek(fp, 0, SEEK_SET);
    if (sz < static_cast<long>(sizeof(OverlayHeader))) {
        std::fclose(fp);
        log_msg("[Overlay] invalid size: %ld", sz);
        return;
    }
    g_overlay_blob.resize(static_cast<size_t>(sz));
    if (std::fread(g_overlay_blob.data(), 1, static_cast<size_t>(sz), fp) != static_cast<size_t>(sz)) {
        std::fclose(fp);
        g_overlay_blob.clear();
        return;
    }
    std::fclose(fp);

    const auto* hdr = reinterpret_cast<const OverlayHeader*>(g_overlay_blob.data());
    if (std::memcmp(hdr->magic, "YUR1", 4) != 0 || hdr->version != 1) {
        log_msg("[Overlay] bad magic/version");
        g_overlay_blob.clear();
        return;
    }
    size_t table_end = sizeof(OverlayHeader) + static_cast<size_t>(hdr->count) * sizeof(OverlayEntry);
    if (hdr->pool_offset < table_end || hdr->pool_offset > g_overlay_blob.size()) {
        log_msg("[Overlay] bad pool_offset");
        g_overlay_blob.clear();
        return;
    }
    g_overlay_entries = reinterpret_cast<const OverlayEntry*>(g_overlay_blob.data() + sizeof(OverlayHeader));
    g_overlay_count = hdr->count;
    g_overlay_pool = g_overlay_blob.data() + hdr->pool_offset;
    g_overlay_pool_size = static_cast<uint32_t>(g_overlay_blob.size() - hdr->pool_offset);
    log_msg("[Overlay] loaded %u translated entries from %s (%zu bytes)", g_overlay_count, full, g_overlay_blob.size());
}

// Called from naked detour on yureaka.exe!0x004589f0 (RVA 0x589f0).
// Returns 1 if handled by overlay, 0 to fall through to original TEXT.DAT reader.
extern "C" int __stdcall try_read_overlay_text(void* dst, uint32_t orig_off, uint32_t max_len) {
    if (!g_overlay_entries || g_overlay_count == 0 || !dst || max_len < 6) return 0;
    if ((orig_off & 0x10000000u) || orig_off == 0x0fffffffu) return 0;

    // Binary search by orig_abs_off
    uint32_t lo = 0, hi = g_overlay_count;
    while (lo < hi) {
        uint32_t mid = lo + ((hi - lo) >> 1);
        uint32_t cur = g_overlay_entries[mid].orig_abs_off;
        if (cur < orig_off) {
            lo = mid + 1;
        } else if (cur > orig_off) {
            hi = mid;
        } else {
            const OverlayEntry& e = g_overlay_entries[mid];
            if (e.str_off + e.str_len > g_overlay_pool_size) return 0;
            uint8_t* out = reinterpret_cast<uint8_t*>(dst);
            std::memcpy(out, &e.text_id, 4);
            uint32_t copy_len = e.str_len;
            if (copy_len > max_len - 5) copy_len = max_len - 5;
            if (copy_len > 0) {
                std::memcpy(out + 4, g_overlay_pool + e.str_off, copy_len);
            }
            out[4 + copy_len] = 0;
            return 1;
        }
    }
    return 0;
}

// Executable 16-byte trampoline buffer for original 7-byte prologue + JMP back to RVA 0x589f7
static uint8_t* g_text_trampoline = nullptr;

// Naked detour matching yureaka.exe!0x004589f0 calling convention:
//   ecx = dst, edx = text_obj, [esp+4] = orig_off, [esp+8] = max_len, returns via plain `ret`!
extern "C" __declspec(naked) void detour_read_text_dat() {
    __asm {
        push ecx
        push edx
        // Stack layout now: [esp+0]=edx, [esp+4]=ecx, [esp+8]=retaddr, [esp+12]=orig_off, [esp+16]=max_len
        push dword ptr [esp + 16]   // max_len
        push dword ptr [esp + 16]   // orig_off (shifted +4 by previous push)
        push ecx                    // dst
        call try_read_overlay_text  // __stdcall cleans its 3 args
        test eax, eax
        jnz handled
        pop edx
        pop ecx
        jmp dword ptr [g_text_trampoline]
    handled:
        pop edx
        pop ecx
        ret
    }
}

static bool install_text_reader_detour(HMODULE hExe) {
    if (!hExe || !g_overlay_entries || g_overlay_count == 0) return false;
    uint8_t* target = reinterpret_cast<uint8_t*>(hExe) + 0x589f0;
    // Verify exact expected 7-byte prologue of yureaka.exe!0x004589f0:
    //   55 8b ec 56 8b 75 08 (push ebp; mov ebp,esp; push esi; mov esi,[ebp+8])
    static const uint8_t expected[7] = {0x55, 0x8B, 0xEC, 0x56, 0x8B, 0x75, 0x08};
    if (std::memcmp(target, expected, sizeof(expected)) != 0) {
        log_msg("[Detour] RVA 0x589f0 prologue mismatch! Found %02x %02x %02x %02x %02x %02x %02x",
                target[0], target[1], target[2], target[3], target[4], target[5], target[6]);
        return false;
    }

    g_text_trampoline = reinterpret_cast<uint8_t*>(
        VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!g_text_trampoline) return false;

    std::memcpy(g_text_trampoline, expected, 7);
    g_text_trampoline[7] = 0xE9; // JMP rel32 to target + 7
    int32_t back_rel = static_cast<int32_t>((target + 7) - (g_text_trampoline + 12));
    std::memcpy(g_text_trampoline + 8, &back_rel, 4);

    DWORD old_prot = 0;
    if (!VirtualProtect(target, 7, PAGE_EXECUTE_READWRITE, &old_prot)) return false;
    target[0] = 0xE9; // JMP rel32 to detour_read_text_dat
    int32_t fwd_rel = static_cast<int32_t>(reinterpret_cast<uint8_t*>(&detour_read_text_dat) - (target + 5));
    std::memcpy(target + 1, &fwd_rel, 4);
    target[5] = 0x90;
    target[6] = 0x90;
    VirtualProtect(target, 7, old_prot, &old_prot);
    FlushInstructionCache(GetCurrentProcess(), target, 7);
    log_msg("[Detour] RVA 0x589f0 TEXT.DAT overlay detour installed OK");
    return true;
}

// ---------------------------------------------------------------------------
// Generic PE IAT patch helper
// ---------------------------------------------------------------------------
static bool patch_iat(HMODULE mod, const char* target_dll, const char* func_name, void* new_fn, void** out_orig) {
    if (!mod) return false;
    auto base = reinterpret_cast<BYTE*>(mod);
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return false;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return false;

    auto& dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dir.VirtualAddress) return false;

    auto desc = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base + dir.VirtualAddress);
    for (; desc->Name; ++desc) {
        const char* dll_name = reinterpret_cast<const char*>(base + desc->Name);
        if (_stricmp(dll_name, target_dll) != 0) continue;

        auto orig_thunk = reinterpret_cast<IMAGE_THUNK_DATA*>(
            base + (desc->OriginalFirstThunk ? desc->OriginalFirstThunk : desc->FirstThunk));
        auto iat_thunk = reinterpret_cast<IMAGE_THUNK_DATA*>(base + desc->FirstThunk);

        for (; orig_thunk->u1.AddressOfData; ++orig_thunk, ++iat_thunk) {
            if (IMAGE_SNAP_BY_ORDINAL(orig_thunk->u1.Ordinal)) continue;
            auto ibn = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base + orig_thunk->u1.AddressOfData);
            if (std::strcmp(reinterpret_cast<const char*>(ibn->Name), func_name) != 0) continue;

            DWORD old_prot = 0;
            if (!VirtualProtect(&iat_thunk->u1.Function, sizeof(void*), PAGE_READWRITE, &old_prot)) {
                return false;
            }
            if (out_orig && !*out_orig) {
                *out_orig = reinterpret_cast<void*>(iat_thunk->u1.Function);
            }
            iat_thunk->u1.Function = reinterpret_cast<DWORD>(new_fn);
            VirtualProtect(&iat_thunk->u1.Function, sizeof(void*), old_prot, &old_prot);
            return true;
        }
    }
    return false;
}

// ---------------------------------------------------------------------------
// Hooked Win32 & Pal.dll functions
// ---------------------------------------------------------------------------
using CreateFontA_t = HFONT (WINAPI*)(int, int, int, int, int, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPCSTR);
using PalFontSetType_t = int (__cdecl*)(int);
using PalFontGetType_t = int (__cdecl*)();
using PalFontBegin_t = int (__cdecl*)();
using PalFontSetFontSize_t = int (__cdecl*)(int);
using PalFontGetSize_t = int (__cdecl*)(LPCSTR, SIZE*);
using CreateWindowExA_t = HWND (WINAPI*)(DWORD, LPCSTR, LPCSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, LPVOID);
using SetWindowTextA_t = BOOL (WINAPI*)(HWND, LPCSTR);
using LoadLibraryA_t = HMODULE (WINAPI*)(LPCSTR);
using LoadLibraryExA_t = HMODULE (WINAPI*)(LPCSTR, HANDLE, DWORD);
using GetProcAddress_t = FARPROC (WINAPI*)(HMODULE, LPCSTR);

static CreateFontA_t        g_orig_CreateFontA = nullptr;
static PalFontSetType_t     g_orig_PalFontSetType = nullptr;
static PalFontGetType_t     g_orig_PalFontGetType = nullptr;
static PalFontBegin_t       g_orig_PalFontBegin = nullptr;
static PalFontSetFontSize_t g_orig_PalFontSetFontSize = nullptr;
static PalFontGetSize_t     g_orig_PalFontGetSize = nullptr;
static CreateWindowExA_t    g_orig_Exe_CreateWindowExA = nullptr;
static SetWindowTextA_t     g_orig_Exe_SetWindowTextA = nullptr;
static CreateWindowExA_t    g_orig_Pal_CreateWindowExA = nullptr;
static SetWindowTextA_t     g_orig_Pal_SetWindowTextA = nullptr;
static LoadLibraryA_t       g_orig_LoadLibraryA = nullptr;
static LoadLibraryExA_t     g_orig_LoadLibraryExA = nullptr;
static GetProcAddress_t     g_orig_GetProcAddress = nullptr;

static HFONT WINAPI hook_CreateFontA(
    int cHeight, int cWidth, int cEscapement, int cOrientation, int cWeight,
    DWORD bItalic, DWORD bUnderline, DWORD bStrikeOut, DWORD iCharSet,
    DWORD iOutPrecision, DWORD iClipPrecision, DWORD iQuality, DWORD iPitchAndFamily,
    LPCSTR pszFaceName
) {
    int base_h = cHeight;
    if (g_cfg.font_size_default > 0 && base_h == 26) {
        base_h = g_cfg.font_size_default;
    }
    int new_height = base_h;
    if (g_cfg.height_scale_percent > 0 && g_cfg.height_scale_percent != 100 && base_h > 0) {
        new_height = (base_h * g_cfg.height_scale_percent + 50) / 100;
    }
    g_cur_font_height = new_height > 0 ? new_height : -new_height;

    int new_weight = g_cfg.font_weight > 0 ? g_cfg.font_weight : cWeight;
    LPCSTR new_face = g_cfg.font_face[0] ? g_cfg.font_face : pszFaceName;

    log_msg("[CreateFontA] orig=(h=%d w=%d wt=%d cs=%lu face=%s) -> new=(h=%d w=0 wt=%d cs=%d q=%d face=%s)",
            cHeight, cWidth, cWeight, iCharSet, pszFaceName ? pszFaceName : "(null)",
            new_height, new_weight, g_cfg.charset, g_cfg.quality, new_face ? new_face : "(null)");

    return g_orig_CreateFontA(
        new_height, 0, cEscapement, cOrientation, new_weight,
        bItalic, bUnderline, bStrikeOut,
        static_cast<DWORD>(g_cfg.charset),
        OUT_TT_PRECIS, iClipPrecision,
        static_cast<DWORD>(g_cfg.quality),
        DEFAULT_PITCH | FF_DONTCARE,
        new_face
    );
}

static bool looks_like_game_title(LPCSTR s) {
    if (!s || !s[0]) return false;
    const auto* u = reinterpret_cast<const unsigned char*>(s);
    // Original Shift-JIS title begins with 紅月 (0x8D 0x67 0x8C 0x8E)
    return (u[0] == 0x8D && u[1] == 0x67 && u[2] == 0x8C && u[3] == 0x8E);
}

static HWND WINAPI hook_Exe_CreateWindowExA(
    DWORD ex_style, LPCSTR cls, LPCSTR title, DWORD style,
    int x, int y, int w, int h, HWND parent, HMENU menu, HINSTANCE inst, LPVOID param
) {
    LPCSTR use_title = (g_cfg.override_window_title && looks_like_game_title(title)) ? g_cfg.window_title : title;
    return g_orig_Exe_CreateWindowExA(ex_style, cls, use_title, style, x, y, w, h, parent, menu, inst, param);
}

static BOOL WINAPI hook_Exe_SetWindowTextA(HWND hwnd, LPCSTR title) {
    LPCSTR use_title = (g_cfg.override_window_title && looks_like_game_title(title)) ? g_cfg.window_title : title;
    return g_orig_Exe_SetWindowTextA(hwnd, use_title);
}

static HWND WINAPI hook_Pal_CreateWindowExA(
    DWORD ex_style, LPCSTR cls, LPCSTR title, DWORD style,
    int x, int y, int w, int h, HWND parent, HMENU menu, HINSTANCE inst, LPVOID param
) {
    LPCSTR use_title = (g_cfg.override_window_title && looks_like_game_title(title)) ? g_cfg.window_title : title;
    return g_orig_Pal_CreateWindowExA(ex_style, cls, use_title, style, x, y, w, h, parent, menu, inst, param);
}

static BOOL WINAPI hook_Pal_SetWindowTextA(HWND hwnd, LPCSTR title) {
    LPCSTR use_title = (g_cfg.override_window_title && looks_like_game_title(title)) ? g_cfg.window_title : title;
    return g_orig_Pal_SetWindowTextA(hwnd, use_title);
}

static void hook_pal_module_iat(HMODULE hPal) {
    if (!hPal || g_pal_iat_hooked) return;
    g_pal_module = hPal;
    g_pal_iat_hooked = true;
    bool ok_font = patch_iat(hPal, "GDI32.dll", "CreateFontA",
                             reinterpret_cast<void*>(&hook_CreateFontA),
                             reinterpret_cast<void**>(&g_orig_CreateFontA));
    bool ok_cw = patch_iat(hPal, "USER32.dll", "CreateWindowExA",
                           reinterpret_cast<void*>(&hook_Pal_CreateWindowExA),
                           reinterpret_cast<void**>(&g_orig_Pal_CreateWindowExA));
    bool ok_sw = patch_iat(hPal, "USER32.dll", "SetWindowTextA",
                           reinterpret_cast<void*>(&hook_Pal_SetWindowTextA),
                           reinterpret_cast<void**>(&g_orig_Pal_SetWindowTextA));
    g_orig_PalFontGetType = reinterpret_cast<PalFontGetType_t>(g_orig_GetProcAddress(hPal, "PalFontGetType"));
    log_msg("[Hook] Pal.dll IAT patched: CreateFontA=%d CreateWindowExA=%d SetWindowTextA=%d",
            ok_font, ok_cw, ok_sw);
}

static int __cdecl hook_PalFontSetType(int font_type) {
    int mapped = (g_cfg.force_gdi_font && font_type == 4) ? 2 : font_type;
    if (mapped != font_type) {
        log_msg("[PalFontSetType] %d -> %d", font_type, mapped);
    }
    return g_orig_PalFontSetType(mapped);
}

static int __cdecl hook_PalFontBegin() {
    if (g_cfg.force_gdi_font && g_orig_PalFontGetType && g_orig_PalFontSetType) {
        if (g_orig_PalFontGetType() == 4) {
            log_msg("[PalFontBegin] forcing type 4 -> 2");
            g_orig_PalFontSetType(2);
        }
    }
    return g_orig_PalFontBegin();
}

static int __cdecl hook_PalFontSetFontSize(int size) {
    int mapped = size;
    if (g_cfg.font_size_default > 0 && size == 26) {
        mapped = g_cfg.font_size_default;
    }
    if (mapped != size) {
        log_msg("[PalFontSetFontSize] %d -> %d", size, mapped);
    }
    return g_orig_PalFontSetFontSize(mapped);
}

static int __cdecl hook_PalFontGetSize(LPCSTR str, SIZE* out_sz) {
    int ret = g_orig_PalFontGetSize(str, out_sz);
    if (ret && str && out_sz && str[0] != '\0' && str[1] == '\0') {
        unsigned char c = static_cast<unsigned char>(str[0]);
        if (c == ' ') {
            int sp = (g_cur_font_height * g_cfg.space_width_percent + 50) / 100;
            if (sp < 4) sp = 4;
            out_sz->cx = sp;
        } else if (c >= 0x21 && c <= 0x7E) {
            long adj = out_sz->cx + g_cfg.char_spacing_delta;
            out_sz->cx = adj > 1 ? adj : 1;
        }
    }
    return ret;
}

static bool is_pal_dll_name(LPCSTR name) {
    if (!name) return false;
    const char* base = std::strrchr(name, '\\');
    base = base ? base + 1 : name;
    return _stricmp(base, "PAL.dll") == 0 || _stricmp(base, "Pal") == 0;
}

static HMODULE WINAPI hook_LoadLibraryA(LPCSTR lpLibFileName) {
    HMODULE mod = g_orig_LoadLibraryA(lpLibFileName);
    if (mod && is_pal_dll_name(lpLibFileName)) {
        log_msg("[LoadLibraryA] caught %s @ %p", lpLibFileName, mod);
        hook_pal_module_iat(mod);
    }
    return mod;
}

static HMODULE WINAPI hook_LoadLibraryExA(LPCSTR lpLibFileName, HANDLE hFile, DWORD dwFlags) {
    HMODULE mod = g_orig_LoadLibraryExA(lpLibFileName, hFile, dwFlags);
    if (mod && is_pal_dll_name(lpLibFileName)) {
        log_msg("[LoadLibraryExA] caught %s @ %p", lpLibFileName, mod);
        hook_pal_module_iat(mod);
    }
    return mod;
}

static FARPROC WINAPI hook_GetProcAddress(HMODULE hModule, LPCSTR lpProcName) {
    FARPROC real = g_orig_GetProcAddress(hModule, lpProcName);
    if (!real || !hModule || HIWORD(lpProcName) == 0) return real;

    // Catch Pal.dll even if loaded before our LoadLibraryA hook fired
    if (!g_pal_iat_hooked && std::strncmp(lpProcName, "PalFont", 7) == 0) {
        hook_pal_module_iat(hModule);
    }
    if (hModule == g_pal_module) {
        if (std::strcmp(lpProcName, "PalFontSetType") == 0) {
            g_orig_PalFontSetType = reinterpret_cast<PalFontSetType_t>(real);
            log_msg("[GetProcAddress] intercepted PalFontSetType");
            return reinterpret_cast<FARPROC>(&hook_PalFontSetType);
        }
        if (std::strcmp(lpProcName, "PalFontBegin") == 0) {
            g_orig_PalFontBegin = reinterpret_cast<PalFontBegin_t>(real);
            log_msg("[GetProcAddress] intercepted PalFontBegin");
            return reinterpret_cast<FARPROC>(&hook_PalFontBegin);
        }
        if (std::strcmp(lpProcName, "PalFontSetFontSize") == 0) {
            g_orig_PalFontSetFontSize = reinterpret_cast<PalFontSetFontSize_t>(real);
            log_msg("[GetProcAddress] intercepted PalFontSetFontSize");
            return reinterpret_cast<FARPROC>(&hook_PalFontSetFontSize);
        }
        if (std::strcmp(lpProcName, "PalFontGetSize") == 0) {
            g_orig_PalFontGetSize = reinterpret_cast<PalFontGetSize_t>(real);
            log_msg("[GetProcAddress] intercepted PalFontGetSize");
            return reinterpret_cast<FARPROC>(&hook_PalFontGetSize);
        }
    }
    return real;
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
static void load_config() {
    GetModuleFileNameA(nullptr, g_exe_dir, MAX_PATH);
    char* slash = std::strrchr(g_exe_dir, '\\');
    if (slash) *slash = '\0';

    char ini_path[MAX_PATH] = {};
    std::snprintf(ini_path, sizeof(ini_path), "%s\\yureaka_en.ini", g_exe_dir);
    std::snprintf(g_log_path, sizeof(g_log_path), "%s\\yureaka_en.log", g_exe_dir);

    g_cfg.enabled = GetPrivateProfileIntA("General", "Enable", 1, ini_path) != 0;
    g_cfg.enable_log = GetPrivateProfileIntA("General", "Log", 0, ini_path) != 0;
    g_cfg.enable_text_overlay = GetPrivateProfileIntA("General", "EnableTextOverlay", 1, ini_path) != 0;
    GetPrivateProfileStringA("General", "TextOverlayFile", g_cfg.text_overlay_file,
                             g_cfg.text_overlay_file, sizeof(g_cfg.text_overlay_file), ini_path);

    g_cfg.force_gdi_font = GetPrivateProfileIntA("Font", "ForceGdiFont", 1, ini_path) != 0;
    g_cfg.font_weight = GetPrivateProfileIntA("Font", "Weight", 400, ini_path);
    g_cfg.font_size_default = GetPrivateProfileIntA("Font", "DefaultSize", 28, ini_path);
    g_cfg.height_scale_percent = GetPrivateProfileIntA("Font", "HeightScalePercent", 104, ini_path);
    g_cfg.char_spacing_delta = static_cast<int>(GetPrivateProfileIntA("Font", "CharSpacingDelta", -2, ini_path));
    g_cfg.space_width_percent = GetPrivateProfileIntA("Font", "SpaceWidthPercent", 26, ini_path);
    g_cfg.charset = GetPrivateProfileIntA("Font", "CharSet", DEFAULT_CHARSET, ini_path);
    g_cfg.quality = GetPrivateProfileIntA("Font", "Quality", ANTIALIASED_QUALITY, ini_path);
    GetPrivateProfileStringA("Font", "FontFile", g_cfg.font_file, g_cfg.font_file, sizeof(g_cfg.font_file), ini_path);
    GetPrivateProfileStringA("Font", "FaceName", g_cfg.font_face, g_cfg.font_face, sizeof(g_cfg.font_face), ini_path);

    g_cfg.override_window_title = GetPrivateProfileIntA("Window", "OverrideTitle", 1, ini_path) != 0;
    GetPrivateProfileStringA("Window", "Title", g_cfg.window_title, g_cfg.window_title, sizeof(g_cfg.window_title), ini_path);
}

// Auto-heal save\favoice.dat if an earlier run saved nested ASCII '"' inside the 5th CSV column
// (e.g. 000000,0,"Asahi","VO03_00095",""Now that's infuriating!""), which crashes Softpal on launch.
static void sanitize_favoice_dat() {
    char fav_path[MAX_PATH] = {};
    std::snprintf(fav_path, sizeof(fav_path), "%s\\save\\favoice.dat", g_exe_dir);
    FILE* fp = std::fopen(fav_path, "rb");
    if (!fp) return;
    std::fseek(fp, 0, SEEK_END);
    long sz = std::ftell(fp);
    std::fseek(fp, 0, SEEK_SET);
    if (sz <= 0 || sz > 4 * 1024 * 1024) {
        std::fclose(fp);
        return;
    }
    std::vector<char> buf(static_cast<size_t>(sz));
    if (std::fread(buf.data(), 1, buf.size(), fp) != buf.size()) {
        std::fclose(fp);
        return;
    }
    std::fclose(fp);

    std::vector<char> out;
    out.reserve(buf.size() + 64);
    bool modified = false;
    size_t i = 0;
    while (i < buf.size()) {
        size_t line_start = i;
        while (i < buf.size() && buf[i] != '\n') ++i;
        size_t line_end = i;
        bool has_lf = (i < buf.size() && buf[i] == '\n');
        if (has_lf) ++i;
        size_t content_end = line_end;
        bool has_cr = (content_end > line_start && buf[content_end - 1] == '\r');
        if (has_cr) --content_end;

        // Format: id,flag,"speaker","voice","<text>"
        // Find the 4th comma to locate the 5th field ("<text>")
        int commas = 0;
        size_t f5_start = content_end;
        for (size_t j = line_start; j < content_end; ++j) {
            if (buf[j] == ',') {
                ++commas;
                if (commas == 4) {
                    f5_start = j + 1;
                    break;
                }
            }
        }
        if (f5_start + 2 <= content_end && buf[f5_start] == '"' && buf[content_end - 1] == '"') {
            out.insert(out.end(), buf.begin() + line_start, buf.begin() + f5_start + 1);
            size_t inner_start = f5_start + 1;
            size_t inner_end = content_end - 1;
            // Strip redundant outer dialogue quotes (""text"" or 0x8167..0x8168) cleanly,
            // and replace any remaining inner '"' with ASCII '\'' so CSV parsing never breaks
            // and text renders cleanly on any Windows locale.
            if (inner_start + 2 <= inner_end && buf[inner_start] == '"' && buf[inner_end - 1] == '"') {
                ++inner_start;
                --inner_end;
                modified = true;
            }
            for (size_t j = inner_start; j < inner_end; ++j) {
                if (buf[j] == '"') {
                    out.push_back('\'');
                    modified = true;
                } else if (j + 1 < inner_end &&
                           static_cast<unsigned char>(buf[j]) == 0x81 &&
                           (static_cast<unsigned char>(buf[j + 1]) == 0x67 ||
                            static_cast<unsigned char>(buf[j + 1]) == 0x68)) {
                    // Also clean any 0x8167/0x8168 written by an earlier sanitizer build
                    if (j > inner_start && j + 2 < inner_end) {
                        out.push_back('\'');
                    }
                    ++j;
                    modified = true;
                } else {
                    out.push_back(buf[j]);
                }
            }
            out.push_back('"');
        } else {
            out.insert(out.end(), buf.begin() + line_start, buf.begin() + content_end);
        }
        if (has_cr) out.push_back('\r');
        if (has_lf) out.push_back('\n');
    }

    if (modified) {
        FILE* wfp = std::fopen(fav_path, "wb");
        if (wfp) {
            std::fwrite(out.data(), 1, out.size(), wfp);
            std::fclose(wfp);
            log_msg("[FavVoice] sanitized nested ASCII quotes in %s", fav_path);
        }
    }
}

static void install_hooks() {
    if (g_hooks_installed || !g_cfg.enabled) return;
    g_hooks_installed = true;

    log_msg("=== yureaka_en v2 hook init (dir=%s) ===", g_exe_dir);
    sanitize_favoice_dat();

    // 1. Register bundled Google Font TTF privately
    if (g_cfg.font_file[0]) {
        char font_full[MAX_PATH] = {};
        if (g_cfg.font_file[1] == ':') {
            std::snprintf(font_full, sizeof(font_full), "%s", g_cfg.font_file);
        } else {
            std::snprintf(font_full, sizeof(font_full), "%s\\%s", g_exe_dir, g_cfg.font_file);
        }
        int added = AddFontResourceExA(font_full, FR_PRIVATE, nullptr);
        log_msg("[Font] AddFontResourceExA(%s) -> %d", font_full, added);
    }

    // 2. Load TEXT.DAT runtime overlay (`yureaka_en.dat`) and detour RVA 0x589f0
    HMODULE hExe = GetModuleHandleA(nullptr);
    load_text_overlay();
    if (g_overlay_count > 0) {
        install_text_reader_detour(hExe);
    }

    // 3. Patch yureaka.exe IAT (LoadLibraryA/ExA + GetProcAddress catch Delay-Loaded PAL.dll!)
    if (hExe) {
        bool ok_ll = patch_iat(hExe, "KERNEL32.dll", "LoadLibraryA",
                               reinterpret_cast<void*>(&hook_LoadLibraryA),
                               reinterpret_cast<void**>(&g_orig_LoadLibraryA));
        bool ok_lle = patch_iat(hExe, "KERNEL32.dll", "LoadLibraryExA",
                                reinterpret_cast<void*>(&hook_LoadLibraryExA),
                                reinterpret_cast<void**>(&g_orig_LoadLibraryExA));
        bool ok_gpa = patch_iat(hExe, "KERNEL32.dll", "GetProcAddress",
                                reinterpret_cast<void*>(&hook_GetProcAddress),
                                reinterpret_cast<void**>(&g_orig_GetProcAddress));
        bool ok_cw = patch_iat(hExe, "USER32.dll", "CreateWindowExA",
                               reinterpret_cast<void*>(&hook_Exe_CreateWindowExA),
                               reinterpret_cast<void**>(&g_orig_Exe_CreateWindowExA));
        bool ok_sw = patch_iat(hExe, "USER32.dll", "SetWindowTextA",
                               reinterpret_cast<void*>(&hook_Exe_SetWindowTextA),
                               reinterpret_cast<void**>(&g_orig_Exe_SetWindowTextA));
        log_msg("[Hook] exe IAT: LoadLibA=%d LoadLibExA=%d GetProcAddr=%d CreateWin=%d SetTitle=%d",
                ok_ll, ok_lle, ok_gpa, ok_cw, ok_sw);
    }

    // Also check if Pal.dll happens to already be loaded
    HMODULE hPal = GetModuleHandleA("PAL.dll");
    if (hPal) {
        if (!g_orig_GetProcAddress) g_orig_GetProcAddress = &GetProcAddress;
        hook_pal_module_iat(hPal);
    }
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        if (!load_real_version()) return FALSE;
        load_config();
        install_hooks();
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_real_version) {
            FreeLibrary(g_real_version);
            g_real_version = nullptr;
        }
    }
    return TRUE;
}
