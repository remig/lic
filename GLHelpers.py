import Image, ImageChops
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
    glEnable(GL_MULTISAMPLE)

    setupLighting()
    setupMaterial()
    
    if doClear:
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE)
        
def adjustGLViewport(x, y, width, height, altOrtho = False):
    x = int(x)
    y = int(y)
    width = int(width)
    height = int(height)
    glViewport(x, y, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()

    # Viewing box (left, right) (bottom, top), (near, far)
    if altOrtho:
        glOrtho(0, width, 0, height, -3000, 3000 )
    else:
        width = max(1, width / 2)
        height = max(1, height / 2)
        glOrtho(-width, width, -height, height, -3000, 3000 )
        
    glMatrixMode(GL_MODELVIEW)

def rotateView(x, y, z):
    glRotatef(x, 1.0, 0.0, 0.0)
    glRotatef(y, 0.0, 1.0, 0.0)
    glRotatef(z, 0.0, 0.0, 1.0)

def rotateToView(rotation, scale, x = 0.0, y = 0.0, z = 0.0):
    # position (x,y,z), look at (x,y,z), up vector (x,y,z)
    gluLookAt(x, y, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
    glRotatef(180.0, 0.0, 0.0, 1.0)
    glScalef(scale, scale, scale)
    rotateView(*rotation)

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

def _checkImgBounds(top, bottom, left, right, size):
    if (top == 0) or (bottom == size):
        return True
    if (left == 0) or (right == size):
        return True
    return False

_imgWhite = (255, 255, 255)
def _getLeftInset(data, width, top):
    for x in range(0, width):
        if (data[x, top] != _imgWhite):
            return x
    print "Error: left inset not found!! w: %d, t: %d" % (width, top)
    return 0

def _getBottomInset(data, height, left):
    for y in range(0, height):
        if (data[left, y] != _imgWhite):
            return y
    print "Error: bottom inset not found!! h: %d, l: %d" % (height, left)
    return 0

bgCache = {}

def _getBounds(size, oglDispID, filename, defaultScale, defaultRotation, partRotation, pBuffer):
    
    # Clear the drawing buffer with white
    glClearColor(1.0, 1.0, 1.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Draw the piece in black
    glLoadIdentity()
    glColor3f(0, 0, 0)
    adjustGLViewport(0, 0, size, size)
    rotateToView(defaultRotation, defaultScale)
    rotateView(*partRotation)

    glCallList(oglDispID)

    # Use PIL to find the image's bounding box (sweet)
    pixels = glReadPixels(0, 0, size, size, GL_RGB,  GL_UNSIGNED_BYTE)
    img = Image.fromstring("RGB", (size, size), pixels)
    
    if size in bgCache:
        bg = bgCache[size]
    else:
        bg = bgCache[size] = Image.new("RGB", img.size, (255, 255, 255))
    dif = ImageChops.difference(img, bg)
    box = dif.getbbox()

    if box is None:
        return (0, 0, 0, 0, 0, 0)  # Rendered entirely out of frame

    #if filename:
        #rawFilename = os.path.splitext(os.path.basename(filename))[0]
        #img.save("C:\\lic\\tmp\\%s_%dx%d.png" % (rawFilename, w, h))
        #print fn + "box: " + str(bbox if bbox else "No box = shit")

    # Find the bottom left corner inset, used for placing PLIItem quantity labels
    data = img.load()
    leftInset = _getLeftInset(data, size, box[1])
    bottomInset = _getBottomInset(data, size, box[0])
    return box + (leftInset - box[0], bottomInset - box[1])
    
def initImgSize(size, oglDispID, filename, defaultScale, defaultRotation, partRotation, pBuffer):
    """
    Draw this piece to the already initialized GL Frame Buffer Object, in order to calculate
    its displayed width and height.  These dimensions are required to properly lay out PLIs and CSIs.
    
    Parameters:
        width: Width of buffer to render to, in pixels.
        height: Height of buffer to render to, in pixels.
        oglDispID: The GL Display List ID to be rendered and dimensioned.
        filename: String name of this thing to draw.
        defaultRotation: An [x, y, z] rotation to use for this rendering's default rotation
        partRotation: An extra [x, y, z] rotation to use when rendering this part, or None.
        pBuffer: Target FrameBufferObject context to use for rendering GL calls.
    
    Returns:
        None, if the rendered image has been rendered partially or wholly out of frame.
        Otherwise, returns the (width, height, centerPoint, leftInset, bottomInset) parameters of this image.
    """
    
    # Draw piece to frame buffer, then calculate bounding box
    left, top, right, bottom, leftInset, bottomInset = _getBounds(size, oglDispID, filename, defaultScale, defaultRotation, partRotation, pBuffer)
    
    if _checkImgBounds(top, bottom, left, right, size):
        return None  # Drew at least one edge out of bounds - try next buffer size
    
    imgWidth = right - left + 1
    imgHeight = bottom - top
    
    w = (left + (imgWidth/2)) - (size/2)
    h = (top + (imgHeight/2)) - (size/2)
    imgCenter = QPointF(-w, h - 1)

    return (imgWidth, imgHeight, imgCenter, leftInset, bottomInset)
