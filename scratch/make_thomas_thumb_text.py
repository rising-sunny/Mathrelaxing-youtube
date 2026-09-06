import os
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import font_path, thumbnail_path  # noqa: E402

frames_dir = os.path.join(REPO, "output", "thomas_1h", "frames")
frame_path = os.path.join(frames_dir, "0300.png")

if not os.path.exists(frame_path):
    print("Frame 300 no existe!")
    sys.exit(1)

img = Image.open(frame_path).convert("RGB")

# Pequeño boost de contraste y saturación
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.1)

enhancer2 = ImageEnhance.Color(img)
img = enhancer2.enhance(1.2)

# Oscurecer un poco la parte izquierda para que resalte el texto (vignette o gradiente sutil)
# Como Pillow puro es complejo para gradientes, simplemente dibujaremos el texto con sombra (Drop Shadow).
draw = ImageDraw.Draw(img)
W, H = img.size

# Tipografias resueltas segun el sistema (ver tools/paths.py)
try:
    font_large = ImageFont.truetype(font_path("bold"), 140)
    font_small = ImageFont.truetype(font_path("regular"), 60)
except:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

def draw_text_with_shadow(draw, text, position, font, text_color, shadow_color=(0, 0, 0, 200), shadow_offset=(5, 5)):
    x, y = position
    # Sombra
    draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=shadow_color)
    draw.text((x + shadow_offset[0]+2, y + shadow_offset[1]+2), text, font=font, fill=shadow_color)
    # Texto principal
    draw.text((x, y), text, font=font, fill=text_color)

# Texto impactante y minimalista
text1 = "1 HOUR"
text2 = "DEEP FOCUS"
text3 = "THOMAS ATTRACTOR"

# Posicionamiento (Izquierda, centrado verticalmente)
margin_x = 100
start_y = H // 2 - 150

draw_text_with_shadow(draw, text1, (margin_x, start_y), font_large, (255, 255, 255))
draw_text_with_shadow(draw, text2, (margin_x, start_y + 160), font_large, (0, 230, 255)) # Cyan eléctrico que combina con el atractor
draw_text_with_shadow(draw, text3, (margin_x + 10, start_y + 330), font_small, (200, 200, 200))

out_path = thumbnail_path("thomas_thumbnail_text.jpg")
img.save(out_path, quality=95)
print(f"Thumbnail guardado en {out_path}")
