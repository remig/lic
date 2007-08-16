import math
import gtk
import gtk.glade
import gtk.gtkgl
import gobject

import Image

from LDrawColors import *
from LDrawFileFormat import *

from OpenGL.GL import *
from OpenGL.GLU import *

# Global constants
UNINIT_OGL_DISPID = -1
UNINIT_PROP = -1
SCALE_WINDOW = 2

MODEL_NAME = "pyramid.dat"
#MODEL_NAME = "Blaster.mpd"

gui_xml = gtk.glade.XML( "c:\\LDraw\\LIC\\LIC.glade")

def adjustGLViewport(x, y, width, height):
	glViewport(x, y, width, height)
	glMatrixMode(GL_PROJECTION)
	glLoadIdentity()
	#viewing box (left, right) (bottom, top), (near, far)
	glOrtho( -(width/SCALE_WINDOW), width/SCALE_WINDOW, -(height/SCALE_WINDOW), height/SCALE_WINDOW, -3000, 3000 )
	glMatrixMode(GL_MODELVIEW)
	
def restoreGLViewport():
	# restoreGLViewport.width & height set by on_configure_event, when window resized
	adjustGLViewport(0, 0, restoreGLViewport.width, restoreGLViewport.height)
	
def rotateToDefaultView(x = 0.0, y = 0.0, z = 0.0):
	# position (x,y,z), look at (x,y,z), up vector (x,y,z)
	gluLookAt(0.0, 0.0, -1000.0,  x, y, z,  0.0, 1.0, 0.0)
	glScalef(1.0, -1.0, -1.0)
	
	# Rotate model into something approximating the regular ortho Lego view.
	# TODO: Figure out the exact rotation for this.
	glRotatef( -20.0, 1.0, 0.0, 0.0,)
	glRotatef( -135.0, 0.0, 1.0, 0.0,)

