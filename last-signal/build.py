"""Build last-signal.html: inline every asset as WebP data URI into one file.

Usage: python3 last-signal/build.py
"""
import base64, io, json, os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'last-signal-assets')
SRC = os.path.join(ROOT, 'last-signal', 'game.html')
OUT = os.path.join(ROOT, 'last-signal.html')


def webp(path, size=None, quality=82):
    im = Image.open(path)
    im = im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB')
    if size:
        im = im.resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=quality, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()


def small_mp3(path, music):
    """Re-encode to a smaller MP3: music 112 kbps stereo, effects 80 kbps mono."""
    try:
        import miniaudio, lameenc
    except ImportError:
        return open(path, 'rb').read()
    ch = 2 if music else 1
    d = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=ch, sample_rate=44100)
    enc = lameenc.Encoder()
    enc.set_bit_rate(112 if music else 80); enc.set_in_sample_rate(44100); enc.set_channels(ch); enc.set_quality(2)
    return bytes(enc.encode(d.samples.tobytes()) + enc.flush())


def main():
    assets = {}
    for folder, prefix, size in (('characters', '', None), ('zombies', '', None), ('items', 'item_', None), ('backgrounds', 'bg_', (1280, 720))):
        d = os.path.join(ASSETS, folder)
        for f in sorted(os.listdir(d)):
            name, ext = os.path.splitext(f)
            if ext.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                assets[prefix + name] = webp(os.path.join(d, f), size, 80 if size else 85)
    snd = os.path.join(ASSETS, 'sounds')
    for f in sorted(os.listdir(snd)) if os.path.isdir(snd) else []:
        name, ext = os.path.splitext(f)
        if ext.lower() == '.mp3':
            assets['snd_' + name] = 'data:audio/mpeg;base64,' + base64.b64encode(small_mp3(os.path.join(snd, f), name.startswith('music_'))).decode()
    html = open(SRC, encoding='utf-8').read()
    html = html.replace('/*ASSETS*/{}', json.dumps(assets))
    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'{len(assets)} assets, {os.path.getsize(OUT) / 1e6:.1f} MB -> {OUT}')


if __name__ == '__main__':
    main()
