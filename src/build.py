#!/usr/bin/env python3
"""Right Property Club listing site builder.

Source:  site.json, listings/<slug>.json, photos/<slug>/*.jpg|png|webp
Output:  docs/  (served by GitHub Pages at https://<domain>/)
  docs/index.html              all live listings
  docs/p/<slug>/index.html     one page per listing
  docs/p/<slug>/<n>.jpg        compressed, watermarked photos
  docs/p/<slug>/og.jpg         WhatsApp / social link preview image
Also writes share/<slug>.txt   WhatsApp-ready message with the link.
"""
import html, json, os, shutil, sys, urllib.parse
from datetime import date
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def inr(n):
    if not n:
        return "Price on request"
    n = float(n)
    if n >= 1e7:
        v, u = n / 1e7, "Crore"
    elif n >= 1e5:
        v, u = n / 1e5, "Lakh"
    else:
        return "₹" + f"{int(n):,}"
    v = f"{v:.2f}".rstrip("0").rstrip(".")
    return f"₹{v} {u}"


def fmt_date(iso):
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%-d %b %Y")
    except Exception:
        return ""


def wa(number, text):
    d = "".join(c for c in str(number or "") if c.isdigit())
    return f"https://wa.me/{d}?text={urllib.parse.quote(text)}" if d else ""


def wa_share(text):
    return "https://wa.me/?text=" + urllib.parse.quote(text)


def enhance(im, strength=1.0):
    from PIL import ImageEnhance, ImageFilter
    im = ImageOps.autocontrast(im, cutoff=(0.5, 0.5))
    im = ImageEnhance.Brightness(im).enhance(1 + 0.04 * strength)
    im = ImageEnhance.Color(im).enhance(1 + 0.08 * strength)
    im = ImageEnhance.Contrast(im).enhance(1 + 0.05 * strength)
    return im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=int(60 * strength), threshold=3))


def process_video(slug, v, outdir):
    import subprocess
    src = os.path.join(ROOT, "photos", slug, v["src"])
    if not os.path.exists(src):
        return None
    cuts = v.get("keep", [[0, 9999]])
    parts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(cuts))
    cat = "".join(f"[v{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0[c];"
    fx = ("[c]crop=iw:ih*" + str(v.get("crop_top", 1)) + ":0:0," if v.get("crop_top") else "[c]") + "eq=contrast=1.06:brightness=0.02:saturation=1.12,unsharp=5:5:0.6,format=yuv420p[o]"
    out = os.path.join(outdir, "video.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", parts + cat + fx, "-map", "[o]", "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-movflags", "+faststart", out], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(v.get("poster_at", 0)), "-i", out, "-frames:v", "1", os.path.join(outdir, "poster.jpg")], check=True)
    return "video.mp4"


