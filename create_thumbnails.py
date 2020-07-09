from PIL import Image
import glob, os

size = 128, 128

extensions = [
  "**/*.jpg",
  "**/*.png"
]

for ext in extensions:
  for infile in glob.glob(ext):
    file, ext = os.path.splitext(infile)
    if file.endswith('-thumbnail'):
      continue
    im = Image.open(infile)
    im.thumbnail(size)
    im.save(file + '-thumbnail' + ext)
