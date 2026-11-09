"""Ad-style cover generator. Usage: python3 tools/cover.py out.jpg "TAG" "HEADLINE" "LOCATION" "chip1|chip2|chip3" [base.jpg]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build import font, FONT_BOLD, FONT_SERIF
from PIL import Image, ImageDraw
out, tag, head, loc, chips = sys.argv[1:6]
base = sys.argv[6] if len(sys.argv) > 6 else os.path.join(os.path.dirname(__file__), "..", "gen", "cover-base.jpg")
W, H = 1080, 1350
bg = Image.new("RGB", (W, H), (16, 32, 25)); bg.paste(Image.open(base).convert("RGB").resize((W, 900)), (0, 0))
grad = Image.new("L", (W, 320)); g = ImageDraw.Draw(grad)
for y in range(320): g.line((0, y, W, y), fill=int(255 * (y / 319) ** 1.3))
bg.paste(Image.new("RGB", (W, 320), (16, 32, 25)), (0, 580), grad)
top = Image.new("L", (W, 180)); g = ImageDraw.Draw(top)
for y in range(180): g.line((0, y, W, y), fill=int(150 * (1 - y / 180)))
bg.paste(Image.new("RGB", (W, 180), (16, 32, 25)), (0, 0), top)
d = ImageDraw.Draw(bg)
GOLD, IVORY, MUTED = (216, 183, 119), (245, 241, 231), (196, 205, 198)
f = font(FONT_BOLD, 32); tw = d.textlength(tag, font=f)
d.rounded_rectangle((56, 56, 56 + tw + 64, 122), 33, fill=GOLD); d.text((56 + (tw + 64) / 2, 89), tag, font=f, fill=(16, 32, 25), anchor="mm")
t = "✓ CHECKED BY RIGHT PROPERTY CLUB"; f = font(FONT_BOLD, 24); tw = d.textlength(t, font=f)
d.rounded_rectangle((W - 56 - tw - 40, 62, W - 56, 116), 27, fill=(16, 32, 25), outline=GOLD, width=2); d.text((W - 56 - tw / 2 - 20, 89), t, font=f, fill=GOLD, anchor="mm")
y = 760
d.text((60, y), "Your future home", font=font(FONT_SERIF, 70), fill=IVORY)
d.text((60, y + 84), "starts with the right plot.", font=font(FONT_SERIF, 62), fill=GOLD)
fs = 40
while d.textlength(head, font=font(FONT_BOLD, fs)) > W - 120: fs -= 2
d.text((60, y + 190), head, font=font(FONT_BOLD, fs), fill=IVORY)
fs = 32
while d.textlength(loc, font=font(FONT_BOLD, fs)) > W - 120: fs -= 2
d.text((60, y + 244), loc, font=font(FONT_BOLD, fs), fill=MUTED)
x = 60; cy = y + 302
for c in chips.split("|"):
    f = font(FONT_BOLD, 27); tw = d.textlength(c, font=f)
    d.rounded_rectangle((x, cy, x + tw + 38, cy + 52), 26, outline=GOLD, width=2); d.text((x + 19, cy + 26), c, font=f, fill=IVORY, anchor="lm"); x += tw + 52
d.line((60, H - 150, W - 60, H - 150), fill=(70, 92, 80), width=2)
d.text((60, H - 104), "DM / WhatsApp for price", font=font(FONT_BOLD, 32), fill=IVORY, anchor="lm")
d.text((60, H - 58), "+91 93108 84844", font=font(FONT_BOLD, 34), fill=GOLD, anchor="lm")
d.text((W - 60, H - 90), "RIGHT PROPERTY CLUB", font=font(FONT_SERIF, 30), fill=GOLD, anchor="rm")
bg.save(out, quality=90)