def process_photos(slug, names, outdir, brand, watermark=True, do_enhance=True):
    src_dir = os.path.join(ROOT, "photos", slug)
    out = []
    for i, name in enumerate(names, 1):
        src = os.path.join(src_dir, name)
        if not os.path.exists(src):
            print(f"  ! missing photo {src}", file=sys.stderr)
            continue
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im.thumbnail((1600, 1600))
        if do_enhance and not name.startswith("cover"):
            im = enhance(im)
        if name.startswith("cover"):
            watermark_this = False
        else:
            watermark_this = watermark
        if watermark_this:
            d = ImageDraw.Draw(im)
            fs = max(16, im.width // 38)
            f = font(FONT_BOLD, fs)
            t = "✓ CHECKED BY " + brand.upper()
            w = d.textlength(t, font=f)
            x, y = im.width - w - fs, im.height - fs * 2
            d.text((x + 1, y + 1), t, font=f, fill=(0, 0, 0))
            d.text((x, y), t, font=f, fill=(255, 255, 255))
        fn = f"{i}.jpg"
        im.save(os.path.join(outdir, fn), "JPEG", quality=80, optimize=True, progressive=True)
        out.append(fn)
    return out


def og_image(cover_path, outpath, title, price, place, sample):
    W, H = 1200, 630
    if cover_path and os.path.exists(cover_path):
        im = ImageOps.fit(Image.open(cover_path).convert("RGB"), (W, H), centering=(0.5, 0.72))
    else:
        im = Image.new("RGB", (W, H), (30, 58, 46))
    band = Image.new("RGBA", (W, 210), (20, 38, 30, 235))
    im.paste(band, (0, H - 210), band)
    d = ImageDraw.Draw(im)
    d.text((48, H - 186), title, font=font(FONT_SERIF, 46), fill=(245, 241, 231))
    d.text((48, H - 118), price, font=font(FONT_BOLD, 40), fill=(216, 183, 119))
    d.text((48, H - 62), place, font=font(FONT_BOLD, 24), fill=(186, 197, 188))
    d.text((W - 360, H - 62), "RIGHT PROPERTY CLUB", font=font(FONT_BOLD, 24), fill=(216, 183, 119))
    if sample:
        d.rectangle((40, 36, 260, 92), fill=(216, 183, 119))
        d.text((62, 46), "SAMPLE", font=font(FONT_BOLD, 34), fill=(20, 38, 30))
    im.save(outpath, "JPEG", quality=82, optimize=True)


CSS = """
:root{--bg:#F5F1E7;--surface:#FFFDF8;--ink:#17231D;--muted:#5B6860;--line:#E3DBC9;--green:#1E3A2E;--green-ink:#F5F1E7;--gold:#8E6E33;--gold-bright:#D8B777;--gold-soft:#EFE4CA;--ok:#2E6A45;--ok-soft:#DCEBDF;--warn:#875C0C;--warn-soft:#F5E6C4;
--f-display:"DM Serif Display",Georgia,"Times New Roman",serif;--f-body:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#0E1511;--surface:#161F1A;--ink:#EAE4D5;--muted:#A0AAA2;--line:#2A352E;--green:#D8B777;--green-ink:#15201A;--gold:#D8B777;--gold-soft:#332B1B;--ok:#86C79F;--ok-soft:#1C3125;--warn:#E3B95E;--warn-soft:#3A2E15;color-scheme:dark}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-body)}
a{color:inherit}img{max-width:100%;display:block}
.top{background:#1E3A2E;color:#F5F1E7}
.top .in{max-width:760px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px max(16px,env(safe-area-inset-right)) 12px max(16px,env(safe-area-inset-left))}
.logo{font-family:var(--f-display);font-size:19px;letter-spacing:.05em;text-decoration:none;white-space:nowrap}.logo span{color:#D8B777}
.top small{color:#BAC5BC;font-size:12px;text-align:right}@media (max-width:480px){.top small{display:none}}
main{max-width:760px;margin:0 auto;padding:0 max(16px,env(safe-area-inset-right)) 110px max(16px,env(safe-area-inset-left))}
.banner{background:var(--warn-soft);color:var(--warn);font-weight:600;font-size:14px;padding:10px 14px;border-radius:8px;margin-top:14px}
.sold{background:var(--ink);color:var(--bg)}
.gal{position:relative;margin:14px calc(-1*max(16px,env(safe-area-inset-left))) 0;}
.track{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none}
.track::-webkit-scrollbar{display:none}
.track img{flex:0 0 100%;width:100%;height:auto;aspect-ratio:4/3;object-fit:cover;scroll-snap-align:center;background:var(--gold-soft)}
.gal.portrait .track img{aspect-ratio:4/5;object-fit:cover}
.gal.portrait + .head{margin-top:12px}.gal.portrait .count{left:auto;right:14px;bottom:14px}
.count{position:absolute;left:14px;bottom:30px;background:rgba(0,0,0,.55);color:#fff;font-size:12px;padding:3px 9px;border-radius:999px}
@media (min-width:760px){.gal{margin:16px 0 0}.track{border-radius:12px}}
.head{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:-18px;position:relative;display:grid;gap:8px}
.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{font-family:var(--f-display);font-weight:400;font-size:clamp(26px,6vw,34px);line-height:1.15;margin:0;text-wrap:balance}
h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:26px 0 10px;font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px;background:var(--gold-soft)}
.chip.ok{background:var(--ok-soft);color:var(--ok)}.chip.warn{background:var(--warn-soft);color:var(--warn)}
.price{font-family:var(--f-display);font-size:32px;color:var(--gold);line-height:1.1;font-variant-numeric:tabular-nums}
.price small{font-family:var(--f-body);font-size:14px;color:var(--muted);margin-left:6px}
.lead{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media (min-width:560px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.cell{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:11px 12px;min-width:0}
.cell dt{font-size:12px;color:var(--muted)}.cell dd{margin:2px 0 0;font-weight:600;overflow-wrap:anywhere}
.wide{grid-template-columns:minmax(0,1fr)}
.tags{display:flex;flex-wrap:wrap;gap:8px}.tags span{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:6px 12px;font-size:14px}
.desc{white-space:pre-line}
.links{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:10px;padding:12px 16px;font-weight:600;text-decoration:none;border:1px solid var(--line);background:var(--surface);font-size:15px}
.btn.pri{background:#1E3A2E;color:#F5F1E7;border-color:#1E3A2E}
.btn.gold{background:#D8B777;color:#15201A;border-color:#D8B777}
.verify{display:flex;gap:10px;align-items:flex-start;background:var(--ok-soft);color:var(--ok);border-radius:10px;padding:12px 14px;margin-top:22px;font-size:14px}
.verify b{display:block}
.fine{color:var(--muted);font-size:13px;margin-top:18px;display:grid;gap:6px}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--surface);border-top:1px solid var(--line);padding:10px max(16px,env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) max(16px,env(safe-area-inset-left))}
.bar .in{max-width:760px;margin:0 auto;display:flex;gap:8px}.bar .btn{flex:1}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:16px;margin-top:18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;text-decoration:none;display:flex;flex-direction:column}
.card img{aspect-ratio:4/3;object-fit:cover;width:100%;height:auto}
.card .b{padding:14px;display:grid;gap:6px}
.card h3{font-family:var(--f-display);font-weight:400;font-size:21px;margin:0}
.hero{padding:26px 0 6px;display:grid;gap:8px}.hero p{color:var(--muted);max-width:60ch;margin:0}
.checked{display:inline-flex;align-items:center;gap:8px;margin-top:14px;background:#1E3A2E;color:#F5F1E7;border:1px solid #D8B777;border-radius:999px;padding:7px 14px;font-weight:600;font-size:14px}.checked span{color:#D8B777}
.concept{margin:12px 0 0;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}.concept img{width:100%;height:auto;max-height:80vh;object-fit:cover}.concept figcaption{padding:10px 12px;font-size:13px;color:var(--muted)}.concept b{display:block;color:var(--ink);font-size:15px;margin-bottom:2px}
@media (min-width:760px){.gal.portrait{max-width:520px;margin-left:auto;margin-right:auto}.concept{max-width:520px}}
.plotfig{margin:0;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px}.plotfig svg{width:100%;height:auto;display:block}.plotfig figcaption{font-size:12px;color:var(--muted);padding:4px 6px 0}
.vid{width:100%;max-height:70vh;border-radius:10px;background:#000}
.why{margin-top:8px}.why h3{font-size:16px;margin:18px 0 8px}
.ticks,.growth,.check{margin:0;padding-left:0;list-style:none;display:grid;gap:8px}
.ticks li{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px 10px 34px;position:relative}.ticks li::before{content:"✓";position:absolute;left:12px;color:var(--ok);font-weight:700}
.growth li{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.src{font-size:12px;color:var(--muted)}
.check{counter-reset:c}.check li{counter-increment:c;padding-left:30px;position:relative}.check li::before{content:counter(c);position:absolute;left:0;top:1px;width:20px;height:20px;border-radius:50%;background:var(--gold-soft);font-size:12px;text-align:center;line-height:20px;font-weight:600}
:focus-visible{outline:2px solid #D8B777;outline-offset:2px}
"""

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;600&display=swap">'

WA_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2c-1.5 0-3-.4-4.3-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.4.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.4.1-.7.3-.2.3-.9.9-.9 2.2s.9 2.5 1 2.7c.1.2 1.8 2.8 4.4 3.9 1.6.7 2.3.8 3.1.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.4-.2Z"/></svg>'


def header(site):
    return (f'<header class="top"><div class="in"><a class="logo" href="/">RIGHT PROPERTY <span>CLUB</span></a>'
            f'<small>{e(site["tagline"])}</small></div></header>')


def dl(rows, wide=False):
    rows = [r for r in rows if r and r[1]]
    if not rows:
        return ""
    return f'<dl class="grid{" wide" if wide else ""}">' + "".join(
        f'<div class="cell"><dt>{e(k)}</dt><dd>{e(v)}</dd></div>' for k, v in rows) + "</dl>"


def plot_svg(L):
    d = L.get("plot")
    if not d:
        return ""
    W, H = 360, 260
    lf, bf = float(d["length_ft"]), float(d["breadth_ft"])
    k = min(240 / lf, 150 / bf)
    pw, ph = lf * k, bf * k
    x0, y0 = (W - pw) / 2, 40
    road = d.get("road_side", "bottom")
    rl = d.get("road_label", "Access road")
    ry = y0 + ph + 26
    return f"""<figure class="plotfig"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Plot diagram {e(d['length_ft'])} by {e(d['breadth_ft'])} feet">
<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="var(--gold-soft)" stroke="var(--gold)" stroke-width="2"/>
<text x="{W/2}" y="{y0+ph/2-4}" text-anchor="middle" font-size="16" font-weight="600" fill="var(--ink)">{e(d.get('area_label',''))}</text>
<text x="{W/2}" y="{y0+ph/2+16}" text-anchor="middle" font-size="12" fill="var(--muted)">{e(d['length_ft'])} ft × {e(d['breadth_ft'])} ft</text>
<line x1="{x0}" y1="{y0-14}" x2="{x0+pw}" y2="{y0-14}" stroke="var(--muted)"/><text x="{W/2}" y="{y0-20}" text-anchor="middle" font-size="12" fill="var(--muted)">{e(d['length_ft'])} ft</text>
<line x1="{x0+pw+14}" y1="{y0}" x2="{x0+pw+14}" y2="{y0+ph}" stroke="var(--muted)"/><text x="{x0+pw+20}" y="{y0+ph/2+4}" font-size="12" fill="var(--muted)">{e(d['breadth_ft'])} ft</text>
{f'<rect x="{x0-20}" y="{y0+ph+8}" width="{pw+40}" height="30" fill="var(--line)"/><text x="{W/2}" y="{ry+2}" text-anchor="middle" font-size="12" fill="var(--ink)">{e(rl)}</text>' if road=="bottom" else ''}
</svg><figcaption>Indicative sketch from the stated dimensions. Not to scale for survey purposes.{(" " + e(d["note"])) if d.get("note") else ""}</figcaption></figure>"""


def plot_layout(L):
    if not L.get("plot"):
        return ""
    h = "<h2>Plot layout</h2>" + plot_svg(L)
    c = L.get("concept")
    if c:
        h += (f'<figure class="concept"><img src="{e(c["src"])}" alt="{e(c.get("alt","Indicative home design"))}" loading="lazy" width="720" height="1280">'
              f'<figcaption><b>{e(c.get("title","What you could build here"))}</b>{e(c.get("caption",""))}</figcaption></figure>')
    return h


def video_block(L):
    if not L.get("video_file"):
        return ""
    return f'<h2>Video walkthrough</h2><video class="vid" src="{e(L["video_file"])}" controls playsinline preload="metadata" poster="{e(L.get("video_poster",""))}"></video>'


def why_block(L):
    w = L.get("why")
    if not w:
        return ""
    h = ""
    if w.get("benefits"):
        h += '<h2>Why this property</h2><ul class="ticks">' + "".join(f"<li>{e(x)}</li>" for x in w["benefits"]) + "</ul>"
    if w.get("location"):
        h += '<h2>Location advantages</h2><ul class="ticks">' + "".join(f"<li>{e(x)}</li>" for x in w["location"]) + "</ul>"
    if w.get("growth"):
        h += '<h2>Growth drivers nearby</h2><ul class="growth">' + "".join(
            f'<li><span class="chip {"ok" if g.get("status","").lower().startswith("operational") else "warn"}">{e(g.get("status",""))}</span> {e(g["text"])}'
            + (f' <a class="src" href="{e(g["src"])}" target="_blank" rel="noopener">Source</a>' if g.get("src") else "") + "</li>" for g in w["growth"]) + "</ul>"
        h += '<p class="fine">Infrastructure helps a location but does not guarantee price growth. Right Property Club does not promise returns or appreciation.</p>'
    return h


def listing_page(site, slug, L, photos):
    base = f'https://{site["domain"]}'
    url = f"{base}/p/{slug}/"
    price = inr(L.get("price"))
    place = ", ".join(x for x in [L.get("locality"), L.get("city")] if x)
    title = L.get("page_title") or f'{L["title"]} for Sale in {L.get("locality","")}'.strip() if L.get("deal", "For Sale") == "For Sale" else L["title"]
    sold = L.get("status") in ("Sold", "Withdrawn")
    enquire = wa(site["whatsapp"], f'Hi Right Property Club, I am interested in {L["title"]}, {place} ({L["id"]}).' + (' Please share the price and details.' if not L.get("price") else '') + f' {url}')
    share_text = f'{L["title"]} in {place} – {price}.\nView all photos & details: {url}'
    desc = f'{price} · {place}. ' + (L.get("headline") or "")
    gal = "".join(f'<img src="{p}" alt="{e(L["title"])} photo {i}" {"" if i == 1 else "loading=lazy"} width="1600" height="1200">' for i, p in enumerate(photos, 1))
    verified = fmt_date(L.get("verified_on", ""))
    links = []
    if L.get("video"):
        links.append(f'<a class="btn" href="{e(L["video"])}" target="_blank" rel="noopener">▶ Watch video tour</a>')
    if L.get("map_link"):
        links.append(f'<a class="btn" href="{e(L["map_link"])}" target="_blank" rel="noopener">{"View area on Google Maps" if L.get("map_indicative") else "Open in Google Maps"}</a>')
    noindex = '<meta name="robots" content="noindex">' if L.get("sample") else ""
    banner = ""
    if L.get("sample"):
        banner = '<div class="banner">Sample listing for layout preview. This is not a real property.</div>'
    if L.get("draft"):
        banner = '<div class="banner">DRAFT PREVIEW – not published. Items marked ⚠ need confirmation.</div>'
        noindex = '<meta name="robots" content="noindex">'
    if sold:
        banner += f'<div class="banner sold">This property is no longer available ({e(L["status"]).lower()}). See our current listings on the home page.</div>'
    bar_btns = []
    if enquire and not sold:
        bar_btns.append(f'<a class="btn pri" href="{e(enquire)}" target="_blank" rel="noopener">{WA_ICON} Enquire on WhatsApp</a>')
    bar_btns.append(f'<a class="btn" href="{e(wa_share(share_text))}" target="_blank" rel="noopener">Share</a>')
    return f"""<!doctype html><html lang="en-IN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)} | {price} | Right Property Club</title>
<meta name="description" content="{e(desc)}">{noindex}
<meta property="og:type" content="website"><meta property="og:site_name" content="Right Property Club">
<meta property="og:title" content="{e(L['title'])} – {e(price)}"><meta property="og:description" content="{e(place)}. View all photos and details.">
<meta property="og:url" content="{url}"><meta property="og:image" content="{url}og.jpg"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><link rel="canonical" href="{url}"><meta name="theme-color" content="#1E3A2E">
{FONTS}<style>{CSS}</style></head><body>
{header(site)}
<main>{banner}
{f'<div class="checked"><span>✓</span> Checked by Right Property Club</div>' if verified and not L.get('sample') else ''}
<div class="gal{' portrait' if L.get('portrait') else ''}"><div class="track">{gal}</div>{f'<span class="count">{len(photos)} photos · swipe</span>' if len(photos) > 1 else ''}</div>
{f'<p class="fine" style="text-align:center">{e(L["media_note"])}</p>' if L.get('media_note') else ''}
<section class="head"><div class="eyebrow">📍 {e(L.get('landmark') + ' · ' if L.get('landmark') else '')}{e(place)}</div>
<h1>{e(title)}</h1>
<div class="chips"><span class="chip">{e(L.get('deal','For Sale'))}</span><span class="chip">{e(L.get('type',''))}</span>{'<span class="chip ok">✓ Verified</span>' if verified else ''}<span class="chip">{e(L['id'])}</span></div>
<div class="price">{e(price)}{f"<small>{e(L['price_note'])}</small>" if L.get('price_note') and L.get('price') else ''}</div>
{f'<div class="eyebrow">≈ ₹{int(L["price"]/L["size_sqyd"]):,} per sq yd</div>' if L.get('price') and L.get('size_sqyd') else ''}
{f'<div class="links" style="margin-top:4px"><a class="btn gold" href="{e(enquire)}" target="_blank" rel="noopener">{WA_ICON} Get the price on WhatsApp</a></div>' if not L.get('price') and enquire and not sold else ''}
</section>
{'<h2>About this property</h2><p class="desc">' + e(L['description']) + '</p>' if L.get('description') else ''}
{''.join('<h2>' + e(h) + '</h2>' + dl(rows, wide=(len(rows) < 3)) for h, rows in L.get('sections', []))}
{'<h2>Property overview</h2>' + dl(L.get('overview', [])) if L.get('overview') else ''}
{'<h2>Interior &amp; status</h2>' + dl(L.get('interior', [])) if L.get('interior') else ''}
{plot_layout(L)}
{why_block(L)}
{'<h2>Amenities</h2><div class="tags">' + ''.join(f'<span>{e(a)}</span>' for a in L['amenities']) + '</div>' if L.get('amenities') else ''}
{video_block(L)}
{('<h2>Location map</h2><div class="links">' + ''.join(links) + '</div>') if links else ''}
{'<p class="fine">Map shows the general area only. The exact location is shared on request or during a site visit.</p>' if L.get('map_indicative') else ('' if L.get('map_link') else '<p class="fine">Exact location is shared on request or during a site visit.</p>')}
<div class="fine">{f"<p>HARERA project registration: {e(L['rera'])}</p>" if L.get('rera') else ''}<p>{e(site['disclaimer'])}</p>{f"<p>HARERA agent registration: {e(site['agent_rera'])}</p>" if site.get('agent_rera') else ''}{f'<p>Call or WhatsApp: {e(site["phone_display"])}</p>' if site.get('phone_display') else ''}<p>Listing ID {e(L['id'])}</p></div>
</main>
<div class="bar"><div class="in">{''.join(bar_btns)}</div></div>
</body></html>"""


def index_page(site, cards):
    base = f'https://{site["domain"]}'
    ask = wa(site["whatsapp"], "Hi Right Property Club, I am looking for a property. My requirement: ")
    body = "".join(cards) if cards else '<p class="lead">New verified listings are on the way.</p>'
    return f"""<!doctype html><html lang="en-IN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Right Property Club | Verified Property Listings</title>
<meta name="description" content="Verified plots, floors and apartments. Find the Right Property. The Right Way.">
<meta property="og:title" content="Right Property Club"><meta property="og:description" content="Verified property listings. Find the Right Property. The Right Way."><meta property="og:url" content="{base}/">
<link rel="canonical" href="{base}/"><meta name="theme-color" content="#1E3A2E">{FONTS}<style>{CSS}</style></head><body>
{header(site)}<main><section class="hero"><div class="eyebrow">Verified listings</div><h1>Find the Right Property. The Right Way.</h1>
<p>We list a property only after the owner or developer authorises us and we have checked its details.</p>
{f'<div class="links"><a class="btn gold" href="{e(ask)}" target="_blank" rel="noopener">{WA_ICON} Share your requirement</a></div>' if ask else ''}</section>
<div class="cards">{body}</div><div class="fine"><p>Call or WhatsApp: <a href="tel:+{e(site['whatsapp'])}">{e(site['phone_display'])}</a></p><p>{e(site['disclaimer'])}</p></div></main></body></html>"""


def card(slug, L, cover):
    price = inr(L.get("price"))
    place = ", ".join(x for x in [L.get("locality"), L.get("city")] if x)
    img = f'<img src="/p/{slug}/{cover}" alt="" loading="lazy">' if cover else ""
    flag = '<span class="chip warn">Sample</span>' if L.get("sample") else ""
    return (f'<a class="card" href="/p/{slug}/">{img}<div class="b"><div class="chips">{flag}<span class="chip">{e(L.get("type",""))}</span></div>'
            f'<h3>{e(L["title"])}</h3><div class="eyebrow">{e(place)}</div><div class="price" style="font-size:24px">{e(price)}</div></div></a>')


def main():
    site = json.load(open(os.path.join(ROOT, "site.json")))
    show_samples = "--with-samples" in sys.argv
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    os.makedirs(os.path.join(ROOT, "share"), exist_ok=True)
    cards = []
    ldir = os.path.join(ROOT, "listings")
    for fn in sorted(os.listdir(ldir)):
        if not fn.endswith(".json"):
            continue
        slug = fn[:-5]
        L = json.load(open(os.path.join(ldir, fn)))
        pdir = os.path.join(OUT, "p", slug)
        os.makedirs(pdir)
        photos = process_photos(slug, L.get("photos", []), pdir, site["brand"], L.get("watermark", True), L.get("enhance", True))
        if L.get("video_src"):
            vf = process_video(slug, L["video_src"], pdir)
            if vf:
                L["video_file"], L["video_poster"] = vf, "poster.jpg"
        og_image(os.path.join(pdir, photos[1] if (len(photos) > 1 and L.get("photos", [""])[0].startswith("cover")) else photos[0]) if photos else None, os.path.join(pdir, "og.jpg"),
                 L["title"], inr(L.get("price")), ", ".join(x for x in [L.get("locality"), L.get("city")] if x), L.get("sample"))
        import hashlib
        vq = lambda f: f + "?v=" + hashlib.md5(open(os.path.join(pdir, f), "rb").read()).hexdigest()[:8]
        if L.get("video_file"):
            L["video_file"], L["video_poster"] = vq(L["video_file"]), vq(L["video_poster"])
        if L.get("concept_src"):
            shutil.copy(os.path.join(ROOT, "photos", slug, L["concept_src"]), os.path.join(pdir, "concept.jpg"))
            L["concept"]["src"] = vq("concept.jpg")
        open(os.path.join(pdir, "index.html"), "w").write(listing_page(site, slug, L, [vq(f) for f in photos]))
        url = f'https://{site["domain"]}/p/{slug}/'
        msg = (f'🏡 {L["title"]} – {L.get("locality","")}\n💰 {inr(L.get("price"))}\n'
               + "".join(f"• {v}\n" for k, v in (L.get("overview", [])[:3] + L.get("interior", [])[:2]) if v)
               + f'\n👉 View all photos & details:\n{url}\n\nReply here to book a site visit. – Right Property Club')
        open(os.path.join(ROOT, "share", slug + ".txt"), "w").write(msg)
        live = L.get("status", "Available") == "Available" and not L.get("draft") and (show_samples or not L.get("sample"))
        if live:
            cards.append(card(slug, L, photos[0] if photos else ""))
        print(f"built /p/{slug}/  ({len(photos)} photos){'  [on home page]' if live else ''}")
    open(os.path.join(OUT, "index.html"), "w").write(index_page(site, cards))
    open(os.path.join(OUT, "CNAME"), "w").write(site["domain"] + "\n")
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    open(os.path.join(OUT, "404.html"), "w").write(index_page(site, cards).replace("<h1>Find the Right Property. The Right Way.</h1>", "<h1>That listing is not available</h1>"))
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n")


if __name__ == "__main__":
    main()
