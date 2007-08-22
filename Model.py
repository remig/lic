import math
import Image
import cairo

from LDrawColors import *
from LDrawFileFormat import *
from GLHelpers import *

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL.EXT.framebuffer_object import *

# Global constants
UNINIT_OGL_DISPID = -1
UNINIT_PROP = -1

# TODO: Implement rotation steps - good luck
# TODO: remove partDictionary global variable - used in few enough spots that it shouldn't be global anymore
partDictionary = {}   # x = PartOGL("3005.dat"); partDictionary[x.filename] == x

class Instructions():
	"""	Represents an overall Lego instruction booklet.	"""
	
	# TODO: Instructions should be a tree, and be used more cleanly than the hack job currently in the tree GUI code.
	def __init__(self, filename):
		
		self.pages = []
		self.filename = filename
		
		# line format: filename width height center-x center-y leftInset bottomInset
		self.PartDimensionsFilename = "PartDimensions_" + filename + ".cache"
		
		self.mainModel = Part(filename, hasSteps = True)
		#ldFile.saveFile()
	
	def getMainModel(self):
		return self.mainModel
	
	def getCurrentModel(self):
		pass

	def initDraw(self):
		
		# Calculate the width and height of each partOGL in the part dictionary
		self.initPartDimensions()
		
		# Calculate an initial layout for each PLI in this instruction book
		for step in self.mainModel.partOGL.steps:
			step.pli.initLayout()
		
		#part = partDictionary['Blaster_big_stock_arms_instructions.ldr']
		#part = partDictionary['Blaster_big_stand_instructions.ldr']
		#part = partDictionary['Blaster_big_emitter_core_instructions.ldr']
		#part.initSize()
		#print ""
	
	def initPartDimensions(self):
		try:
			# Have a valid part dimension cache file for this model - load from there
			f = file(self.PartDimensionsFilename + "die", "r")
			self.initPartDimensionsFromFile(f)
			f.close()
		except IOError:
			# Need to calculate all part dimensions from scratch
			self.initPartDimensionsManually()

	def initPartDimensionsFromFile(self, f):
		for line in f:
			part, w, h, x, y, l, b = line.split()
			if (not partDictionary.has_key(part)):
				print "Warning: part dimension cache contains parts not present in model - suggest regenerating part dimension cache."
				continue
			p = partDictionary[part]
			p.width = max(1, int(w))
			p.height = max(1, int(h))
			p.center = (int(x), int(y))
			p.leftInset = int(l)
			p.bottomInset = int(b)
	
	def initPartDimensionsManually(self):
		# No part dimension cache file exists, so calculate each part size and store in cache file.  Create a 
		# temporary Frame Buffer Object for this, so we can render to a buffer independent of the display buffer. 
		
		# Setup framebuffer
		framebuffer = glGenFramebuffersEXT(1)
		glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, framebuffer)
		
		# TODO: Calculate this so that like 90% of all standard pieces render with a minimal size.  Or make it a list
		sizes = [256, 512, 1024] # TODO: Use this instead of w & h
		w = h = 512
		
		# Need a temporary image hanging around for the glTexImage2D call below to work
		image = Image.new ("RGB", (w, h), (1, 1, 1))
		bits = image.tostring("raw", "RGBX", 0, -1)
		
		# Setup depthbuffer
		depthbuffer = glGenRenderbuffersEXT(1)
		glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, depthbuffer)
		glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, GL_DEPTH_COMPONENT, w, h)
		
		# Create texture to render to
		texture = glGenTextures (1)
		glBindTexture(GL_TEXTURE_2D, texture)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, bits)
		glFramebufferTexture2DEXT (GL_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT, GL_TEXTURE_2D, texture, 0);
		glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, GL_DEPTH_ATTACHMENT_EXT, GL_RENDERBUFFER_EXT, depthbuffer);
		
		status = glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT);
		if status != GL_FRAMEBUFFER_COMPLETE_EXT:
			print "Error in framebuffer activation"
			return
		
		# Render each part and calculate their sizes
		lines = []
		for p in partDictionary.values():
			p.initSize(w, h)
			if (not p.isPrimitive):
				lines.append("%s %d %d %d %d %d %d\n" % (p.filename, p.width, p.height, p.center[0], p.center[1], p.leftInset, p.bottomInset))
		print ""
		
		# Create a part dimension cache file
		f = file(self.PartDimensionsFilename, 'w')
		f.writelines(lines)
		f.close()
		
		# Clean up - disable any created buffers
		glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, 0)
		glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)
		glDeleteTextures(texture)
		glDeleteFramebuffersEXT(1, [framebuffer])
	
