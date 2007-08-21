from OpenGL.GL import *
from OpenGL.GLU import *

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
