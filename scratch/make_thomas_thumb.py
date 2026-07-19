import os
from PIL import Image, ImageEnhance
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frames_dir = os.path.join(REPO, "output", "thomas_1h", "frames")

# Elegir un frame donde el atractor de thomas se ve increíble (ej. 300)
frame_path = os.path.join(frames_dir, "0300.png")

if not os.path.exists(frame_path):
    print("Frame 300 no existe!")
    sys.exit(1)

img = Image.open(frame_path).convert("RGB")

# Pequeño boost de contraste y saturación para que brille aún más
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.1)

enhancer2 = ImageEnhance.Color(img)
img = enhancer2.enhance(1.2)

out_path = r"C:\Users\sunse\.gemini\antigravity\brain\3e24b39e-9a8d-491e-a653-8cd9f3d3adc2\thomas_thumbnail.jpg"
img.save(out_path, quality=95)
print(f"Thumbnail guardado en {out_path}")