class Line():
	"""
	Drawing properties for any given line an instruction book.
	"""

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
	
class Box():
	"""
	Represents a border and fill drawn around a PLI / CSI / page,
	and the position and size info needed to draw the border.
	"""
	
	def __init__(self, x = UNINIT_PROP, y = UNINIT_PROP, width = UNINIT_PROP, height = UNINIT_PROP):
		self.line = Line(0, 0, 0)
		self.fill = Fill()
		
		# TODO: Convert all of these to relative values (from 0..1, % of overall width | height)
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		
		self.cornerRadius = 0 # Radius for rounded corners. 0 = square
		self.internalGap = 10  # Distance from inside edge of border to outside edge of contents

	def draw(self, context):
		# TODO: Remove this check once all is well
		if (self.x == UNINIT_PROP or self.y == UNINIT_PROP or self.width == UNINIT_PROP or self.height == UNINIT_PROP):
			print "ERROR: Trying to draw an uninitialized box!!"
			return
		
		context.set_source_rgb(*self.line.color)
		context.rectangle(self.x, self.y, self.width, self.height)
		context.stroke()

class Page():
	"""
	A single page in an instruction book.
	"""
	
	def __init__(self, number):
		self.number = number
		self.box = Box()
		self.fill = Fill()
		self.steps = []

	def draw(self, context, width, height):
		pass

