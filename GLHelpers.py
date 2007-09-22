import Image
import os

from Drawables import Point

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL.EXT.framebuffer_object import *

# Global constants
SCALE_WINDOW = 1

def adjustGLViewport(x, y, width, height):
	x = int(x)
	y = int(y)
	width = int(width)
	height = int(height)
	glViewport(x, y, width, height)
	glMatrixMode(GL_PROJECTION)
	glLoadIdentity()
	width = max(1, width / 2 * SCALE_WINDOW)
	height = max(1, height / 2 * SCALE_WINDOW)
	# Viewing box (left, right) (bottom, top), (near, far)
	glOrtho( -width, width, -height, height, -3000, 3000 )
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
	
	# Rotate model into something approximating the generic ortho view
	glRotatef(20.0, 1.0, 0.0, 0.0)
	glRotatef(45.0, 0.0, 1.0, 0.0)
	
def getDefaultCamera():
	return [('y', 45.0), ('x', 20)]

def rotateToPLIView(x = 0.0, y = 0.0, z = 0.0):
	# position (x,y,z), look at (x,y,z), up vector (x,y,z)
	gluLookAt(x, y, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
	glScalef(-1.0, 1.0, 1.0)
	
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

def createFBO(width, height):
	"""
	Creates a new Frame Buffer Object of specified width and height (in pixels).
	This rendering buffer is independent of any display resolution & size, which means
	we can create it arbitrarily large.  Perfect for rendering parts to calculate their
	eventual drawn dimensions.
	
	Returns a tuple consisting of all objects that need to be destroyed by destroyFBO.
	So, just store the returned value then pass it right back to destroyFBO for easy cleanup.
	"""
	
	# Setup frame buffer
	framebuffer = glGenFramebuffersEXT(1)
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, framebuffer)
	
	# Need a temporary image hanging around for the glTexImage2D call below to work
	image = Image.new ("RGB", (width, height), (1, 1, 1))
	bits = image.tostring("raw", "RGBX", 0, -1)
	
	# Setup depth buffer
	depthbuffer = glGenRenderbuffersEXT(1)
	glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, depthbuffer)
	glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, GL_DEPTH_COMPONENT, width, height)
	
	# Create texture to render to
	texture = glGenTextures (1)
	glBindTexture(GL_TEXTURE_2D, texture)
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, bits)
	
	# Bind texture to frame buffer
	glFramebufferTexture2DEXT(GL_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT, GL_TEXTURE_2D, texture, 0);
	glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, GL_DEPTH_ATTACHMENT_EXT, GL_RENDERBUFFER_EXT, depthbuffer);
	
	status = glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT);
	if (status != 0) and (status != GL_FRAMEBUFFER_COMPLETE_EXT):
		print "Error in framebuffer activation.  Status: %d, expected %d" % (status, GL_FRAMEBUFFER_COMPLETE_EXT)
		destroyFBO(texture, framebuffer)
		return None

	return (texture, framebuffer)
	
def destroyFBO(texture, framebuffer):
	glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, 0)
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)
	glDeleteTextures(texture)
	glDeleteFramebuffersEXT(1, [framebuffer])

def _checkImgMaxBounds(top, bottom, left, right, width, height, filename):
	
	if (top == 0) and (bottom == height-1): 
		if (filename):
			print "%s - top & bottom out of bounds" % (filename)
		return True
	
	if (left == 0) and (right == width-1):
		if (filename):
			print "%s - left & right out of bounds" % (filename)
		return True
	
	if (top == height) and (bottom == 0):
		if (filename):
			print "%s - blank page" % (filename)
		return True
	
	if (left == width) and (right == 0):
		if (filename):
			print "%s - blank page" % (filename)
		return True
	
	return False

def _checkImgTouchingBounds(top, bottom, left, right, width, height, filename):
	
	if (top == 0) or (bottom == height-1):
		if (filename) and (top == 0):
			print "%s - top out of bounds" % (filename)
		if (filename) and (bottom == height-1):
			print "%s - bottom out of bounds" % (filename)
		return True
	
	if (left == 0) or (right == width-1):
		if (filename) and (left == 0):
			print "%s - left out of bounds" % (filename)
		if (filename) and (right == width-1):
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

def _initImgSize_getBounds(x, y, w, h, oglDispID, filename, isCSI = False, rotStep = None):
	
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
	
	pixels = glReadPixels (0, 0, w, h, GL_RGB,  GL_UNSIGNED_BYTE)
	img = Image.new ("RGB", (w, h), (1, 1, 1))
	img.fromstring(pixels)
	if filename:
		rawFilename = os.path.splitext(os.path.basename(filename))[0]
		img.save ("C:\\LDraw\\tmp\\%s.png" % (rawFilename))
	
	data = img.load()
	top = _checkPixelsTop(data, w, h)
	bottom, bottomInset = _checkPixelsBottom(data, w, h, top)
	left, leftInset = _checkPixelsLeft(data, w, h, top, bottom)
	right = _checkPixelsRight(data, w, h, top, bottom, left)
	
	return (top, bottom, left, right, bottom - leftInset, bottomInset - left)

def initImgSize(width, height, oglDispID, isCSI, filename = None, rotStep = None):
	"""
	Draw this piece to the already initialized GL Frame Buffer Object, in order to calculate
	its displayed width and height.  These dimensions are required to properly lay out PLIs and CSIs.
	Note that an appropriate FBO *must* be initialized before calling initSize.
	
	Parameters:
		width: Width of FBO to render to, in pixels.
		height: Height of FBO to render to, in pixels.
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
	top, bottom, left, right, leftInset, bottomInset = _initImgSize_getBounds(0.0, 0.0, width, height, oglDispID, filename, isCSI, rotStep)
	
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
		top, bottom, left, right, leftInset, bottomInset = _initImgSize_getBounds(x, y, width, height, oglDispID, filename, isCSI, rotStep)
	
	if _checkImgTouchingBounds(top, bottom, left, right, width, height, filename):
		return None  # Drew on edge out of bounds - could try another displacement, but easier to just try bigger size
	
	imgWidth = right - left + 1
	imgHeight = bottom - top + 2
	imgLeftInset = leftInset 
	imgBottomInset = bottomInset
	
	w = (left + (imgWidth/2)) - (width/2)
	h = (top + (imgHeight/2)) - (height/2)
	imgCenter = Point(x - w, y + h)

	if isCSI:
		return (imgWidth, imgHeight, imgCenter)
	else:
		return (imgWidth, imgHeight, imgLeftInset, imgBottomInset, imgCenter)
