import os.path
from PIL import Image, ImageFont, ImageDraw
import zipfile
import io
from datetime import datetime
import img2pdf
import argparse
from yaml import safe_load

argparser = argparse.ArgumentParser(description='Assemble graphic novel from source files')
argparser.add_argument('projectfile',help='The YAML file that defines the project')
argparser.add_argument('--force',help='Disregard dates and regenerate all pages',action='store_true')
argparser.add_argument('--pdfonly',help='Regenerate PDF but not images',action='store_true')
argparser.add_argument('--suppress_annotations',help='Do not stamp pages with filenames or memos',action='store_true',default=False)

arguments = argparser.parse_args()

with open(arguments.projectfile,"r") as f:
    project = safe_load(f)

settings = project['project']
defaults = project['defaults']
directories = project['directories']
pages = project['pages']


staging_dir = os.path.normpath(settings['staging'])
sub_dimension = settings['sub_dimension']
page_dimension = settings['page_dimension']


def compareFileTime(file1,file2):
    # Returns the file which has been modified most recently
    try:
        file1_time = os.path.getmtime(file1)
        file2_time = os.path.getmtime(file2)
        if file1_time > file2_time:
            return file1
        else:
            return file2
    except FileNotFoundError:
        return False

def image_resize(image,mode):
    if mode=='mono':
        image = image.resize(sub_dimension, Image.LANCZOS)
        threshold = 129
        image = image.point(lambda p: p > threshold and 255)
    else:
        image = image.resize(sub_dimension, Image.NEAREST)
    return image

def image_displace(image,is_verso):
    d = settings['displacement']
    recto_displace = (d['recto'],d['vertical'])
    verso_displace = (d['verso'],d['vertical'])
    if is_verso:
        displacement = verso_displace
    else:
        displacement = recto_displace
    image = addMargin(image,page_dimension,displacement)
    return image

def extractMergedImageFromKRA(kra):
    archive = zipfile.ZipFile(kra,'r')
    extract_image = archive.read('mergedimage.png')
    image = Image.open(io.BytesIO(extract_image))
    return image

def addMargin(image,dimensions,displace):
    canvas = Image.new('L',dimensions,'white')
    canvas.paste(image, displace)
    return canvas

def CreateFrontMatter():
    image = Image.new('L', page_dimension, 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/TTF/Inconsolata-Regular.ttf', 76)
    time = datetime.now()
    draw.text((700, 700), settings['title']+" by "+settings['author']+"\nThis version compiled on " + time.strftime("%d %b %Y at %I:%M %p"),
              'black', font=font)
    image = image.point(lambda p: p > 129 and 255)
    image = image.convert('1')
    return image

def StampImage(image,stamp,margin=''):
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/TTF/Inconsolata-Regular.ttf',76)
    if margin=='top':
        position = (page_dimension[0] / 2, page_dimension[1] - (page_dimension[1] - 135))
    else:
        position = (page_dimension[0]/2,page_dimension[1]-135)
    draw.text(position,stamp,font=font)
    return image

def CreateBlankPage():
    image = Image.new('L',page_dimension,'white')
    image = image.convert('1')
    return image

def img_to_pdf(filename):
    print("Assembling PDF")
    #filename = os.path.normpath(filename)
    files = [f for f in os.listdir(staging_dir) if os.path.isfile(os.path.join(staging_dir, f))]
    images = []
    files.sort()
    with open(filename,'wb') as f:
        for file in files:
            if os.path.splitext(file)[1] == '.tif':
                path = os.path.join(staging_dir, file)
                images.append(path)
        f.write(img2pdf.convert(images))
    return filename

def get_value_or_default(dictionary,value_name):
    value = dictionary.get(value_name)
    if not value:
        value = defaults.get(value_name)
    return value

def image_needs_update(page,output_file):
    directory_index = get_value_or_default(page, 'dir')
    image_file = get_value_or_default(page, 'file')
    directory = directories[directory_index]
    input_file = os.path.join(directory, image_file)
    newer = compareFileTime(input_file, output_file)
    if newer != output_file or arguments.force:
        return True
    else:
        return False

def process_imagefile(page,page_number):
    directory_index = get_value_or_default(page,'dir')
    image_file = get_value_or_default(page,'file')
    colorspace = get_value_or_default(page,'colorspace')
    directory = directories[directory_index]
    source_file = os.path.join(directory,image_file)
    print('Processing:', image_file)
    if os.path.splitext(source_file)[1] == '.kra':
        image = extractMergedImageFromKRA(source_file)
    else:
        image = Image.open(source_file)
    image = image_resize(image,colorspace) #Resize image
    image = image_displace(image,(page_number % 2) == 0)
    if not arguments.suppress_annotations:
        if settings.get('filenames'):
            image=StampImage(image,source_file)
        if settings.get('memos'):
            memo = get_value_or_default(page,'memo')
            if memo:
                image=StampImage(image,memo,margin='top')
    return image


new = 0

for page_number, page in enumerate(pages):
    file_digits = f"{page_number:03d}"
    output_file = os.path.abspath(os.path.join(staging_dir, 'ao_' + file_digits + '.tif'))
    page_type = get_value_or_default(page,'type')
    if page_type == 'frontmatter':
        page_image = CreateFrontMatter()
    elif page_type == 'blank':
        page_image = CreateBlankPage()
    elif page_type == 'image':
        if image_needs_update(page,output_file):
            new = 1
            page_image = process_imagefile(page,page_number)
        else:
            continue
    else:
        page_image = CreateBlankPage()
        page_image=StampImage(page_image,'Invalid page type '+str(page_type),margin='top')
    page_image.save(output_file, dpi=(settings['dpi'], settings['dpi']), compression='tiff_lzw')

if new or arguments.pdfonly:
    img_to_pdf(settings['output'])
else:
    print('No update needed')

