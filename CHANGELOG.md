# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/) dan
[Semantic Versioning](https://semver.org/lang/id/).

## [1.1.0] - 2026-11-15

### Ditambahkan

- Versi program (`VERSION`), muncul di tooltip tray, judul panel Settings, dan
  `netspeed.py --version`.
- Ikon aplikasi: digambar sendiri di kode (glyph panah bawah/atas), tertanam di
  `NetSpeedMonitor.exe` dan dipakai untuk ikon system tray.
- Metadata Windows pada exe (Properties → Details): FileVersion, ProductName,
  CompanyName, FileDescription.
- `make_ico.py`: util dev untuk merender ikon menjadi `.ico` multi-ukuran
  (16/24/32/48/64/128/256).

### Diubah

- `config.json` disimpan di samping exe saat dijalankan sebagai build PyInstaller
  (sebelumnya bisa nyasar ke folder temp bundle).

## [1.0.0] - 2026-11-15

### Ditambahkan

- Widget kecepatan jaringan (Mbps) di taskbar Windows 11, satu widget per monitor,
  posisi tetap di sebelah kiri tombol Start.
- Background transparan per piksel, teks click-through sehingga klik taskbar tetap
  jalan.
- Ikon system tray: Settings, Enable monitor, Start with Windows, Exit.
- Panel Settings: ganti font, ukuran (8-30), warna teks, enable/disable, autostart.
- Autostart via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- Build satu file `.exe`, tanpa perlu Python terinstall.

[1.1.0]: https://github.com/sdra88/netmonitorsimple/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sdra88/netmonitorsimple/releases/tag/v1.0.0
