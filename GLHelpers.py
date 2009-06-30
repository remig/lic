import Image
import os

from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt4.QtCore import QPointF

DEBUG = 0

def drawCoordLines(length = 20.0):
    glPushAttrib(GL_CURRENT_BIT)
    
    glBegin(GL_LINES)
    glColor4f(1.0, 0.0, 0.0, 1.0)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(length, 0.0, 0.0)
    
    glColor4f(0.0, 1.0, 0.0, 1.0)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(0.0, length, 0.0)
    
    glColor4f(0.0, 0.0, 1.0, 1.0)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(0.0, 0.0, length)
    glEnd()
    glPopAttrib()

def setupLight(light):
    glLightfv(GL_LIGHT0, GL_SPECULAR, [0.0, 0.0, 0.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0])
    glLightfv(GL_LIGHT0, GL_POSITION, [0.0, 100.0, 100.0])
    glEnable(GL_LIGHT0)

def setupLighting():
    glDisable(GL_NORMALIZE)
    glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
    glEnable(GL_LIGHTING)
    
    maxLights = glGetIntegerv(GL_MAX_LIGHTS)
    for i in range(0, maxLights):
        glDisable(GL_LIGHT0 + i)

    setupLight(GL_LIGHT0)
    glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 1.0)
    glLightf(GL_LIGHT0, GL_LINEAR_ATTENUATION, 0.0)
    glLightf(GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 0.0)
    
    glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, 1)
    
def setupMaterial():
    glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, [0.0, 0.0, 0.0, 1.0])
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [0.0, 0.0, 0.0, 1.0])
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 64.0)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_COLOR_MATERIAL)

def initFreshContext(doClear):
    
    glLightModeli(GL_LIGHT_MODEL_LOCAL_VIEWER, 0)
    glShadeModel(GL_SMOOTH)
    glEnable(GL_CULL_FACE)
    glEnable(GL_MULTISAMPLE)
    glFrontFace(GL_CCW)
    
    setupLighting()
    setupMaterial()
    
    if doClear:
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE)
        