class PLI():
	"""
	Parts List Image.  Includes border and layout info for a list of parts added to a step.
	"""
	
	def __init__(self, x = 10, y = 10):
		self.x = x  # top left corner of PLI box
		self.y = y  # top right corner of PLI box
		
		self.layout = {}  # {part filename: [count, part, x, y]}
		self.box = Box(x, y)
	
	def addPartOGL(self, part):

		if (part.filename in self.layout):
			self.layout[part.filename][0] += 1
		else:
			self.layout[part.filename] = [1, part, 0, 0]

	def initLayout(self):

		b = self.box
		b.width = b.height = UNINIT_PROP
		x = b.x + b.internalGap
		
		for item in self.layout.values():
			part = item[1]
			
			for step in part.steps:
				step.pli.initLayout()
			
			if (part.width == UNINIT_PROP or part.height == UNINIT_PROP):
				# TODO: Remove this check once all is well
				print "ERROR: Trying to init the a PLI layout containing uninitialized parts!"
				continue
			
			item[2] = x
			item[3] = b.y + b.internalGap
			x += part.width + b.internalGap
			b.width = x - b.x
			b.height = max(b.height, part.height + (b.internalGap * 2))

	def drawParts(self, width, height):
		""" Must be called inside a valid gldrawable context. """
		
		if (len(self.layout) < 1):
			return  # No parts in this PLI - nothing to draw
		
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
			return
		
		pushAllGLMatrices()
		for (count, part, x, y) in self.layout.values():
			adjustGLViewport(x, height - y - part.height, part.width, part.height)
			glLoadIdentity()
			rotateToDefaultView(part.center[0], part.center[1], 0.0)
			
			part.drawModel()
		popAllGLMatrices()

	def drawPageElements(self, context):
		""" Must be called AFTER any OGL calls - otherwise OGL will switch buffers and erase all this. """
		
		if (len(self.layout) < 1):
			return  # No parts in this PLI - nothing to draw
		
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
		
		context.set_source_rgb(1.0, 0.0, 0.0)
		context.select_font_face('Arial', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
		context.set_font_size(100)
		context.move_to(50, 50)
		text = 'abcdefg'
		context.show_text(text)
		context.show_text("Howdihow")
		
		x = y = 30
		context.move_to(x, y)
		context.line_to(x + 50, y + 50)
		context.line_to(x, y + 50)
		context.close_path()
		context.stroke()
		
		#self.box.draw(context)
		for (count, p, x, y) in self.layout.values():
			
			context.set_source_rgb(1.0, 0.0, 0.0)
			context.move_to(x, y + p.leftInset)
			context.line_to(x + p.bottomInset, y + p.height)
			context.line_to(x, y + p.height)
			context.close_path()
			context.stroke()
			
			# TODO: Draw each PLI quantity label here.  cairo_text_extents calculates label size
			# draw\cairo\labels.c: 235 for sizing, 395 for drawing, 37 for setting font
			context.select_font_face('Arial', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
			context.set_font_size(10)
			context.move_to(20, 20)
			text = 'x'
			context.show_text(text)
		
		# TODO: Draw part quantity labels.  
		# Label's y: center of label's 'x' == bottom of part box
		# Label's x: depends on part - as far into the part box as possible without overlapping part
		# To calculate x, find the intersection point between calculated triangle's hypotenuse and
		# horizontal line placed above label's 'x' (or more, for padding)

class CSI():
	"""
	Construction Step Image.  Includes border and positional info.
	"""
	
	def __init__(self, x = 0, y = 0):
		self.box = Box(x, y)
		
		# TODO: Move Step's oglDispIDs generation & drawing here
		# TODO: Need to calculate bounds on each STEP / CSI image too - ouch

	def drawModel(self, width, height):
		pass

	def drawPageElements(self, context):
		#if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			#print "ERROR: Trying to draw an unitialized PLI layout!"
		
		#self.box.draw(context)
		pass

class BOM():
	"""
	Bill Of Materials - just an elaborate PLI, containing a list of all parts in the model, nicely laid out.
	"""
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
		if (not part.ignorePLIState):
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
	
	def drawPageElements(self, context):
		if (context):
			self.pli.drawPageElements(context)
			self.csi.drawPageElements(context)

	def callOGLDisplayList(self):
		glCallList(self.oglDispIDs[0][0])

class PartOGL():
	"""
	Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
	simple primitive, like stud.dat, could be a full submodel with its own steps, buffers, etc.  
	Used inside 'concrete' Part below. One PartOGL instance will be shared across several 
	Part instances.  In other words, PartOGL represents everything that two 2x4 bricks have
	in common when present in a model.
	"""
	
	def __init__(self, filename, parentLDFile = None, hasSteps = False):
		
		self.name = self.filename = filename
		self.ldrawFile = None
		self.inverted = False  # inverted = GL_CW - TODO
		self.invertNext = False
		self.parts = []
		self.primitives = []
		self.oglDispID = UNINIT_OGL_DISPID
		self.isPrimitive = False  # primitive here means any file in 'P'
		
		if (hasSteps):
			self.currentStep = Step()
			self.steps = [self.currentStep]
		else:
			self.currentStep = None
			self.steps = []
		
		self.buffers = []  #[(bufID, stepNumber)]
		self.ignorePLIState = False
		
		self.width = self.height = 1
		self.leftInset = self.bottomInset = 0
		self.center = (0, 0)
		
		if ((parentLDFile is not None) and (filename in parentLDFile.subModelsInFile)):
			self._loadFromSubModelArray(parentLDFile)
		else:
			self._loadFromFile()
		
		# Check if the last step in model is empty - occurs often, since we've implicitly
		# created a step before adding any parts and many models end with a Step.
		if (len(self.steps) > 0 and self.steps[-1].parts == []):
			self.steps.pop()
		
		self.createOGLDisplayList()
	
	def _loadFromSubModelArray(self, ldrawFile):
		
		self.currentStep = Step()
		self.steps = [self.currentStep]
		self.ldrawFile = ldrawFile
		
		start, end = ldrawFile.subModelsInFile[self.filename]
		subModelArray = ldrawFile.fileArray[start + 1 : end]
		
		for line in subModelArray:
			self._loadOneLDrawLineCommand(line)

	def _loadFromFile(self):
		
		self.ldrawFile = LDrawFile(self.filename)
		self.isPrimitive = self.ldrawFile.isPrimitive
		self.name = self.ldrawFile.name
		
		for line in self.ldrawFile.fileArray[1:]:
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

	def addPart(self, p):
		try:
			part = Part(p['filename'], p['color'], p['matrix'], p['ghost'], list(self.buffers), ldrawFile = self.ldrawFile)
		except IOError:
			# TODO: This should be printed - commented out for debugging
			#print "Could not find file: %s - Ignoring." % p['filename']
			return
		
		part.ignorePLIState = self.ignorePLIState
		
		if (self.currentStep):
			self.currentStep.addPart(part)
		else:
			self.parts.append(part)
	
	def addPrimitive(self, p, shape):
		primitive = Primitive(p['color'], p['points'], shape, self.inverted ^ self.invertNext)
		self.primitives.append(primitive)
	
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

	def setPLIIGNState(self, state, line):
		if (self.ignorePLIState == state):
			if (state):
				print "PLI Ignore Warning: Begnining PLI IGN when already begun.  Line: ", line[0]
			else:
				print "PLI Ignore Warning: Ending PLI IGN when no valid PLI IGN had begun. Line: ", line[0]
		else:
			self.ignorePLIState = state
	
	def createOGLDisplayList(self):
		""" Initialize this part's display list.  Expensive call, but called only once. """
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

	def initSize_checkRotation(self):
		# TODO: Once a part's dimensions have been calculated, use the existing bounds and render
		# to check if it's rotated correctly.  Want all long skinny pieces to go the same way -
		# from bottom left corner to top right.  To verify this, from left and right edges, 10%
		# below top, count blank pixels.  Whichever is shorter determines rotation - flip
		# render / drawing if needed.
		pass

	def checkMaxBounds(self, top, bottom, left, right, width, height):
		
		if ((top == 0) and (bottom == height-1)): 
			print self.filename + " - top & bottom out of bounds - hosed"
			return True
		
		if ((left == 0) and (right == width-1)):
			print self.filename + " - left & right out of bounds - hosed"
			return True
		
		if ((top == height) and (bottom == 0)):
			print self.filename + " - blank page - hosed"
			return True
		
		if ((left == width) and (right == 0)):
			print self.filename + " - blank page - hosed"
			return True
		
		return False

	def initSize_getBounds(self, x, y, w, h, first = '_first'):
		
		# TODO: Move frame buffer creation up call stack to initPartDimensionsManually, so that it's only created once
		# Clear the drawing buffer with white
		glClearColor(1.0, 1.0, 1.0, 0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		# Draw the piece in black
		glLoadIdentity()
		adjustGLViewport(0, 0, w, h)
		rotateToDefaultView(x, y, 0.0)
		glColor3f(0, 0, 0)
		glCallList(self.oglDispID)
		
		pixels = glReadPixels (0, 0, w, h, GL_RGB,  GL_UNSIGNED_BYTE)
		img = Image.new ("RGB", (w, h), (1, 1, 1))
		img.fromstring(pixels)
		img = img.transpose(Image.FLIP_TOP_BOTTOM)
		img.save ("C:\\LDraw\\tmp\\buf_" + self.filename + first + ".png")
		
		data = img.load()
		top = checkPixelsTop(data, w, h)
		bottom, bottomLeft = checkPixelsBottom(data, w, h, top)
		left, leftBottom = checkPixelsLeft(data, w, h, top, bottom)
		right = checkPixelsRight(data, w, h, top, bottom, left)
		
		return (top, bottom, left, right, leftBottom - top, bottomLeft - left)

	def initSize(self, width, height):
		
		# Primitive parts need not be sized
		if (self.isPrimitive):
			return
		
		# TODO: update some kind of load status bar her - this function is *slow*
		print self.filename,
		
		# Draw piece to frame buffer, then calculate bounding box
		top, bottom, left, right, leftInset, bottomInset = self.initSize_getBounds(0.0, 0.0, width, height)
		
		if self.checkMaxBounds(top, bottom, left, right, width, height):
			# TODO: Now that we're using an arbitrarily resizable FBO for temp rendering, queue this piece up for a re-render at larger size
			return
		
		# If we hit one of these cases, at least one edge was drawn off screen
		# Try to reposition the drawing and draw again, see if we can fit it on screen
		# TODO: Blaster_big_stock_arms_instructions.ldr - one displacement not enough - fix by queueing up for re-render at larger size
		# TODO: Same with Blaster_big_stand_instructions.ldr
		x = y = 0
		if (top == 0):
			y = bottom - height + 2
		
		if (bottom == height-1):
			y = top - 1
		
		if (left == 0):
			x = right - width + 2
		
		if (right == width-1):
			x = left - 1
		
		if ((x != 0) or (y != 0)):
			#print self.filename
			#print "old t: %d, b: %d, l: %d, r: %d" % (top, bottom, left, right)
			#print "displacing by x: %d, y: %d" % (x, y)
			top, bottom, left, right, leftInset, bottomInset = self.initSize_getBounds(x, y, width, height, '_second')
			#print "new t: %d, b: %d, l: %d, r: %d" % (top, bottom, left, right)
		
		if self.checkMaxBounds(top, bottom, left, right, width, height):
			# TODO: Now that we're using an arbitrarily resizable FBO for temp rendering, queue this piece up for a re-render at larger size
			return
		
		self.width = right - left + 1
		self.height = bottom - top + 1
		self.leftInset = leftInset 
		self.bottomInset = bottomInset
		
		dx = left + (self.width/2)
		dy = top + (self.height/2)
		w = dx - (width/2)
		h = dy - (height/2)
		self.center = (w - x, h - y)
		
		#im = im.crop((left, top, right+1, bottom+1))
		#im.save("C:\\" + self.filename + ".png")
		#self.width, self.height = im.size

# TODO: verify these 4 functions for all cases, with blaster
white = (255, 255, 255)
def checkPixelsTop(data, width, height):
	for i in range(0, height):
		for j in range(0, width):
			if (data[j, i] != white):
				return i
	return height

def checkPixelsBottom(data, width, height, top):
	for i in range(height-1, top, -1):
		for j in range(0, width):
			if (data[j, i] != white):
				return (i, j)
	return (0, 0)

def checkPixelsLeft(data, width, height, top, bottom):
	for i in range(0, width):
		for j in range(bottom, top, -1):
			if (data[i, j] != white):
				return (i, j)
	return (0, 0)

def checkPixelsRight(data, width, height, top, bottom, left):
	for i in range(width-1, left, -1):
		for j in range(top, bottom):
			if (data[i, j] != white):
				return i
	return width

class Part():
	"""
	Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
	info to draw that abstract part in context of a model, ie color, positional 
	info, containing buffer state, etc.  In other words, Part represents everything
	that could be different between two 2x4 bricks in a model.
	"""
	
	def __init__(self, filename, color = None, matrix = None, ghost = False, buffers = [], invert = False, ldrawFile = None, hasSteps = False):
		
		self.color = color
		self.matrix = matrix
		self.ghost = ghost
		self.buffers = buffers  # [(bufID, stepNumber)]
		self.inverted = invert
		self.ignorePLIState = False
		
		if (filename in partDictionary):
			self.partOGL = partDictionary[filename]
		else:
			self.partOGL = partDictionary[filename] = PartOGL(filename, ldrawFile, hasSteps)
		
		self.name = self.partOGL.name

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
	
class Primitive():
	"""
	Not a primitive in the LDraw sense, just a single line/triangle/quad.
	Used mainly to construct an OGL display list for a set of points.
	"""
	
	def __init__(self, color, points, type, invert = True):
		self.color = color
		self.type = type
		self.points = points
		self.inverted = invert

	# TODO: using numpy for all this would probably work a lot better
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
