# TODO: Get/Set these config settings through the actual GUI

# Anything after a '#' is a comment.  Backslashes '\' need to be escaped '\\'
# Lines must be in double quotation marks. Don't end a line with backslashes.

# Path to LDraw.exe and P & PARTS folder
LDrawPath = "C:\\LDraw"

# Path to l3p executable
L3P = "C:\\LDraw\\apps\\l3p\\l3p.exe"

# POV-Ray executable
# home
#POVRay = "C:\\Program Files\\POV-Ray\\bin\\pvengine.exe"

# work
POVRay = "C:\\Program Files\\POV-Ray for Windows v3.6\\bin\\pvengine.exe"

filename = ""

import os

def checkPath(pathName, root = None):
    root = root if root else modelCachePath()
    path = os.path.join(root, pathName)
    if not os.path.isdir(path):
        os.mkdir(path)
    return path

def rootCachePath():
    return checkPath('cache', os.getcwd())

def modelCachePath():
    return checkPath(os.path.basename(filename), rootCachePath())

def datCachePath():
    return checkPath('DATs')

def povCachePath():
    return checkPath('POVs')

def pngCachePath():
    return checkPath('PNGs')

def finalImageCachePath():
    return checkPath('Final_Images')

def glImageCachePath():
    return checkPath('GL_Images')

def pdfCachePath():
    return checkPath('PDFs')
