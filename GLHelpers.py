import Image
import os

from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt4.QtCore import QPointF

# Global constants
SCALE_WINDOW = 1.0
DEBUG = 0

def initFreshContext():
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glShadeModel(GL_SMOOTH)
    
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    
    lightPos = [100.0, 500.0, -500.0]
    ambient = [0.2, 0.2, 0.2]
    diffuse = [0.8, 0.8, 0.8]
    specular = [0.5, 0.5, 0.5]
    
    glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
    glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
    glLightfv(GL_LIGHT0, GL_SPECULAR, specular)
    
    glEnable(GL_DEPTH_TEST)
    glClearColor(1.0, 1.0, 1.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
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
    glOrtho( -width, width, height, -height, -3000, 3000 )
    glMatrixMode(GL_MODELVIEW)

def rotateViewByPoint3D(pt3D):
    rotateView(pt3D.x, pt3D.y, pt3D.z)

def rotateView(x, y, z):
    glRotatef(x, 1.0, 0.0, 0.0)
    glRotatef(y, 0.0, 1.0, 0.0)
    glRotatef(z, 0.0, 0.0, 1.0)

def rotateToDefaultView(x = 0.0, y = 0.0, z = 0.0):
    # position (x,y,z), look at (x,y,z), up vector (x,y,z)
    gluLookAt(x, y, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
    glScalef(-1.0, 1.0, 1.0)
    glScalef(SCALE_WINDOW, SCALE_WINDOW, SCALE_WINDOW)
    
    # Rotate model into something approximating the generic ortho view
    glRotatef(20.0, 1.0, 0.0, 0.0)
    glRotatef(45.0, 0.0, 1.0, 0.0)
    
def getDefaultCamera():
    return [('y', 45.0), ('x', 20)]

def rotateToPLIView(x = 0.0, y = 0.0, z = 0.0):
    # position (x,y,z), look at (x,y,z), up vector (x,y,z)
    gluLookAt(x, y, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
    glScalef(SCALE_WINDOW, SCALE_WINDOW, SCALE_WINDOW)
    
    # Rotate model into something approximating the ortho view as seen in Lego PLIs
    glRotatef(20.0, 1.0, 0.0, 0.0)
    glRotatef(45.0, 0.0, 1.0, 0.0)

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

def _checkImgMaxBounds(top, bottom, left, right, width, height, filename):
    
    if (top == 0) and (bottom == height-1): 
        if DEBUG and filename:
            print "%s - top & bottom out of bounds" % (filename)
        return True
    
    if (left == 0) and (right == width-1):
        if DEBUG and filename:
            print "%s - left & right out of bounds" % (filename)
        return True
    
    if (top == height) and (bottom == 0):
        if DEBUG and filename:
            print "%s - blank page" % (filename)
        return True
    
    if (left == width) and (right == 0):
        if DEBUG and filename:
            print "%s - blank page" % (filename)
        return True
    
    return False

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
                return i
    return height

def _checkPixelsBottom(data, width, height, top):
    for i in range(height-1, top, -1):
        for j in range(0, width):
            if (data[j, i] != _imgWhite):
                return (i, j)
    return (0, 0)

def _checkPixelsLeft(data, width, height, top, bottom):
    for i in range(0, width):
        for j in range(bottom, top, -1):
            if (data[i, j] != _imgWhite):
                return (i, j)
    return (0, 0)

def _checkPixelsRight(data, width, height, top, bottom, left):
    for i in range(width-1, left, -1):
        for j in range(top, bottom):
            if (data[i, j] != _imgWhite):
                return i
    return width

def _initImgSize_getBounds(x, y, w, h, oglDispID, filename, isCSI = False, rotStep = None, pBuffer = None):
    
    # Clear the drawing buffer with white
    glClearColor(1.0, 1.0, 1.0, 0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Draw the piece in black
    glLoadIdentity()
    glColor3f(0, 0, 0)
    adjustGLViewport(0, 0, w, h)
    if isCSI:
        rotateToDefaultView(x, y, 0.0)
        if rotStep:
            rotateViewByPoint3D(rotStep['point'])
    else:
        rotateToPLIView(x, y, 0.0)

    glCallList(oglDispID)

    if pBuffer:
        # TODO: If the old way of calculating image size, with PLI's Image, is still slow, try this pBuffer's QImage
        #if filename:
        #    rawFilename = os.path.splitext(os.path.basename(filename))[0]
        #   image = pBuffer.toImage()
        #    if image:
        #       image.save("C:\\LDraw\\tmp\\pixbuf_%s_%dx%d.png" % (rawFilename, w, h), None)
        pass

    pixels = glReadPixels (0, 0, w, h, GL_RGB,  GL_UNSIGNED_BYTE)
    img = Image.new ("RGB", (w, h), (1, 1, 1))
    img.fromstring(pixels)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    
#    if filename:
#        rawFilename = os.path.splitext(os.path.basename(filename))[0]
#       img.save("C:\\LDraw\\tmp\\%s_%dx%d.png" % (rawFilename, w, h))
    
    data = img.load()
    top = _checkPixelsTop(data, w, h)
    bottom, bottomInset = _checkPixelsBottom(data, w, h, top)
    left, leftInset = _checkPixelsLeft(data, w, h, top, bottom)
    right = _checkPixelsRight(data, w, h, top, bottom, left)
    
    return (top, bottom, left, right, bottom - leftInset, bottomInset - left)

def initImgSize(width, height, oglDispID, isCSI, filename = None, rotStep = None, pBuffer = None):
    """
    Draw this piece to the already initialized GL Frame Buffer Object, in order to calculate
    its displayed width and height.  These dimensions are required to properly lay out PLIs and CSIs.
    
    Parameters:
        width: Width of buffer to render to, in pixels.
        height: Height of buffer to render to, in pixels.
        oglDispID: The GL Display List ID to be rendered and dimensioned.
        isCSI: Need to do a few things differently if we're working with a CSI vs a PLI part.
        filename: Optional string used for debugging.
        rotStep: An optional rotation step to use when rendering this part.
    
    Returns:
        None, if the rendered image has been rendered partially or wholly out of frame.
        If isCSI is True, retuns the (width, height, centerPoint, displacementPoint) parameters of this image.
        If isCSI is False, returns the (width, height, leftInset, bottomInset, centerPoint) parameters of this image.
    """
    
    # Draw piece to frame buffer, then calculate bounding box
    top, bottom, left, right, leftInset, bottomInset = _initImgSize_getBounds(0.0, 0.0, width, height, oglDispID, filename, isCSI, rotStep, pBuffer)
    
    if _checkImgMaxBounds(top, bottom, left, right, width, height, filename):
        return None  # Drawn completely out of bounds
    
    # If we hit one of these cases, at least one edge was drawn off screen
    # Try to reposition the part and draw again, see if we can fit it on screen
    x = y = 0
    if top == 0:
        y = bottom - height + 2
    
    if bottom == height-1:
        y = top - 1
    
    if left == 0:
        x = width - right - 2
    
    if right == width-1:
        x = 1 - left
    
    if (x != 0) or (y != 0):
        # Drew at least one edge out of bounds - try moving part as much as possible and redrawing
        top, bottom, left, right, leftInset, bottomInset = _initImgSize_getBounds(x, y, width, height, oglDispID, filename, isCSI, rotStep, pBuffer)
    
    if _checkImgTouchingBounds(top, bottom, left, right, width, height, filename):
        return None  # Drew on edge out of bounds - could try another displacement, but easier to just try bigger size
    
    imgWidth = right - left + 1
    imgHeight = bottom - top + 2
    imgLeftInset = leftInset 
    imgBottomInset = bottomInset
    
    w = (left + (imgWidth/2)) - (width/2)
    h = (top + (imgHeight/2)) - (height/2)
    imgCenter = QPointF(x - w, y + h)

    return (imgWidth, imgHeight, imgCenter, imgLeftInset, imgBottomInset)
