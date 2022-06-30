from PIL import Image


async def convert_img(path: str, file_name):
    img = Image.open(path)
    width, height = img.size
    if width > height:
        size = (512, 512 * height // width)
    elif height > width:
        size = (512 * width // height, 512)
    else:
        size = (512, 512)
    im_resized = img.resize(size, Image.ANTIALIAS)
    im_resized.save(file_name, "PNG")