class DrawArea(gtk.DrawingArea, gtk.gtkgl.Widget):
	def __init__(self):
		gtk.DrawingArea.__init__(self)
		
		self.set_events(gtk.gdk.BUTTON_MOTION_MASK  | gtk.gdk.KEY_PRESS_MASK |
						gtk.gdk.KEY_RELEASE_MASK    | gtk.gdk.POINTER_MOTION_MASK |
						gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
						gtk.gdk.SCROLL_MASK)
		
		display_mode = (gtk.gdkgl.MODE_RGBA | gtk.gdkgl.MODE_DOUBLE)
		glconfig = gtk.gdkgl.Config(mode=display_mode)
		self.set_gl_capability(glconfig)
		
		self.set_events(gtk.gdk.BUTTON_MOTION_MASK  | gtk.gdk.KEY_PRESS_MASK |
						gtk.gdk.KEY_RELEASE_MASK    | gtk.gdk.POINTER_MOTION_MASK |
						gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
						gtk.gdk.SCROLL_MASK)
		
		self.connect( "expose_event", self.on_expose_event ) # expose = OnDraw
		self.connect( "realize", self.on_realize )  # one shot initialization
		self.connect( "configure_event", self.on_configure_event ) # given a size and width, resized
		self.connect( "button_press_event", self.on_button_press )
		
		self.tree = gui_xml.get_widget("treeview")
		self.treemodel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
		self.tree.connect("button_release_event", self.treeview_button_press)
		
		self.tree.set_reorderable(True)
		self.tree.set_model(self.treemodel)
		
		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Instructions", renderer, text=0)
		self.tree.append_column(column)
		
		self.model = self.cairo_context = None
		
	def treeview_button_press(self, obj, event):
		treemodel, iter = self.tree.get_selection().get_selected()
		self.model = treemodel.get_value(iter, 1)
		self.on_expose_event()

	def insert_row(self, model, parent, sibling, firstcol, secondcol):
		iter = model.insert_after(parent, sibling)
		model.set_value(iter, 0, firstcol)
		model.set_value(iter, 1, secondcol)
		return iter

	def insert_before(self, model, parent, sibling, firstcol, secondcol):
		iter = model.insert_before(parent, sibling)
		model.set_value(iter, 0, firstcol)
		model.set_value(iter, 1, secondcol)
		return iter
	
	def on_exit(self, widget, event):
		gtk.main_quit()

	def on_button_press(self, *args):
		x = args[1].x
		y = args[1].y
		
		if (x < (self.width/3)):
			glRotatef( -10.0, 0.0, 1.0, 0.0,)
		elif (x > (self.width*2/3)):
			glRotatef( 10.0, 0.0, 1.0, 0.0,)
		elif (y < (self.height/3)):
			glRotatef( -10.0, 1.0, 0.0, 0.0,)
		elif (y > (self.height*2/3)):
			glRotatef( 10.0, 1.0, 0.0, 0.0,)
			
		self.on_expose_event()

	def on_realize(self, *args):
		""" Initialize the window. """
		
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		
		if not gldrawable.gl_begin(glcontext):
			return
		
		specular = [1.0, 1.0, 1.0, 1.0]
		shininess = [50.0]
		lightPos = [1.0, 1.0, 1.0, 0.0]
		
		glShadeModel(GL_SMOOTH)
		
		glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, specular)
		glMaterialfv(GL_FRONT_AND_BACK, GL_SHININESS, shininess)
		glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
		
		glEnable(GL_LIGHTING)
		glEnable(GL_LIGHT0)
		
		glEnable(GL_DEPTH_TEST)
		#glCullFace(GL_BACK)
		#glFrontFace(GL_CCW)
		#glEnable(GL_CULL_FACE)
		glClearColor(1.0, 1.0, 1.0, 1.0)  # Draw clear white screen
		
		print "*** Loading Model ***"
		self.model = initEverything()
		self.model.initDraw(self.width, self.height)
		
		gldrawable.gl_end()
		
		self.initializeTree()
		self.cairo_context = self.window.cairo_create()

	def initializeTree(self):
		print "*** Loading TreeView ***"
		root = self.insert_row(self.treemodel, None, None, self.model.name, self.model)
		self.addStepsToTree(self.model.steps, root)

	def addStepsToTree(self, steps, root):
		loadedSubModels = []
		iterStep = iterPart = None
		for step in steps:
			
			# Add each step to specified spot in tree
			iterStep = self.insert_row(self.treemodel, root, iterStep, "Step " + str(step.number), step)
			
			for part in step.parts:
				if ((part.steps != []) and (part.name not in loadedSubModels)):
					# This part has steps of its own, so add this part to specified root.
					subRoot = self.insert_before(self.treemodel, root, iterStep, "SubModel " + part.name, part.partOGL)
					loadedSubModels.append(part.name)
					# Add this part's steps into this part in the tree.
					if (part.steps != []):
						self.addStepsToTree(part.steps, subRoot)
					
				# Add this part to tree, placed inside the current step.
				iterPart = self.insert_row(self.treemodel, iterStep, iterPart, part.name, part)
				
			iterPart = None
	
	def on_configure_event(self, *args):
		""" Resize the window. """
		
		self.width = restoreGLViewport.width = args[1].width
		self.height = restoreGLViewport.height = args[1].height
		
		if ((self.width < 5) or (self.height < 5)):
			return  # ignore resize if window is basically invisible
		
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		adjustGLViewport(0, 0, self.width, self.height)
		glLoadIdentity()	
		rotateToDefaultView()
		
		gldrawable.gl_end()
		
		# Create a new cairo context based on the new window size
		self.cairo_context = self.window.cairo_create()
	
	def on_expose_event(self, *args):
		""" Draw the window. """
		
		gldrawable = self.get_gl_drawable()
		glcontext  = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		glClearColor(1.0,1.0,1.0,1.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		glFrontFace(GL_CW)
		glColor3f(0,0,0)
		#self.displayGrid()
		
		glPushMatrix()
		
		# Draw any 3D stuff first (swap buffer call below would hose any 2D draw calls)
		if (self.model):
			self.model.drawModel(width = self.width, height = self.height)
		
		glPopMatrix()
		glFlush()
		
		gldrawable.swap_buffers()
		gldrawable.gl_end()
		
		# Draw any 2D page elements, like borders, labels, etc.
		if (self.model and isinstance(self.model, Step)):
			self.model.drawPageElements(context = self.cairo_context, width = self.width, height = self.height)
		
		return
		
	def displayGrid(self):
		glBegin( GL_LINES )
		glVertex3i( 0, 0, 0 )
		glVertex3i( 1000, 0, 0 )
		glVertex3i( 0, 0, 0 )
		glVertex3i( 0, 1000, 0 )
		glVertex3i( 0, 0, 0 )
		glVertex3i( 0, 0, 1000 )
		glEnd()

def on_exit(widget, event):
	gtk.main_quit()

# Not a primitive in the LDraw sense, just a single line/triangle/quad
class Primitive():
	def __init__(self, color, points, type, invert = True):
		self.color = color
		self.type = type
		self.points = points
		self.inverted = invert

	def addNormal(self, p1, p2, p3):
		Bx = p2[0] - p1[0]
		By = p2[1] - p1[1]
		Bz = p2[2] - p1[2]
		
		Cx = p3[0] - p1[0]
		Cy = p3[1] - p1[1]
		Cz = p3[2] - p1[2]
		
		Ax = (By * Cz) - (Bz * Cy)
		Ay = (Bz * Cx) - (Bx * Cz)
		Az = (Bx * Cy) - (By * Cx)
		l = math.sqrt((Ax*Ax)+(Ay*Ay)+(Az*Az))
		if (l != 0):
			Ax /= l
			Ay /= l
			Az /= l
		return [Ax, Ay, Az]
	
	def callOGLDisplayList(self):
		
		# must be called inside a glNewList/EndList pair
		color = convertToRGBA(self.color)
		
		if (color != CurrentColor):
			glPushAttrib(GL_CURRENT_BIT)
			if (len(color) == 3):
				glColor3fv(color)
			elif (len(color) == 4):
				glColor4fv(color)
			
		p = self.points
		
		if (self.inverted):
			normal = self.addNormal(p[6:9], p[3:6], p[0:3])
			#glBegin( GL_LINES )
			#glVertex3f(p[3], p[4], p[5])
			#glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
			#glEnd()
			
			glBegin( self.type )
			glNormal3fv(normal)
			if (self.type == GL_QUADS):
				glVertex3f( p[9], p[10], p[11] )
			glVertex3f( p[6], p[7], p[8] )
			glVertex3f( p[3], p[4], p[5] )
			glVertex3f( p[0], p[1], p[2] )
			glEnd()
		else:
			normal = self.addNormal(p[0:3], p[3:6], p[6:9])
			#glBegin( GL_LINES )
			#glVertex3f(p[3], p[4], p[5])
			#glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
			#glEnd()
			
			glBegin( self.type )
			glNormal3fv(normal)
			glVertex3f( p[0], p[1], p[2] )
			glVertex3f( p[3], p[4], p[5] )
			glVertex3f( p[6], p[7], p[8] )
			if (self.type == GL_QUADS):
				glVertex3f( p[9], p[10], p[11] )
			glEnd()
		
		if (color != CurrentColor):
			glPopAttrib()

class Instructions():
# TODO: Initializing everything.  Instructions can also be a tree, and be used
#       more cleanly than the hack job currently in the tree GUI code above.
	def __init__(self):
		self.pages = []

# Bill Of Materials
class BOM():
	pass

class Line():
# TODO: Define all members and their units in this class
	def __init__(self, red = 0, green = 0, blue = 0):
		self.color = [red, green, blue]  # [red, green, blue], 0.0 - 1.0
		self.thickness = 0
		self.dash = 0

class Fill():
# TODO: Define all members and their units in this class
	def __init__(self):
		self.color = [0.0, 0.0, 0.0]  # [red, green, blue], 0.0 - 1.0
		self.pattern = 0
		self.image = 0
	
# Represents a border drawn around a PLI / CSI / page
# Contains position and size info too
class Box():
	def __init__(self, x = UNINIT_PROP, y = UNINIT_PROP, width = UNINIT_PROP, height = UNINIT_PROP):
		self.line = Line(0, 0, 0)
		self.fill = Fill()
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.cornerRadius = 0 # Radius for rounded corners. 0 = square
		self.internalGap = 0  # Distance from inside edge of border to outside edge of contents

	def draw(self, context):
		# TODO: Remove this check once all is well
		if (self.x == UNINIT_PROP or self.y == UNINIT_PROP or self.width == UNINIT_PROP or self.height == UNINIT_PROP):
			print "ERROR: Trying to draw an uninitialized box!!"
			return
		
		context.set_source_rgb(*self.line.color)
		context.rectangle(self.x, self.y, self.width, self.height)
		context.stroke()

# A single page in an instruction book
class Page():
	def __init__(self, number):
		self.number = number
		self.box = Box()
		self.fill = Fill()
		self.steps = []
		
	def draw(self, context, width, height):
		pass

# Parts List Image.  Includes border and positional info.
class PLI():
	def __init__(self, x = 10, y = 10):
		self.x = x  # top left corner of PLI box
		self.y = y  # top right corner of PLI box
		
		self.layout = {}  # {part filename: [count, part, x, y]}
		self.box = Box(x, y)
		self.box.internalGap = 10  # TODO: Convert this to relative value (%)
	
	def addPartOGL(self, part):
		if (part.filename in self.layout):
			self.layout[part.filename][0] += 1
		else:
			self.layout[part.filename] = [1, part, 0, 0]
		
		#self.initLayout()

	def initLayout(self):
		b = self.box
		b.width = b.height = UNINIT_PROP
		x = b.x + b.internalGap
		for item in self.layout.values():
			part = item[1]
			
			if (part.width == UNINIT_PROP or part.height == UNINIT_PROP):
				# TODO: Get rid of this check once all is initialized properly
				print "ERROR: Trying to init the a PLI layout containing uninitialized parts!"
				continue
			
			item[2] = x
			item[3] = b.y + b.internalGap
			x += part.width + b.internalGap
			b.width = x - b.x
			b.height = max(b.height, part.height + (b.internalGap * 2))

	# Must be called inside a valid gldrawable context
	def drawParts(self, width, height):
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
		
		for (count, part, x, y) in self.layout.values():
			adjustGLViewport(x, height - y - part.height, part.width, part.height)
			glPushMatrix()
			glLoadIdentity()
			rotateToDefaultView(-part.center[0], part.center[1], 0.0)
			
			part.drawModel()
			glPopMatrix()
		
		restoreGLViewport()

	# Must be called AFTER any OGL calls - otherwise OGL will switch buffers and erase all this
	def drawPageElements(self, context, width, height):
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
		
		self.box.draw(context)

# Construction Step Image.  Includes border and positional info.
class CSI():
	def __init__(self, x = 0, y = 0):
		self.box = Box(x, y)
		self.fill = Fill()
		# TODO: Move Step's oglDispIDs generation & drawing here

	def drawModel(self, width, height):
		pass

	def drawPageElements(self, context, width, height):
		pass

class Step():
	def __init__(self, prevStep = None, buffers = []):
		self.parts = []
		self.prevStep = prevStep
		self.buffers = buffers  # [(bufID, stepNumber)], set of buffers active inside this Step
		self.oglDispIDs = []  # [(dispID, buffer)]
		if (prevStep):
			self.number = prevStep.number + 1
		else:
			self.number = 1
		
		self.pli = PLI()
		self.csi = CSI()

	def addPart(self, part):
		self.parts.append(part)
		self.pli.addPartOGL(part.partOGL)

	def createOGLDisplayList(self):
		if (self.oglDispIDs != []):
			return   # Have already initialized this Step's display list, so do nothing
		
		# Ensure all parts in this step have proper display lists
		for part in self.parts:
			if (part.partOGL.oglDispID == UNINIT_OGL_DISPID):
				part.partOGL.createOGLDisplayList()
		
		# Convert the list of buffers into a list of the concatenated buffer stack
		# TODO: Ugly - find a more pythonic way to do this
		bufferStackList = [[]]
		for buffer in self.buffers:
			tmp = list(bufferStackList[-1])
			tmp.append(buffer)
			bufferStackList.append(tmp)
		
		# Create one display list for each buffer set present in this Step
		for buffers in bufferStackList:
			id = glGenLists(1);
			self.oglDispIDs.append((id, buffers))
			glNewList(id, GL_COMPILE)
			
			for part in self.parts:
				part.callOGLDisplayList(buffers)
			
			glEndList()

	def drawModel(self, currentBuffers = None, width = UNINIT_PROP, height = UNINIT_PROP):
		
		# Draw any previous steps first
		if (self.prevStep):
			if (currentBuffers is None):
				self.prevStep.drawModel(self.buffers, width, height)
			else:
				self.prevStep.drawModel(currentBuffers, width, height)
		
		if (currentBuffers is None):
			self.pli.drawParts(width, height)
		
		# Draw this step
		if (currentBuffers is None):
			# This is the currently selected step - draw with its own buffer set (last stored)
			glCallList(self.oglDispIDs[-1][0])
			
		elif (len(currentBuffers) > 0):
			# Have current buffer - draw corresponding list (need to search for it)
			for id, buffer in self.oglDispIDs:
				if (buffer == currentBuffers):
					glCallList(id)
					return
			
		# Draw the default list, with no buffers present
		glCallList(self.oglDispIDs[0][0])
	
	def drawPageElements(self, currentBuffers = None, context = None, width = UNINIT_PROP, height = UNINIT_PROP):
		if (context):
			self.pli.drawPageElements(context, width, height)
			self.csi.drawPageElements(context, width, height)

	def callOGLDisplayList(self):
		glCallList(self.oglDispIDs[0][0])

# Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
# simple primitive (stud.dat), could be a full submodel with its own steps, buffers, etc.  
# Used inside 'concrete' Part below. One PartOGL instance will be shared across several 
# Part instances.  In other words, PartOGL represents everything that two 2x4 bricks have
# in common when present in a model.
class PartOGL():
	def __init__(self, filename, preLoadedFile = None):
		self.name = self.filename = filename
		self.inverted = False  # inverted = GL_CW
		self.invertNext = False
		self.parts = []
		self.primitives = []
		self.oglDispID = UNINIT_OGL_DISPID
		self.width = self.height = UNINIT_PROP
		self.isPrimitive = False  # primitive here == anything in 'P'
		
		self.currentStep = None
		self.steps = []
		self.buffers = []  #[(bufID, stepNumber)]
		self.pli_ign = False
		
		if (filename in ldrawFile.subModelsInFile):
			self._loadFromSubModelArray()
		else:
			self._loadFromFile(preLoadedFile)
		
		# Check if the last step in model is empty - occurs often, since we've implicitly
		# created a step before adding any parts, and many models end with a Step.
		if (len(self.steps) > 0 and self.steps[-1].parts == []):
			self.steps.pop()
		
		self.createOGLDisplayList()
	
	def _loadFromSubModelArray(self):
		
		self.currentStep = Step()
		self.steps.append(self.currentStep)
		
		start, end = ldrawFile.subModelsInFile[self.filename]
		subModelArray = ldrawFile.fileArray[start+1:end]
		
		for line in subModelArray:
			self._loadOneLDrawLineCommand(line)

	def _loadFromFile(self, preLoadedFile = None):
		
		if (preLoadedFile):
			ldfile = preLoadedFile
			self.currentStep = Step()
			self.steps.append(self.currentStep)
		else:
			ldfile = LDrawFile(self.filename)
			self.isPrimitive = ldfile.isPrimitive
			
		self.name = ldfile.name
		
		for line in ldfile.fileArray[1:]:
			if (isValidFileLine(line)):
				return
			self._loadOneLDrawLineCommand(line)

	def _loadOneLDrawLineCommand(self, line):
		
		if (isValidStepLine(line)):
			self.addStep(line[0])
		
		elif (isValidPartLine(line)):
			self.addPart(lineToPart(line))
		
		elif (isValidGhostLine(line)):
			self.addPart(lineToGhostPart(line))
		
		elif (isValidBufferLine(line)):
			self.addBuffer(lineToBuffer(line))
		
		elif (isValidPLIIGNLine(line)):
			self.setPLIIGNState(True, line)
		
		elif (isValidPLIEndLine(line)):
			self.setPLIIGNState(False, line)
		
		elif (isValidTriangleLine(line)):
			self.addPrimitive(lineToTriangle(line), GL_TRIANGLES)
		
		elif (isValidQuadLine(line)):
			self.addPrimitive(lineToQuad(line), GL_QUADS)

	def setPLIIGNState(self, state, line):
		if (self.pli_ign == state):
			if (state):
				print "PLI Ignore Warning: Begnining PLI IGN when already begun.  Line: ", line[0]
			else:
				print "PLI Ignore Warning: Ending PLI IGN when no valid PLI IGN had begun. Line: ", line[0]
		else:
			self.pli_ign = state
	
	def addStep(self, lineNumber = None):
		if (self.currentStep and self.currentStep.parts == []): # Current step is empty - remove it and warn
			if (lineNumber):
				print "Step Warning: Empty step found on line %d.  Ignoring Step #%d" % (lineNumber, self.currentStep.number)
			else:
				print "Step Warning: Empty step found.  Ignoring Step #%d" % (self.currentStep.number)
			self.steps.pop()
			self.currentStep = self.currentStep.prevStep
		
		self.currentStep = Step(self.currentStep, list(self.buffers))
		self.steps.append(self.currentStep)

	def addPrimitive(self, p, shape):
		primitive = Primitive(p['color'], p['points'], shape, self.inverted ^ self.invertNext)
		self.primitives.append(primitive)
	
	def addPart(self, p):
		try:
			part = Part(p['filename'], p['color'], p['matrix'], p['ghost'], list(self.buffers))
		except IOError:
			# TODO: This should be printed - commented out for debugging
#			print "Could not find file: %s - Ignoring." % p['filename']
			return
		
		if (self.currentStep):
			self.currentStep.addPart(part)
		else:
			self.parts.append(part)
	
	def addBuffer(self, b):
		buffer, state = b.values()
			
		if (state == BufferStore):
			self.buffers.append((buffer, self.currentStep.number))
			self.currentStep.buffers = list(self.buffers)
		
		elif (state == BufferRetrieve):
			if (self.buffers[-1][0] == buffer):
				self.buffers.pop()
				self.currentStep.buffers = list(self.buffers)
				if (self.currentStep.parts != []):
					print "Buffer Exchange error.  Restoring a buffer in Step ", self.currentStep.number, " after adding pieces to step.  Pieces will never be drawn."
			else:
				print "Buffer Exchange error.  Last stored buffer: ", self.buffers[-1][0], " but trying to retrieve buffer: ", buffer

	# Initialize this part's display list.  Expensive call, but called only once.
	def createOGLDisplayList(self):
		if (self.oglDispID != UNINIT_OGL_DISPID):
			return
		
		# Ensure any steps in this part have been initialized
		for step in self.steps:
			step.createOGLDisplayList()
		
		# Ensure any parts in this part have been initialized
		for part in self.parts:
			if (part.partOGL.oglDispID == UNINIT_OGL_DISPID):
				part.partOGL.createOGLDisplayList()
		
		self.oglDispID = glGenLists(1)
		glNewList(self.oglDispID, GL_COMPILE)
		
		for step in self.steps:
			step.callOGLDisplayList()
		
		for part in self.parts:
			part.callOGLDisplayList()
		
		for primitive in self.primitives:
			primitive.callOGLDisplayList()
		
		glEndList()

	def drawModel(self, context = None, width = UNINIT_PROP, height = UNINIT_PROP):
		if (self.width == UNINIT_PROP or self.height == UNINIT_PROP):
			print "ERROR: Trying to draw a part with uninitialized width / height!!: ", self.filename
			return
		
		glCallList(self.oglDispID)

	def initSize(self, width, height):
		
		# Primitive parts need not be sized
		if (self.isPrimitive):
			self.width = self.height = 0
			return
		
		if (self.width != UNINIT_PROP and self.height != UNINIT_PROP):
			print "ERROR: initializing size of an already initialized part!", self.filename
			return
		
		# TODO: update some kind of load status bar her - this function is *slow*
		print self.filename,
		
		# Clear the drawing buffer with white
		glClearColor(1.0,1.0,1.0,0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		# Draw the piece in black
		glColor3f(0,0,0)
		glCallList(self.oglDispID)
	
		# Read the rendered pixel data to local variable
		glReadBuffer(GL_BACK)
		glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
		pixels = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
		
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		im = Image.new("RGBA", (width, height))
		im.fromstring(pixels)
		#im.save("C:\\" + self.filename + "_f.png")
		data = im.load()
		
		top = checkPixels(data, 0, height, 1, 0, width, height, True)
		bottom = checkPixels(data, height-1, -1, -1, 0, width, 0, True)
		left = checkPixels(data, 0, width, 1, top, bottom+1, 0, False)
		right = checkPixels(data, width-1, -1, -1, top, bottom+1, width, False)
		
		self.width = right - left + 1
		self.height = bottom - top + 1
		
		x = left + (self.width/2)
		y = top + (self.height/2)
		w = x - (width/2)
		h = y - (height/2)
		self.center = (w, h)
		
		#im = im.crop((left, top, right+1, bottom+1))
		#im.save("C:\\" + self.filename + ".png")
		#self.width, self.height = im.size

white = (255, 255, 255, 0)
def checkPixels(data, start1, stop1, step1, start2, stop2, max, rightToLeft):
	for i in range(start1, stop1, step1):
		for j in range(start2, stop2):
			if (rightToLeft):
				if (data[j, i] != white):
					return i
			else:
				if (data[i, j] != white):
					return i
	return max

# Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
# info to draw that abstract part in context of a model, ie color, positional 
# info, containing buffer state, etc.  In other words, Part represents everything
# that could be different between two 2x4 bricks in a model.
class Part():
	def __init__(self, filename, color = None, matrix = None, ghost = False, buffers = [], invert = False, preLoadedFile = None):
		
		self.color = color
		self.matrix = matrix
		self.ghost = ghost
		self.buffers = buffers  # [(bufID, stepNumber)]
		self.inverted = invert
		
		if (filename in partDictionary):
			self.partOGL = partDictionary[filename]
		else:
			self.partOGL = partDictionary[filename] = PartOGL(filename, preLoadedFile)
			
		self.name = self.partOGL.name
		self.steps = self.partOGL.steps

	def shouldBeDrawn(self, currentBuffer):
		
		if (len(self.buffers) < 1):
			return True  # Piece not in any buffer - draw always
		
		# This piece is in a buffer
		if ((currentBuffer is None) or (len(currentBuffer) < 1)):
			return False  # Piece in a buffer, but no current buffer - don't draw
		
		if (self.buffers == currentBuffer): # Piece and current buffer match - draw
			return True
		
		return False # Piece and current buffer don't match - don't draw

	def callOGLDisplayList(self, currentBuffer = None):
		
		if (not self.shouldBeDrawn(currentBuffer)):
			return
		
		# must be called inside a glNewList/EndList pair
		if (self.color):
			color = convertToRGBA(self.color)
		else:
			color = CurrentColor
		
		if (color != CurrentColor):
			glPushAttrib(GL_CURRENT_BIT)
			if (len(color) == 3):
				glColor3fv(color)
			elif (len(color) == 4):
				glColor4fv(color)
		
		if (self.inverted):
			glPushAttrib(GL_POLYGON_BIT)
			glFrontFace(GL_CW)
		
		if (self.matrix):
			glPushMatrix()
			glMultMatrixf(self.matrix)
			
		glCallList(self.partOGL.oglDispID)
		
		if (self.matrix):
			glPopMatrix()
		
		if (self.inverted):
			glPopAttrib()
		
		if (color != CurrentColor):
			glPopAttrib()

	def drawModel(self, context = None, width = UNINIT_PROP, height = UNINIT_PROP):
		
		if (self.matrix):
			glPushMatrix()
			glMultMatrixf(self.matrix)
		
		glCallList(self.partOGL.oglDispID)
		
		if (self.matrix):
			glPopMatrix()
	
	def initDraw(self, width, height):
		for part in partDictionary.values():
			part.initSize(width, height)
		print ""
		
		for step in self.steps:
			step.pli.initLayout()
	
partDictionary = {}   # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
ldrawFile = LDrawFile(MODEL_NAME)

def initEverything():
	mainModel = Part(MODEL_NAME, preLoadedFile = ldrawFile)
#	ldrawFile.saveFile()
	return mainModel
	
def go():
	area = DrawArea()
	
	main = gui_xml.get_widget("main_window")
	main.connect( "delete_event", on_exit )
	
	box = gui_xml.get_widget("box_opengl")
	box.pack_start(area)  

	#main.maximize()
	main.set_title("First example")
	main.show_all()
	
	gtk.main()

go()

#import hotshot
#prof = hotshot.Profile("hotshot_stats_no_int")
#prof.runcall(gogo)
#prof.close()
