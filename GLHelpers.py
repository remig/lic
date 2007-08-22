import Image

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL.EXT.framebuffer_object import *

# Global constants
SCALE_WINDOW = 1

def adjustGLViewport(x, y, width, height):
	glViewport(x, y, width, height)
	glMatrixMode(GL_PROJECTION)
	glLoadIdentity()
	#viewing box (left, right) (bottom, top), (near, far)
	width /= 2 * SCALE_WINDOW
	height /= 2 * SCALE_WINDOW
	width = max(1, width)
	height = max(1, height)
	glOrtho( -width, width, -height, height, -3000, 3000 )
	glMatrixMode(GL_MODELVIEW)

def rotateToDefaultView(x = 0.0, y = 0.0, z = 0.0):
	# position (x,y,z), look at (x,y,z), up vector (x,y,z)
	gluLookAt(x, y, -1000.0,  x, y, z,  0.0, -1.0, 0.0)
	
	# Rotate model into something approximating the regular ortho Lego view.
	# TODO: Figure out the exact rotation for this.
	glRotatef(20.0, 1.0, 0.0, 0.0,)
	glRotatef(135.0, 0.0, 1.0, 0.0,)

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
	if status != GL_FRAMEBUFFER_COMPLETE_EXT:
		print "Error in framebuffer activation"
		destroyFBO(texture, framebuffer)
		return

	return (texture, framebuffer)
	
def destroyFBO(texture, framebuffer):
	glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, 0)
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)
	glDeleteTextures(texture)
	glDeleteFramebuffersEXT(1, [framebuffer])
