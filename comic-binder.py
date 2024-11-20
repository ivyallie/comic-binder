import os.path
from PIL import Image, ImageFont, ImageDraw
import zipfile
import io
from datetime import datetime
import img2pdf
import argparse
from yaml import safe_load
from math import ceil

argparser = argparse.ArgumentParser(description='Assemble graphic novel from source files')
argparser.add_argument('projectfile',help='The YAML file that defines the project')
argparser.add_argument('--force',help='Disregard dates and regenerate all pages',action='store_true')
argparser.add_argument('--pdfonly',help='Regenerate PDF but not images',action='store_true')
argparser.add_argument('--suppress_annotations',help='Do not stamp pages with filenames or memos',action='store_true',default=False)
argparser.add_argument('--booklet',help='Override booklet setting',action=argparse.BooleanOptionalAction)
argparser.add_argument('--output',help='Output filename')

arguments = argparser.parse_args()

with open(arguments.projectfile,"r") as f:
    project = safe_load(f)

settings = project['project']
defaults = project['defaults']
directories = project['directories']
pages = project['pages']


staging_dir = os.path.normpath(settings['staging'])

universal_defaults = {
    'memo': None,
    'type': 'image'
}


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
    sub_dimension = get_value_or_default(page,'sub_dimension')
    if mode=='mono':
        image = image.resize(sub_dimension, Image.LANCZOS)
        threshold = 129
        image = image.point(lambda p: p > threshold and 255)
    else:
        image = image.resize(sub_dimension, Image.NEAREST)
    return image

def image_displace(image,is_verso):
    page_dimension = get_value_or_default(page,'page_dimension')
    recto = get_value_or_default(page,'recto_displace')
    verso = get_value_or_default(page,'verso_displace')
    vertical = get_value_or_default(page,'vertical_displace')
    recto_displace = (recto,vertical)
    verso_displace = (verso,vertical)
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
    page_dimension = get_value_or_default(page,'page_dimension')
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
    page_dimension = get_value_or_default(page,'page_dimension')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/TTF/Inconsolata-Regular.ttf',76)
    if margin=='top':
        position = (page_dimension[0] / 2, page_dimension[1] - (page_dimension[1] - 135))
    else:
        position = (page_dimension[0]/2,page_dimension[1]-135)
    draw.text(position,stamp,font=font)
    return image

def CreateBlankPage():
    page_dimension = get_value_or_default(page,'page_dimension')
    image = Image.new('L',page_dimension,'white')
    image = image.convert('1')
    return image

def img_to_pdf_from_list(list,filename):
    print("Assembling PDF",filename)
    files = [f for f in list if os.path.isfile(f)]
    #print(files)
    files.sort()
    with open(filename,'wb') as f:
        f.write(img2pdf.convert(files))
    return filename

def get_value_or_default(dictionary,value_name):
    value = dictionary.get(value_name)
    optional_defaults = ['memo']
    if not value:
        try:
            value = defaults[value_name]
        except KeyError:
            try:
                value = universal_defaults[value_name]
            except KeyError:
                print('Default for',value_name,'not defined! Abort.')
                quit()
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
        if get_value_or_default(page,'filenames'):
            image=StampImage(image,source_file)
        if get_value_or_default(page,'memos'):
            memo = get_value_or_default(page,'memo')
            if memo:
                image=StampImage(image,memo,margin='top')
    return image

def get_image_or_blank(file):
    if file=='blank':
        return CreateBlankPage()
    else:
        return Image.open(file)

def make_booklet_sheet(file1,file2,booklet_page_dimension):
    page_dimension = defaults.get('page_dimension')
    image1 = get_image_or_blank(file1)
    image2 = get_image_or_blank(file2)
    sheet_image = Image.new(image1.mode, booklet_page_dimension)
    sheet_image.paste(image1,(0,0))
    sheet_image.paste(image2,(page_dimension[0],0))
    return sheet_image


