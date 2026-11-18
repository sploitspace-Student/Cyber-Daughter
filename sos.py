"""Tombol darurat untuk HP anak (Termux, Android).

Dipakai dengan sepengetahuan dan persetujuan anak.

Penggunaan:
  python sos.py sos      -> kirim peringatan darurat + lokasi ke orang tua
  python sos.py sampai   -> kirim kabar "sudah sampai dengan selamat" + lokasi
  python sos.py aman     -> kirim kabar "aku baik-baik saja" + lokasi

Pengaturan ada di config.env (BOT_TOKEN, CHAT_ID, NAMA).
Hanya memakai library bawaan Python.
"""

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PESAN = {
    "sos": "SOS! {nama} menekan tombol darurat. Hubungi sekarang.",
    "sampai": "{nama} sudah sampai dengan selamat.",
    "aman": "{nama} mengabarkan: aku baik-baik saja.",
}


def muat_env(nama_file="config.env"):
    path = os.path.join(BASE_DIR, nama_file)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for baris in f:
            baris = baris.strip()
            if not baris or baris.startswith("#") or "=" not in baris:
                continue
            kunci, nilai = baris.split("=", 1)
            os.environ.setdefault(kunci.strip(), nilai.strip().strip('"').strip("'"))


muat_env()
TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
NAMA = os.environ.get("NAMA", "Anak")


def termux(perintah, timeout=10):
    try:
        return subprocess.run(perintah, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def toast(teks):
    termux(["termux-toast", teks])


def getar():
    termux(["termux-vibrate", "-d", "300"])


def api(metode, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{metode}"
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(url, data=data, timeout=20) as resp:
        return json.loads(resp.read().decode())


def kirim_dengan_ulang(metode, percobaan=3, **params):
    """Coba beberapa kali supaya tahan sinyal yang putus-putus."""
    for _ in range(percobaan):
        try:
            api(metode, **params)
            return True
        except Exception:
            continue
    return False


def ambil_lokasi():
    """Network dulu (cepat), lalu GPS, lalu lokasi terakhir yang tersimpan."""
    percobaan = [
        (["termux-location", "-p", "network"], 15, False),
        (["termux-location", "-p", "gps"], 30, False),
        (["termux-location", "-p", "passive", "-r", "last"], 10, True),
    ]
    for perintah, batas, lama in percobaan:
        hasil = termux(perintah, batas)
        if hasil and hasil.stdout.strip():
            try:
                data = json.loads(hasil.stdout)
            except json.JSONDecodeError:
                continue
            if "latitude" in data:
                data["_lama"] = lama
                return data
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "sos"
    if mode not in PESAN:
        print("Mode tidak dikenal. Pilih: sos, sampai, aman")
        return
    if not TOKEN or not CHAT_ID:
        toast("config.env belum diisi")
        print("BOT_TOKEN dan CHAT_ID belum diisi di config.env")
        return

    getar()
    toast("Mengirim...")

    # 1) Kabar dikirim SEGERA, tanpa menunggu lokasi.
    teks = PESAN[mode].format(nama=NAMA)
    terkirim = kirim_dengan_ulang("sendMessage", chat_id=CHAT_ID, text=teks)

    # 2) Lalu lokasi menyusul.
    lokasi = ambil_lokasi()
    if lokasi:
        lat, lon = lokasi["latitude"], lokasi["longitude"]
        catatan = f"Akurasi: {lokasi.get('accuracy', '?')} m ({lokasi.get('provider', '?')})"
        if lokasi.get("_lama"):
            catatan += " - ini lokasi TERAKHIR yang tersimpan, bukan yang terbaru"
        kirim_dengan_ulang("sendLocation", chat_id=CHAT_ID, latitude=lat, longitude=lon)
        kirim_dengan_ulang(
            "sendMessage",
            chat_id=CHAT_ID,
            text=f"{catatan}\nhttps://maps.google.com/?q={lat},{lon}",
            disable_web_page_preview="true",
        )
    elif terkirim:
        kirim_dengan_ulang("sendMessage", chat_id=CHAT_ID, text="Lokasi belum berhasil didapat.")

    if terkirim:
        getar()
        toast("Terkirim ke orang tua")
    else:
        toast("GAGAL terkirim. Cek internet lalu coba lagi")


if __name__ == "__main__":
    main()
