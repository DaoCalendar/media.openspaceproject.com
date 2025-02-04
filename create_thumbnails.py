from PIL import Image
import glob, os

size = 256, 256

extensions = [
  "**/*.jpg",
  "**/*.png"
]

for ext in extensions:
  for infile in glob.glob(ext, recursive=True):
    file, ext = os.path.splitext(infile)
    if file.endswith('-thumbnail'):
      continue
    im = Image.open(infile)
    im.thumbnail(size)
    im.save(file + '-thumbnail' + ext)