def get_setting(setting):
    try:
        setting_value = settings[setting]
        return setting_value
    except KeyError:
        print('Setting',setting,'must be defined!')

def next_multiple_of_four(value):
    return (ceil(value) + 3) & ~0x03

def add_blank_pages(pages,signature_length):
    blank_pages_needed = signature_length - len(pages)
    if blank_pages_needed:
        global blank_pages_added
        blank_pages_added = True
        blanks = ['blank'] * blank_pages_needed
        pages.extend(blanks)
    return pages


def make_booklet():
    signatures = get_setting('booklet_signatures')
    booklet_content = output_files
    if not signatures or signatures == 1:
        signature_length = next_multiple_of_four(len(booklet_content))
        booklet_content = add_blank_pages(booklet_content,signature_length)
        make_signature(booklet_content,get_output_filename())
    if signatures > 1:
        pages_per_signature = next_multiple_of_four(len(booklet_content)/signatures)
        signatures_content = define_signatures(booklet_content,pages_per_signature)
        for iter, signature in enumerate(signatures_content):
            general_output_filename = os.path.splitext(get_output_filename())
            signature_filename = general_output_filename[0]+"_"+str(iter).zfill(3)+general_output_filename[1]
            signature_content = add_blank_pages(signatures_content[iter],pages_per_signature)
            make_signature(signature_content,signature_filename)


def define_signatures(imagelist,pages_per_signature):
    signatures = []
    for i in range(0,len(imagelist),pages_per_signature):
        signature = imagelist[i:i + pages_per_signature]
        signatures.append(signature)
    return signatures


def make_signature(imagelist,outputfile):
    page_dimension = defaults.get('page_dimension')
    signature_sheets_files = []
    booklet_page_dimension = (page_dimension[0] * 2, page_dimension[1])
    booklet_sheets = len(imagelist) / 2

    sheet = 0
    while sheet < booklet_sheets:
        iter = sheet + 1
        if not iter % 2:  # recto
            image1 = imagelist[iter - 1]
            image2 = imagelist[len(imagelist) - iter]
        else:
            image2 = imagelist[iter - 1]
            image1 = imagelist[len(imagelist) - iter]
        booklet_sheet_image = make_booklet_sheet(image1, image2, booklet_page_dimension)
        booklet_sheet_number = str(sheet).zfill(3)
        booklet_sheet_file_name = 'booklet_sheet_' + booklet_sheet_number
        booklet_sheet_file_path = os.path.join(staging_dir, booklet_sheet_file_name + '.tif')
        booklet_sheet_image_output_file = os.path.abspath(booklet_sheet_file_path)
        booklet_sheet_image.save(booklet_sheet_image_output_file, dpi=(defaults['dpi'], defaults['dpi']),
                                 compression='tiff_lzw')
        signature_sheets_files.append(booklet_sheet_file_path)
        sheet += 1
    img_to_pdf_from_list(signature_sheets_files, outputfile)

def get_output_filename():
    if arguments.output is not None:
        output = os.path.normpath(arguments.output)
    else:
        output = os.path.normpath(settings['output'])
    return output



new = 0

if arguments.booklet is not None:
    booklet = arguments.booklet
else:
    booklet = settings.get('booklet')

output_files = []

for page_number, page in enumerate(pages):
    file_digits = f"{page_number:03d}"
    output_file = os.path.abspath(os.path.join(staging_dir, 'ao_' + file_digits + '.tif'))
    output_files.append(output_file)
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
    dpi = get_value_or_default(page,'dpi')
    page_image.save(output_file, dpi=(dpi, dpi), compression='tiff_lzw')


if new or arguments.pdfonly:
    if booklet:
        print('Making booklet...')
        blank_pages_added = False
        make_booklet()
        if blank_pages_added:
            print('Warning: Blank pages were added to round page count.')
    else:
        output=get_output_filename()
        imagelist = output_files
        img_to_pdf_from_list(imagelist,output)
else:
    print('No update needed')