def adjustGLViewport(x, y, width, height):
    x = int(x)
    y = int(y)
    width = int(width)
    height = int(height)
    glViewport(x, y, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    width = max(1, width / 2)
    height = max(1, height / 2)

    # Viewing box (left, right) (bottom, top), (near, far)
    glOrtho( -width, width, -height, height, -3000, 3000 )
    glMatrixMode(GL_MODELVIEW)

def rotateView(x, y, z):
    glRotatef(x, 1.0, 0.0, 0.0)
    glRotatef(y, 0.0, 1.0, 0.0)
    glRotatef(z, 0.0, 0.0, 1.0)

def rotateToDefaultView(x = 0.0, y = 0.0, z = 0.0, scale = 1.0):
    # position (x,y,z), look at (x,y,z), up vector (x,y,z)
    gluLookAt(x, y, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
    glRotatef(180.0, 0.0, 0.0, 1.0)
    glScalef(scale, scale, scale)
    
    # Rotate model into something approximating the generic ortho view
    glRotatef(20.0, 1.0, 0.0, 0.0)
    glRotatef(45.0, 0.0, 1.0, 0.0)
    
def getDefaultCamera():
    return [('y', 45.0), ('x', 20)]

def rotateToPLIView(x = 0.0, y = 0.0, z = 0.0, scale = 1.0):
    # position (x,y,z), look at (x,y,z), up vector (x,y,z)
    gluLookAt(x, y, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
    glRotatef(180.0, 0.0, 0.0, 1.0)
    glScalef(scale, scale, scale)
    
    # Rotate model into something approximating the ortho view as seen in Lego PLIs
    glRotatef(20.0, 1.0, 0.0, 0.0)
    glRotatef(-45.0, 0.0, 1.0, 0.0)

def getPLICamera():
    return [('y', -45.0), ('x', 20)]

def pushAllGLMatrices():
    glPushAttrib(GL_TRANSFORM_BIT | GL_VIEWPORT_BIT)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()

def popAllGLMatrices():
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glPopAttrib()

def _checkImgTouchingBounds(top, bottom, left, right, width, height, filename):
    
    if (top == 0) or (bottom == height-1):
        if DEBUG and (filename) and (top == 0):
            print "%s - top out of bounds" % (filename)
        if DEBUG and (filename) and (bottom == height-1):
            print "%s - bottom out of bounds" % (filename)
        return True
    
    if (left == 0) or (right == width-1):
        if DEBUG and (filename) and (left == 0):
            print "%s - left out of bounds" % (filename)
        if DEBUG and (filename) and (right == width-1):
            print "%s - right out of bounds" % (filename)
        return True
    
    return False

_imgWhite = (255, 255, 255)
def _checkPixelsTop(data, width, height):
    for i in range(0, height):
        for j in range(0, width):
            if (data[j, i] != _imgWhite):
                return (i, j)
    return (height, 0)

def _checkPixelsBottom(data, width, height, top):
    for i in range(height-1, top, -1):
        for j in range(0, width):
            if (data[j, i] != _imgWhite):
                return i
    return 0

def _checkPixelsLeft(data, width, height, top, bottom):
    for i in range(0, width):
        for j in range(top, bottom):
            if (data[i, j] != _imgWhite):
                return (i, j)
    return (0, 0)

def _checkPixelsRight(data, width, height, top, bottom, left):
    for i in range(width-1, left, -1):
        for j in range(top, bottom):
            if (data[i, j] != _imgWhite):
                return i
    return width

def _initImgSize_getBounds(x, y, w, h, oglDispID, filename, isCSI = False, rotation = None, pBuffer = None):
    
    # Clear the drawing buffer with white
    glClearColor(1.0, 1.0, 1.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Draw the piece in black
    glLoadIdentity()
    glColor3f(0, 0, 0)
    adjustGLViewport(0, 0, w, h)
    if isCSI:
        rotateToDefaultView(x, y, 0.0)
        if rotation:
            rotateView(*rotation)
    else:
        rotateToPLIView(x, y, 0.0)

    glCallList(oglDispID)

#    if pBuffer and filename:
#        rawFilename = os.path.splitext(os.path.basename(filename))[0]
#        image = pBuffer.toImage()
#        if image:
#            image.save("C:\\Lic\\tmp\\pixbuf_%s_%dx%d.png" % (rawFilename, w, h), None)

    pixels = glReadPixels (0, 0, w, h, GL_RGB,  GL_UNSIGNED_BYTE)
    img = Image.new("RGB", (w, h), (1, 1, 1))
    img.fromstring(pixels)

    #img = img.transpose(Image.FLIP_TOP_BOTTOM)
    #if filename:
    #    rawFilename = os.path.splitext(os.path.basename(filename))[0]
    #    img.save("C:\\lic\\tmp\\%s_%dx%d.png" % (rawFilename, w, h))
    
    data = img.load()
    top, leftInset = _checkPixelsTop(data, w, h)
    bottom  = _checkPixelsBottom(data, w, h, top)
    left, bottomInset = _checkPixelsLeft(data, w, h, top, bottom)
    right = _checkPixelsRight(data, w, h, top, bottom, left)
    
    return (top, bottom, left, right, leftInset - left, bottomInset - top)

def initImgSize(width, height, oglDispID, isCSI, filename = None, rotation = None, pBuffer = None):
    """
    Draw this piece to the already initialized GL Frame Buffer Object, in order to calculate
    its displayed width and height.  These dimensions are required to properly lay out PLIs and CSIs.
    
    Parameters:
        width: Width of buffer to render to, in pixels.
        height: Height of buffer to render to, in pixels.
        oglDispID: The GL Display List ID to be rendered and dimensioned.
        isCSI: Need to do a few things differently if we're working with a CSI vs a PLI part.
        filename: Optional string used for debugging.
        rotation: An optional [x, y, z] rotation to use when rendering this part.
    
    Returns:
        None, if the rendered image has been rendered partially or wholly out of frame.
        If isCSI is True, returns the (width, height, centerPoint, displacementPoint) parameters of this image.
        If isCSI is False, returns the (width, height, leftInset, bottomInset, centerPoint) parameters of this image.
    """
    
    # Draw piece to frame buffer, then calculate bounding box
    top, bottom, left, right, leftInset, bottomInset = _initImgSize_getBounds(0.0, 0.0, width, height, oglDispID, filename, isCSI, rotation, pBuffer)
    
    if _checkImgTouchingBounds(top, bottom, left, right, width, height, filename):
        return None  # Drew on edge out of bounds - try next size
    
    imgWidth = right - left + 1
    imgHeight = bottom - top + 2
    
    w = (left + (imgWidth/2)) - (width/2)
    h = (top + (imgHeight/2)) - (height/2)
    imgCenter = QPointF(-w, h)

    return (imgWidth, imgHeight, imgCenter, leftInset, bottomInset)
