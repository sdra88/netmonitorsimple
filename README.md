# NetSpeed Monitor

Widget kecepatan jaringan (Mbps) yang menempel di taskbar Windows 11, satu widget
per monitor, tepat di sebelah kiri tombol Start. Background transparan, teks
click-through (klik taskbar tetap jalan).

![contoh tampilan](docs/preview.png)

## Fitur

- Satu widget per monitor (monitor utama + semua monitor tambahan).
- Posisi tetap di sebelah kiri tombol Start.
- Background transparan, teks bisa diganti warna/ukuran/font.
- Ikon system tray: Settings, Enable/Disable, Start with Windows, Exit.
- Tanpa dependensi pihak ketiga (stdlib + ctypes).

## Pakai (versi .exe — tanpa install Python)

1. Taruh `NetSpeedMonitor.exe` di folder tetap, mis. `C:\NetSpeedMonitor\`.
2. Jalankan `NetSpeedMonitor.exe`. Muncul ikon di system tray + widget di taskbar.
3. `config.json` dibuat otomatis di folder yang sama saat pertama jalan.

Klik ikon tray (kiri atau kanan) untuk menu:

| Menu | Fungsi |
|---|---|
| Settings... | panel ganti font, ukuran, warna, enable, auto start |
| Enable monitor | nyala/matikan widget (centang = aktif) |
| Start with Windows | tulis/hapus entri `HKCU\...\CurrentVersion\Run` |
| Exit | keluar total |

Catatan: kalau folder dipindah, jalankan lagi sekali — entri autostart menunjuk
path exe, jadi path lama akan gagal. Ulangi centang *Start with Windows*.

## Pakai (versi .py — butuh Python 3)

```
pythonw netspeed.py
```

`pythonw` (bukan `python`) supaya tidak ada jendela console.

## Isi config.json

| Key | Arti | Default |
|---|---|---|
| `enabled` | widget aktif | `true` |
| `font` | nama font | `Segoe UI` |
| `size` | ukuran font (8-30) | `13` |
| `color` | warna teks `#RRGGBB` | `#FFFFFF` |
| `refresh_ms` | interval ukur (ms) | `1000` |
| `layout_ms` | interval cek posisi taskbar (ms) | `2000` |

Ubah dari panel Settings, atau edit file lalu Exit + jalankan lagi.

## Build ulang .exe

```
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name NetSpeedMonitor netspeed.py
```

Hasil di `dist\NetSpeedMonitor.exe`.

## Struktur

| File | Isi |
|---|---|
| `netspeed.py` | seluruh program (widget, tray, settings, autostart) |
| `NetSpeedMonitor.exe` | versi terkompilasi, tanpa perlu Python |
| `Start.bat` | peluncur, taruh di samping exe |
| `grab.py` | util dev: screenshot satu region ke BMP untuk verifikasi tampilan |

## Catatan teknis

- Sumber angka: `GetIfTable2` (iphlpapi), jumlah `InOctets`/`OutOctets` NIC fisik
  aktif, didedupe per MAC. ×8 ÷ detik ÷ 1e6 = Mbps.
- Widget = layered popup topmost + `WS_EX_TRANSPARENT`, jadi tidak menghalangi klik
  taskbar dan tidak muncul di Alt-Tab.
- Teks digambar ke DIB 32-bit lalu `UpdateLayeredWindow`, alpha dihitung ulang per
  piksel supaya latar benar-benar transparan di warna taskbar apa pun.
- Build satu file butuh ~2-4 detik saat start pertama (ekstrak bundle ke temp).
