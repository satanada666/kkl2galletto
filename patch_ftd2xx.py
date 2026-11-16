# -*- coding: utf-8 -*-
"""
Программная замена диода TXD-DTR для Galletto 1260 на обычном VAG KKL (FT232).

Что делает:
  В таблице экспорта FTD2XX.dll (той, что лежит в папке Galletto) переадресует
      FT_SetDtr -> FT_SetBreakOn   (K-линия прижимается к нулю)
      FT_ClrDtr -> FT_SetBreakOff  (K-линия отпущена)
  Galletto будит ЭБУ, дёргая DTR. В кабеле Galletto DTR через диод тянет TXD
  к нулю. Break делает то же самое с TXD программно, поэтому паять не нужно.

Использование:
  python patch_ftd2xx.py "C:\\путь\\к\\GALLETTO_1260"           - пропатчить
  python patch_ftd2xx.py "C:\\путь\\к\\GALLETTO_1260" --restore - вернуть оригинал
  python patch_ftd2xx.py "C:\\путь\\к\\GALLETTO_1260" --check   - показать состояние

Перед патчем оригинал сохраняется как FTD2XX_original.dll (если его ещё нет).
"""
import os
import shutil
import struct
import sys

SWAP = (("FT_SetDtr", "FT_SetBreakOn"), ("FT_ClrDtr", "FT_SetBreakOff"))


def read_exports(data):
    if data[:2] != b"MZ":
        raise ValueError("не PE-файл")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("не PE-файл")
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x10B:
        raise ValueError("ожидалась 32-битная DLL")
    exp_rva = struct.unpack_from("<I", data, opt + 96)[0]
    secs = []
    for i in range(nsec):
        s = opt + optsz + 40 * i
        vsize, va, rsize, roff = struct.unpack_from("<IIII", data, s + 8)
        secs.append((va, max(vsize, rsize), roff))

    def off(rva):
        for va, size, roff in secs:
            if va <= rva < va + size:
                return rva - va + roff
        raise ValueError("RVA вне секций: %#x" % rva)

    e = off(exp_rva)
    _, n_names, a_funcs, a_names, a_ords = struct.unpack_from("<IIIII", data, e + 20)
    result = {}
    for i in range(n_names):
        name_off = off(struct.unpack_from("<I", data, off(a_names) + 4 * i)[0])
        name = data[name_off:data.index(0, name_off)].decode("ascii")
        ordinal = struct.unpack_from("<H", data, off(a_ords) + 2 * i)[0]
        slot = off(a_funcs) + 4 * ordinal
        result[name] = (slot, struct.unpack_from("<I", data, slot)[0])
    return result


def state(exports):
    if all(exports[a][1] == exports[b][1] for a, b in SWAP):
        return "patched"
    if all(exports[a][1] != exports[b][1] for a, b in SWAP):
        return "original"
    return "mixed"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    folder = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--patch"
    dll = os.path.join(folder, "FTD2XX.dll")
    backup = os.path.join(folder, "FTD2XX_original.dll")

    if mode == "--restore":
        if not os.path.exists(backup):
            print("Нет FTD2XX_original.dll - восстанавливать нечего.")
            return 1
        shutil.copyfile(backup, dll)
        print("Оригинальная FTD2XX.dll возвращена.")
        return 0

    data = bytearray(open(dll, "rb").read())
    exports = read_exports(data)
    missing = [n for pair in SWAP for n in pair if n not in exports]
    if missing:
        print("В DLL нет функций:", ", ".join(missing))
        return 1
    st = state(exports)
    print("Сейчас FTD2XX.dll:", {"patched": "ПРОПАТЧЕНА (без диода)",
                                  "original": "оригинальная",
                                  "mixed": "частично изменена (?)"}[st])
    if mode == "--check":
        return 0
    if st == "patched":
        print("Патч уже стоит, ничего не меняю.")
        return 0
    if st != "original":
        print("DLL в странном состоянии. Сначала --restore.")
        return 1
    if not os.path.exists(backup):
        shutil.copyfile(dll, backup)
        print("Оригинал сохранён:", backup)
    for src, dst in SWAP:
        struct.pack_into("<I", data, exports[src][0], exports[dst][1])
    with open(dll, "wb") as f:
        f.write(data)
    if state(read_exports(bytes(data))) != "patched":
        print("ОШИБКА: проверка после записи не прошла.")
        return 1
    print("Готово: FT_SetDtr -> FT_SetBreakOn, FT_ClrDtr -> FT_SetBreakOff.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
