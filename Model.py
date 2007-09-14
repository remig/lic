import math
import Image
import cairo

import GLHelpers

from LDrawColors import *
from LDrawFileFormat import *
from Drawables import *

from OpenGL.GL import *
from OpenGL.GLU import *

# Global constants
UNINIT_OGL_DISPID = -1
UNINIT_PROP = -1

"""
TODO: Work on generating actual POV renderings from whatever is displayed:
First, abstract away all the opengl calls in the gui preview window so that they can be easily replaced
by calls to L3P / Pov-ray.
Then, use existing layout / cairo drawing engine to create finalized, nice looking instruction book pages.

Once all that's done, LIC is actually mildly useful.  Nothing revolutionary yet, but useful.


Should keep me busy for the next few weeks...
"""

# TODO: Implement rotation steps - good luck
# TODO: remove partDictionary global variable - used in few enough spots that it shouldn't be global anymore
# TODO: File load is sluggish, even if loading from a thoroughly Lic-created file
# TODO: SubModel CSIs and PLIs are not being initialized properly
partDictionary = {}   # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
ldrawFile = None
_windowWidth = -1
_windowHeight = -1

class Instructions():
	"""	Represents an overall Lego instruction booklet.	"""
	
	# TODO: Instructions should be a tree, and be used more cleanly than the hack job currently in the tree GUI code.
	def __init__(self, filename):
		global ldrawFile
		
		self.pages = []
		self.pagePadding = 20
		self.filename = filename
		
		# line format: filename width height center-x center-y leftInset bottomInset
		self.ImgDimensionsFilename = "PartDimensions_" + filename + ".cache"
		
		self.mainModel = Part(filename, isMainModel = True)
		ldrawFile = self.mainModel.partOGL.ldrawFile
	
	def resize(self, width, height):
		global _windowWidth, _windowHeight
		
		_windowWidth = width - (self.pagePadding * 2)
		_windowHeight = height - (self.pagePadding * 2)
		
		for step in self.mainModel.partOGL.steps:
			step.resize()
	
	def drawPage(self, context, width, height):
		
		# TODO: This whole method belongs in the Page class - move it there, and use Pages inside this instruction book
		# Flood context with grey background
		context.set_source_rgb(0.5, 0.5, 0.5)
		context.paint()
		
		scaleWidth = width - (self.pagePadding * 2)
		scaleHeight = height - (self.pagePadding * 2)
		width -= self.pagePadding * 2
		height -= self.pagePadding * 2
		
		# Draw a slightly down-left translated black rectangle, for the page shadow effect
		context.translate(self.pagePadding, self.pagePadding)
		context.set_source_rgb(0,0,0)
		context.rectangle(1, 1, width + 3, height + 3)
		context.fill()
		
		# Draw the page itself - white with a thin black border
		context.rectangle(0, 0, width, height)
		context.stroke_preserve()
		context.set_source_rgb(1,1,1)
		context.fill()
		
		return (scaleWidth, scaleHeight)
	
	def getMainModel(self):
		return self.mainModel
	
	def getCurrentModel(self):
		pass

	def generateImages(self):
		for part in partDictionary.values():
			if not part.isPrimitive:
				part.renderToPov()
		print "Instruction generation complete"
	
	def initDraw(self, context):
		
		# Calculate the width and height of each partOGL in the part dictionary and each CSI
		self.initPartDimensions()
		self.initCSIDimensions()
		
		# Calculate an initial layout for each Step and PLI in this instruction book
		for step in self.mainModel.partOGL.steps:
			step.initLayout(context)
			step.writeToGlobalFileArray()

	def initPartDimensions(self):
		
		try:
			# Have a valid part dimension cache file for this model - load from there
			f = file(self.ImgDimensionsFilename, "r")
			self.initPartDimensionsFromFile(f)
			f.close()
		except IOError:
			# Need to calculate all part dimensions from scratch
			self.initPartDimensionsManually()

	def initPartDimensionsFromFile(self, f):
		""" Used to initialize all part dimensions from the specified valid part dimension cache file f."""
		
		for line in f:
			filename, w, h, x, y, l, b, size = line.split()
			if (not partDictionary.has_key(filename)):
				print "Warning: part dimension cache contains part (%s) not present in model - suggest regenerating part dimension cache." % (filename)
				continue
			p = partDictionary[filename]
			p.width = max(1, int(w))
			p.height = max(1, int(h))
			p.center = Point(int(x), int(y))
			p.leftInset = int(l)
			p.bottomInset = int(b)
	
	def buildCSIList(self, part, loadedParts = []):
		csiList = []
		for step in part.steps:
			for part in step.parts:
				if (part.partOGL.filename not in loadedParts and part.partOGL.steps != []):
					csiList += self.buildCSIList(part.partOGL, loadedParts)
				loadedParts.append(part.partOGL.filename)
			if step.csi.fileLine is None:
				csiList.append(step.csi)
		return csiList

	def initCSIDimensions(self):
		csiList = self.buildCSIList(self.mainModel.partOGL)
		csiList2 = []
		sizes = [512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels
		
		for size in sizes:
			
			# Create a new FBO
			buffers = GLHelpers.createFBO(size, size)
			if buffers is None:
				print "ERROR: Failed to initialize FBO - aborting initCSIDimensions"
				return
			
			# Render each image and calculate their sizes
			for csi in csiList:
				if not csi.initSize(size):  # Draw image and calculate its size:
					csiList2.append(csi)
			
			# Clean up created FBO
			GLHelpers.destroyFBO(*buffers)
			
			if len(csiList2) < 1:
				break  # All images initialized successfully
			else:
				csiList = csiList2  # Some images rendered out of frame - loop and try bigger frame
				csiList2 = []
	
	def initPartDimensionsManually(self):
		"""
		Used to calculate each part's display width and height if no valid part dimension cache file exists.
		Creates GL FBOs to render a temp copy of each part, then uses those raw pixels to determine size.
		Will create and store results in a part dimension cache file.
		"""
		
		partList = [part for part in partDictionary.values() if not part.isPrimitive]
		partList2 = []
		lines = []
		sizes = [256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels
		
		for size in sizes:
			
			# Create a new FBO
			buffers = GLHelpers.createFBO(size, size)
			if buffers is None:
				print "ERROR: Failed to initialize FBO - aborting initPartDimensionsManually"
				return
			
			# Render each image and calculate their sizes
			for partOGL in partList:
				
				successfulDraw = partOGL.initSize(size)  # Draw image and calculate its size
				
				if successfulDraw:					
					lines.append(partOGL.dimensionsToString())
				else:
					partList2.append(partOGL)
			
			# Clean up created FBO
			GLHelpers.destroyFBO(*buffers)
			
			if len(partList2) < 1:
				break  # All images initialized successfully
			else:
				partList = partList2  # Some images rendered out of frame - loop and try bigger frame
				partList2 = []
		
		# Create an image dimension cache file
		print ""
		f = file(self.ImgDimensionsFilename, "w")
		f.writelines(lines)
		f.close()
	
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

class BOM():
	"""
	Bill Of Materials - just an elaborate PLI, containing a list of all parts in the model, nicely laid out.
	"""
	pass

class Callout():
	def __init__(self):
		self.box = Box(0, 0)

class PLI():
	"""
	Parts List Image.  Includes border and layout info for a list of parts added to a step.
	"""
	
	def __init__(self, step, topLeftCorner = Point(10, 10)):
		
		self.box = Box(topLeftCorner.x, topLeftCorner.y)
		self.qtyLabelFont = Font(size = 14, bold = True)
		self.qtyMultiplierChar = 'x'
		self.layout = {}  # {part filename: [count, part, bottomLeftCorner, qtyLabelReference, partFileLine]}
		
		self.step = step
		self.fileLine = None

	def isEmpty(self):
		if (len(self.layout) > 0):
			return False
		return True

	def addPart(self, part):
		
		p = part.partOGL		
		if (p.filename in self.layout):
			self.layout[p.filename][0] += 1
			self.layout[p.filename][-1] = part.fileLine
		else:
			self.layout[p.filename] = [1, p, Point(0, 0), Point(0, 0), part.fileLine]

	def initLayout(self, context):
		
		if self.fileLine:
			print "Trying to initalize a PLI that was alread initialized from file.  Ignoring call."
			return
		
		# If this PLI is empty, nothing to do here
		if (len(self.layout) < 1):
			return
		
		# Return the height of the part in the specified layout item
		def itemHeight(layoutItem):
			return layoutItem[1].height
		
		# Compare the width of layout Items 1 and 2
		def compareLayoutItemWidths(item1, item2):
			""" Returns 1 if part 2 is wider than part 1, 0 if equal, -1 if narrower. """
			if (item1[1].width < item2[1].width):
				return 1
			if (item1[1].width == item2[1].width):
				return 0
			return -1
		
		# Sort the list of parts in this PLI from widest to narrowest, with the tallest one first
		partList = self.layout.values()
		tallestPart = max(partList, key=itemHeight)
		partList.remove(tallestPart)
		partList.sort(compareLayoutItemWidths)
		partList.insert(0, tallestPart)
		
		# Note that PLI box's top left corner must be set by container before this layout call
		b = self.box
		overallX = b.x + b.internalGap
		b.width = b.height = UNINIT_PROP
		
		for i, (count, part, corner, labelCorner, line) in enumerate(partList):  # item: [count, part, bottomLeftCorner, fileline]
			
			if (part.width == UNINIT_PROP or part.height == UNINIT_PROP):
				# TODO: Remove this check once all is well
				print "ERROR: Trying to init the a PLI layout containing uninitialized parts!"
				continue
			
			# Calculate and store this part's bottom left corner
			corner.x = overallX
			corner.y = b.y + b.internalGap + part.height
			
			# Check if the current PLI box is big enough to fit this part *below* the previous part,
			# without making the box any bigger.  If so, position part there instead.
			newWidth = part.width
			if (i > 0):
				prevCorner = partList[i-1][2]
				prevLabelCorner = partList[i-1][3]
				remainingHeight = b.y + b.height - b.internalGap - b.internalGap - prevCorner.y
				if (part.height < remainingHeight):
					if (prevCorner.x > prevLabelCorner.x):
						overallX = int(prevLabelCorner.x)
						newWidth = (prevCorner.x - overallX) + partList[i-1][1].width
					else:
						overallX = prevCorner.x
						newWidth = partList[i-1][1].width
					corner.x = overallX + (newWidth - part.width)
					corner.y = prevCorner.y + b.internalGap + part.height
			
			# Position the part quantity label
			labelCorner.x, labelCorner.y, xBearing, xHeight = self.initQtyLabelPos(context, count, part, corner)
			
			if (labelCorner.x < overallX):
				# We're trying to draw the label to the left of the part's current position - shift everything
				dx = overallX - labelCorner.x
				overallX += dx
				labelCorner.x += dx
				corner.x += dx
			
			# Account for any x bearing in label (space between left corner of bounding box and actual reference point)
			labelCorner.x -= xBearing
			
			# Increase overall x, box width and box height to make PLI box big enough for this part
			overallX += newWidth + b.internalGap
			b.width = overallX - b.x
			b.height = max(b.height, part.height + int(xHeight / 2) + (b.internalGap * 2))

	def initQtyLabelPos(self, context, count, part, partCorner):
		
		# Tell cairo to use the quantity label's current font
		self.qtyLabelFont.passToCairo(context)
		
		# Figure out the display height of multiplier label and the width of full quantity label
		label = str(count) + self.qtyMultiplierChar
		xbearing, ybearing,     xWidth,     xHeight, xa, ya = context.text_extents(self.qtyMultiplierChar)
		xbearing, ybearing, labelWidth, labelHeight, xa, ya = context.text_extents(label)
		
		# Position label based on part corner, empty corner triangle and label's size
		if (part.leftInset == part.bottomInset == 0):
			dx = -3   # Bottom left triangle is empty - shift just a little, for a touch more padding
		else:
			slope = part.leftInset / float(part.bottomInset)
			dx = ((part.leftInset - (xHeight / 2)) / slope) - 3  # 3 for a touch more padding
		
		x = int(partCorner.x - labelWidth + max(0, dx))
		y = int(partCorner.y + (xHeight / 2))
		return (x, y, xbearing, xHeight)
	
	def drawParts(self):
		""" Must be called inside a valid gldrawable context. """
		
		if (len(self.layout) < 1):
			return  # No parts in this PLI - nothing to draw
		
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw parts for an unitialized PLI layout!"
			return
		
		GLHelpers.pushAllGLMatrices()
		
		for (count, part, corner, labelCorner, line) in self.layout.values():
			GLHelpers.adjustGLViewport(corner.x, corner.y - part.height, part.width, part.height)
			glLoadIdentity()
			GLHelpers.rotateToDefaultView(part.center.x, part.center.y, 0.0)
			part.drawModel()
		
		GLHelpers.popAllGLMatrices()

	def drawPageElements(self, context):
		""" Draw this PLI's background, border and quantity labels to the specified cairo context. """
		
		if (len(self.layout) < 1):
			return  # No parts in this PLI - nothing to draw
		
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout box!"
		
		# Draw the PLIs overall bounding box
		self.box.draw(context)
		
		# Draw the quantity label for each part, if needed
		for (count, part, corner, labelCorner, line) in self.layout.values():
			
			# Draw part's quantity label
			self.qtyLabelFont.passToCairo(context)
			context.move_to(labelCorner.x, labelCorner.y)
			context.show_text(str(count) + self.qtyMultiplierChar)

	def writeToGlobalFileArray(self):
		global ldrawFile
		
		if self.fileLine:
			# If this PLI already has a file line, it means it already exists in the file
			return
		
		# Write out the main PLI command to file, including box and label position info
		self.fileLine = [Comment, LICCommand, PLICommand, self.box.x, self.box.y, self.box.width, self.box.height, self.qtyMultiplierChar, self.qtyLabelFont.size, self.qtyLabelFont.face]
		ldrawFile.insertLine(self.step.fileLine[0], self.fileLine)
		
		# Write out each PLI item in the layout, positioned right after the last occurance of the part in this step
		for filename, item in self.layout.items():
			ldrawFile.insertLine(item[-1][0], [Comment, LICCommand, PLIItemCommand, filename, item[0], item[2].x, item[2].y, item[3].x, item[3].y])

class CSI():
	"""
	Construction Step Image.  Includes border and positional info.
	"""
	
	def __init__(self, filename, step, buffers):
		self.box = Box(0, 0)
		self.centerOffset = Point(0, 0)
		self.offsetPLI = 0
		self.filename = filename
		self.step = step
		self.buffers = buffers  # [(bufID, stepNumber)], set of buffers active inside this CSI
		
		self.oglDispIDs = []  # [(dispID, buffer)]
		self.oglDispID = UNINIT_OGL_DISPID
		
		self.fileLine = None
	
	def initSize(self, size):
		"""
		Initialize this CSI's display width, height and center point. To do
		this, draw this CSI to the already initialized GL Frame Buffer Object.
		These dimensions are required to properly lay out PLIs and CSIs.
		Note that an appropriate FBO *must* be initialized before calling initSize.
		
		Parameters:
			size: Width & height of FBO to render to, in pixels.  Note that FBO is assumed square
		
		Returns:
			True if CSI rendered successfully.
			False if the CSI has been rendered partially or wholly out of frame.
		"""
		
		if self.fileLine:
			print "Trying to initalize a CSI that was alread initialized from file.  Ignoring call."
			return
		
		# TODO: update some kind of load status bar her - this function is *slow*
		print "CSI %s step %d - size %d" % (self.filename, self.step.number, width)
		
		params = GLHelpers.initImgSize(size, size, self.oglDispID, wantInsets = False, filename = self.filename + " - step " + str(self.step.number))
		if params is None:
			return False
		
		self.box.width, self.box.height, self.centerOffset = params
		return True

	def resize(self):
		global _windowWidth, _windowHeight
		self.box.x = (_windowWidth / 2.) - (self.box.width / 2.)
		self.box.y = ((_windowHeight - self.offsetPLI) / 2.) - (self.box.height / 2.) + self.offsetPLI

	def callPreviousOGLDisplayLists(self, currentBuffers = None):
		if (self.step.prevStep):
			self.step.prevStep.csi.callPreviousOGLDisplayLists(currentBuffers)
		
		if (currentBuffers == []):
			# Draw the default list, since there's no buffers present
			glCallList(self.oglDispIDs[0][0])
		else:
			# Have current buffer - draw corresponding list (need to search for it)
			for id, buffer in self.oglDispIDs:
				if (buffer == currentBuffers):
					glCallList(id)
					return
		
		# If we get here, no better display list was found, so call the default display list
		glCallList(self.oglDispIDs[0][0])

	def createOGLDisplayList(self):
		
		self.oglDispIDs = []
		self.oglDispID = -1
		
		# Ensure all parts in this step have proper display lists
		for part in self.step.parts:
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
			id = glGenLists(1)
			self.oglDispIDs.append((id, buffers))
			glNewList(id, GL_COMPILE)
			
			for part in self.step.parts:
				part.callOGLDisplayList(buffers)
			
			glEndList()
		
		self.oglDispID = glGenLists(1)
		glNewList(self.oglDispID, GL_COMPILE)
		self.callPreviousOGLDisplayLists(self.buffers)
		glEndList()

	def drawModel(self):
		global _windowWidth, _windowHeight
		
		GLHelpers.adjustGLViewport(0, 0, _windowWidth, _windowHeight + self.offsetPLI)
		glLoadIdentity()
		GLHelpers.rotateToDefaultView(self.centerOffset.x, self.centerOffset.y, 0.0)
		glCallList(self.oglDispID)

	def drawPageElements(self, context):
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized CSI layout!"
			return
		self.box.draw(context)

	def callOGLDisplayList(self):
		glCallList(self.oglDispIDs[0][0])
	
	def writeToGlobalFileArray(self):
		global ldrawFile
		
		if not self.fileLine:
			self.fileLine = [Comment, LICCommand, CSICommand, self.box.x, self.box.y, self.box.width, self.box.height, self.centerOffset.x, self.centerOffset.y]
			ldrawFile.insertLine(self.step.fileLine[0], self.fileLine)

	def partTranslateCallback(self):
		global _windowWidth, _windowHeight
		self.createOGLDisplayList()
		self.initSize(min(_windowWidth, _windowHeight))
		self.resize()
	
class Step():
	def __init__(self, filename, prevStep = None, buffers = []):
		self.parts = []
		self.prevStep = prevStep
		
		self.internalGap = 20
		self.stepNumberFont = Font(20)
		self.stepNumberRefPt = Point(0, 0)
		
		self.fileLine = None
		
		if (prevStep):
			self.number = prevStep.number + 1
		else:
			self.number = 1
		
		self.csi = CSI(filename, self, list(buffers))
		self.pli = PLI(self, Point(self.internalGap, self.internalGap))

	def addPart(self, part):
		self.parts.append(part)
		part.translateCallback = self.csi.partTranslateCallback
		
		if (not part.ignorePLIState):
			self.pli.addPart(part)
	
	def resize(self):
		
		# Notify this step's CSI about the new size
		self.csi.resize()
		
		# Notify any steps in any sub models about the resize too
		for part in self.parts:
			for step in part.partOGL.steps:
				step.resize()

	def initLayout(self, context):
		global _windowHeight
		
		# If this step's PLI has not been initialized by the LDraw file (first run?), choose a nice initial layout
		if self.pli.fileLine is None:
			self.pli.initLayout(context)
		
		# Ensure all sub model PLIs and steps are also initialized
		for part in self.parts:
			for step in part.partOGL.steps:
				step.initLayout(context)
		
		# Determine space between top page edge and bottom of PLI, including gaps
		if (self.pli.isEmpty()):
			topGap = self.internalGap
		else:
			topGap = self.internalGap * 2 + self.pli.box.height
		
		# Figure out the display height of the step number label
		self.stepNumberFont.passToCairo(context)
		xbearing, ybearing = context.text_extents(str(self.number))[:2]
		
		# Initialize this step number's label position
		self.stepNumberRefPt.x = self.internalGap - xbearing
		self.stepNumberRefPt.y = topGap - ybearing
		
		# Tell this step's CSI about the PLI, so it can center itself vertically better
		self.csi.offsetPLI = topGap
		self.csi.resize()

	def writeToGlobalFileArray(self):
		self.pli.writeToGlobalFileArray()
		self.csi.writeToGlobalFileArray()
		
		for part in self.parts:
			for step in part.partOGL.steps:
				step.writeToGlobalFileArray()

	def drawModel(self):
		""" Draw this step's CSI and PLI parts (not GUI elements, just the 3D GL bits) """
		self.pli.drawParts()
		self.csi.drawModel()

	def drawPageElements(self, context):
		""" Draw this step's PLI and CSI page elements, and this step's number label. """
		self.csi.drawPageElements(context)
		self.pli.drawPageElements(context)
		
		# Draw this step's number label
		self.stepNumberFont.passToCairo(context)
		context.move_to(self.stepNumberRefPt.x, self.stepNumberRefPt.y)
		context.show_text(str(self.number))
	
class PartOGL():
	"""
	Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
	simple primitive, like stud.dat, could be a full submodel with its own steps, buffers, etc.  
	Used inside 'concrete' Part below. One PartOGL instance will be shared across several 
	Part instances.  In other words, PartOGL represents everything that two 2x4 bricks have
	in common when present in a model.
	"""
	
	def __init__(self, filename, parentLDFile = None, isMainModel = False):
		
		self.name = self.filename = filename
		self.ldrawFile = None
		self.ldArrayStartEnd = None  # list [start, end]
		
		self.inverted = False  # TODO: Fix this! inverted = GL_CW
		self.invertNext = False
		self.parts = []
		self.primitives = []
		self.oglDispID = UNINIT_OGL_DISPID
		self.isPrimitive = False  # primitive here means any file in 'P'
		
		self.currentStep = None
		self.steps = []
		
		self.buffers = []  #[(bufID, stepNumber)]
		self.ignorePLIState = False
		
		self.width = self.height = self.imageSize = 1
		self.leftInset = self.bottomInset = 0
		self.center = Point(0, 0)
		
		if ((parentLDFile is not None) and (filename in parentLDFile.subModelArray)):
			self._loadFromSubModelArray(parentLDFile)
		else:
			self._loadFromFile(isMainModel)
		
		# Check if the last step in model is empty - occurs often, since we've implicitly
		# created a step before adding any parts and many models end with a Step.
		if (len(self.steps) > 0 and self.steps[-1].parts == []):
			self.steps.pop()
		
		self.createOGLDisplayList()
	
	def _loadFromSubModelArray(self, ldrawFile):
		
		self.ldrawFile = ldrawFile
		
		self.ldArrayStartEnd = ldrawFile.subModelArray[self.filename]
		start, end = self.ldArrayStartEnd
		subModelArray = ldrawFile.fileArray[start + 1 : end]
		
		for line in subModelArray:
			self._loadOneLDrawLineCommand(line)

	def _loadFromFile(self, isMainModel):
		
		self.ldrawFile = LDrawFile(self.filename)
		if isMainModel:
			self.ldrawFile.addLICHeader()
			self.ldrawFile.addInitialSteps()
			self.ldArrayStartEnd = [0]
		
		self.isPrimitive = self.ldrawFile.isPrimitive
		self.name = self.ldrawFile.name
		
		# Loop over the specified LDraw file array, skipping the first line
		for line in self.ldrawFile.fileArray[1:]:
			
			# A FILE line means we're finished loading this model
			if isValidFileLine(line):
				if isMainModel:
					self.ldArrayStartEnd.append(line[0] - 1)
				return
			
			self._loadOneLDrawLineCommand(line)

	def _loadOneLDrawLineCommand(self, line):
		
		if isValidStepLine(line):
			self.addStep(line)
		
		elif isValidPartLine(line):
			self.addPart(lineToPart(line), line)
		
		elif isValidGhostLine(line):
			self.addPart(lineToGhostPart(line), line)
		
		elif isValidBufferLine(line):
			self.addBuffer(lineToBuffer(line))
		
		elif isValidTriangleLine(line):
			self.addPrimitive(lineToTriangle(line), GL_TRIANGLES)
		
		elif isValidQuadLine(line):
			self.addPrimitive(lineToQuad(line), GL_QUADS)
		
		elif isValidLPubLine(line):
			
			if isValidLPubPLILine(line):
				self.setPLIState(line)
		
		elif isValidLICLine(line):
			
			if isValidCSILine(line):
				self.addCSI(line)
			
			elif isValidPLILine(line):
				self.addPLI(line)
			
			elif isValidPLIItemLine(line):
				self.addPLIItem(line)

	def addPLI(self, line):
		
		if not self.currentStep:
			print "PLI Error: Trying to create a PLI outside of a step.  Line %d" % (line[0])
			return
		
		# [index, Comment, LICCommand, PLICommand, self.box.x, self.box.y, self.box.width, self.box.height, self.qtyMultiplierChar, self.qtyLabelFont.size, self.qtyLabelFont.face]
		# {'box': Box(*line[4:8]), 'qtyLabel': line[8], 'font': Font(line[9], line[10])}
		d = lineToPLI(line)
		pli = self.currentStep.pli
		pli.fileLine = line
		pli.box = d['box']
		pli.qtyMultiplierChar = d['qtyLabel']
		pli.qtyLabelFont = d['font']
	
	def addPLIItem(self, line):
		
		if not self.currentStep:
			print "PLI Item Error: Trying to add an item to a PLI outside of a step.  Line %d" % (line[0])
			return
		
		if len(self.currentStep.parts) < 1:
			print "PLI Item Error: Trying to add an item to a PLI inside a step with no parts.  Line %d" % (line[0])
			return
		
		d = lineToPLIItem(line)
		if not partDictionary.has_key(d['filename']):
			print "PLI item Error: Trying to add a non-existent part (%s) to a PLI.  Line %d" % (d['filename'], line[0])
			return
		
		# [index, Comment, LICCommand, PLIItemCommand, filename, item[0], item[2].x, item[2].y, item[3].x, item[3].y]
		# {part filename: [count, part, bottomLeftCorner, qtyLabelReference]}
		partLine = self.currentStep.parts[-1].fileLine
		self.currentStep.pli.layout[d['filename']] = [d['count'], partDictionary[d['filename']], d['corner'], d['labelCorner'], partLine]
	
	def addCSI(self, line):
		if not self.currentStep:
			print "CSI Warning: Trying to create a CSI outside of a step.  Line %d" % (line[0])
			return
		
		#{'box': Box(*line[4:8]), 'offset': Point(line[8], line[9])}
		d = lineToCSI(line)
		csi = self.currentStep.csi
		csi.fileLine = line
		csi.box = d['box']
		csi.centerOffset = d['offset']

	def addStep(self, line):
		if (self.currentStep and self.currentStep.parts == []): # Current step is empty - remove it and warn
			print "Step Warning: Empty step found on line %d.  Ignoring Step #%d" % (line[0], self.currentStep.number)
			self.steps.pop()
			self.currentStep = self.currentStep.prevStep
		
		# Create a new step, and make it the current step
		self.currentStep = Step(self.filename, self.currentStep, list(self.buffers))
		self.currentStep.fileLine = line
		self.steps.append(self.currentStep)

	def addPart(self, p, line):
		try:
			part = Part(p['filename'], p['color'], p['matrix'], p['ghost'], list(self.buffers), ldrawFile = self.ldrawFile)
		except IOError:
			# TODO: This should be printed - commented out for debugging
			#print "Could not find file: %s - Ignoring." % p['filename']
			return
		
		part.ignorePLIState = self.ignorePLIState
		part.fileLine = line
		
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
			self.currentStep.csi.buffers = list(self.buffers)
		
		elif (state == BufferRetrieve):
			if (self.buffers[-1][0] == buffer):
				self.buffers.pop()
				self.currentStep.csi.buffers = list(self.buffers)
				if (self.currentStep.parts != []):
					print "Buffer Exchange Error.  Restoring a buffer in Step ", self.currentStep.number, " after adding pieces to step.  Pieces will never be drawn."
			else:
				print "Buffer Exchange Error.  Last stored buffer: ", self.buffers[-1][0], " but trying to retrieve buffer: ", buffer

	def setPLIState(self, line):
		
		state = lineToLPubPLIState(line)
		if (self.ignorePLIState == state):
			if (state):
				print "PLI Ignore Error: Begnining PLI IGN when already begun.  Line: ", line[0]
			else:
				print "PLI Ignore Error: Ending PLI IGN when no valid PLI IGN had begun. Line: ", line[0]
		else:
			self.ignorePLIState = state
	
	def createOGLDisplayList(self):
		""" Initialize this part's display list.  Expensive call, but called only once. """
		if (self.oglDispID != UNINIT_OGL_DISPID):
			return
		
		# Ensure any steps in this part have been initialized
		for step in self.steps:
			step.csi.createOGLDisplayList()
		
		# Ensure any parts in this part have been initialized
		for part in self.parts:
			if (part.partOGL.oglDispID == UNINIT_OGL_DISPID):
				part.partOGL.createOGLDisplayList()
		
		self.oglDispID = glGenLists(1)
		glNewList(self.oglDispID, GL_COMPILE)
		
		for step in self.steps:
			step.csi.callOGLDisplayList()
		
		for part in self.parts:
			part.callOGLDisplayList()
		
		for primitive in self.primitives:
			primitive.callOGLDisplayList()
		
		glEndList()

	def drawModel(self, context = None, width = UNINIT_PROP, height = UNINIT_PROP):
		if (self.width == UNINIT_PROP or self.height == UNINIT_PROP):
			# TODO: Remove this check once all is well
			print "ERROR: Trying to draw a part with uninitialized width / height!!: ", self.filename
			return
		
		glCallList(self.oglDispID)
	
	def initSize_checkRotation(self):
		# TODO: Create a static list of all standard parts along with the necessary rotation needed
		# to get them from their default file rotation to the rotation seen in Lego's PLIs.
		pass

	def dimensionsToString(self):
		if (self.isPrimitive):
			return ""
		return "%s %d %d %d %d %d %d %d\n" % (self.filename, self.width, self.height, self.center.x, self.center.y, self.leftInset, self.bottomInset, self.imageSize)

	def initSize(self, size):
		"""
		Initialize this part's display width, height, empty corner insets and center point.
		To do this, draw this part to the already initialized GL Frame Buffer Object.
		These dimensions are required to properly lay out PLIs and CSIs.
		Note that an appropriate FBO *must* be initialized before calling initSize.
		
		Parameters:
			size: Width & height of FBO to render to, in pixels.  Note that FBO is assumed square
		
		Returns:
			True if part rendered successfully.
			False if the part has been rendered partially or wholly out of frame.
		"""
		
		# Primitive parts need not be sized
		if (self.isPrimitive):
			return True
		
		# TODO: update some kind of load status bar her - this function is *slow*
		#print self.filename,
		
		params = GLHelpers.initImgSize(size, size, self.oglDispID, wantInsets = True, filename = self.filename)
		if (params is None):
			return False
		
		self.imageSize = size
		self.width, self.height, self.leftInset, self.bottomInset, self.center = params
		return True
	
	def renderToPov(self):
		
		filename = None
		if self.ldArrayStartEnd:
			# This is a submodel in main file - need to write this to its own .dat
			filename = self.ldrawFile.writeLinesToDat(self.filename, *self.ldArrayStartEnd)
		
		# Render this part to a pov file then a final image
		self.ldrawFile.createPov(self.width + 3, self.height + 3, filename)
		
		# If this part has steps, need to generate dats, povs & images for each step
		if self.steps != []:
			if self.ldArrayStartEnd:
				stepDats = self.ldrawFile.splitStepDats(self.filename, *self.ldArrayStartEnd)
			else:
				stepDats = self.ldrawFile.splitStepDats()
			
			if len(stepDats) != len(self.steps):
				print "Error: Generated %d step dats, but have %d steps" % (len(stepDats), len(self.steps))
				return
			
			# Render any steps we generated above
			for i, dat in enumerate(stepDats):
				width = self.steps[i].csi.box.width
				height = self.steps[i].csi.box.height
				self.ldrawFile.createPov(width + 3, height + 3, dat)
	
class Part():
	"""
	Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
	info to draw that abstract part in context of a model, ie color, positional 
	info, containing buffer state, etc.  In other words, Part represents everything
	that could be different between two 2x4 bricks in a model.
	"""
	
	def __init__(self, filename, color = None, matrix = None, ghost = False, buffers = [], invert = False, ldrawFile = None, isMainModel = False):
		
		self.color = color
		self.matrix = matrix
		self.ghost = ghost
		self.buffers = buffers  # [(bufID, stepNumber)]
		self.inverted = invert
		self.ignorePLIState = False
		self.fileLine = None 
		
		self.translateCallback = None
		
		if (filename in partDictionary):
			self.partOGL = partDictionary[filename]
		else:
			self.partOGL = partDictionary[filename] = PartOGL(filename, ldrawFile, isMainModel)
		
		self.name = self.partOGL.name

	def translate(self, x, y, z):
		self.matrix[12] = x
		self.matrix[13] = y
		self.matrix[14] = z
		
		if self.ghost:
			self.fileLine[5] = str(x)
			self.fileLine[6] = str(y)
			self.fileLine[7] = str(z)
		else:
			self.fileLine[3] = str(x)
			self.fileLine[4] = str(y)
			self.fileLine[5] = str(z)
		
		if self.translateCallback:
			self.translateCallback()

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

	def drawModel(self):
		
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
