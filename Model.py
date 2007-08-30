import math
import Image
import cairo

from LDrawColors import *
from LDrawFileFormat import *
from GLHelpers import *
from Drawables import *

from OpenGL.GL import *
from OpenGL.GLU import *

# Global constants
UNINIT_OGL_DISPID = -1
UNINIT_PROP = -1

"""
TODO: Once PLI and CSI are laid out properly (just need to touch up PLI), work on generating actual POV 
renderings from whatever is displayed:
First, figure out menus in pyGTK, and get a 'generate' menu to do something, anything
Then, check out the os module's exec & spawn functions to call L3P (http://docs.python.org/lib/os-process.html)
Then, figure out the correct arguments to L3P so that a single brick is rendered identical in PLI and L3P

Also need to get LDraw file *SAVE* working:
First, add changes & calculation made on load back into the file array (initial STEP, PLI positions, subModel dimensions, etc).
Then, write that new file array to disk, then load it and see if we can save a ton of work on init.

Once all that's done, LIC is actually mildly useful.  Nothing revolutionary yet, but useful.


Should keep me busy for the next few weeks...
"""

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
		self.ImgDimensionsFilename = "PartDimensions_" + filename + ".cache"
		
		self.mainModel = Part(filename, hasSteps = True)
		self.mainModel.partOGL.ldrawFile.saveFile() 
		self.mainModel.partOGL.writeToFile() 
	
	def drawPage(self, context, width, height):
		
		# TODO: This whole method belongs in the Page class - move it there, and use Pages inside this instruction book
		pagePadding = 20
		
		# Flood context with grey background
		context.set_source_rgb(0.5, 0.5, 0.5)
		context.paint()
		
		scaleWidth = width - (pagePadding * 2)
		scaleHeight = height - (pagePadding * 2)
		width -= pagePadding * 2
		height -= pagePadding * 2
		
		# Draw a slightly down-left translated black rectangle, for the page shadow effect
		context.translate(pagePadding, pagePadding)
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

	def initDraw(self, context, width, height):
		
		# Calculate the width and height of each partOGL in the part dictionary and each CSI
		self.initPartDimensions()
		
		# Calculate an initial layout for each Step and PLI in this instruction book
		for step in self.mainModel.partOGL.steps:
			step.initLayout(context, width, height)

	def initPartDimensions(self):
		# TODO: CSI dimensions should *NOT* be stored with part dimensions.  Part dimensions
		# should be shareable across models, if those models have the necessary same display setting.
		# Instead, store CSI dimensions right along with the STEP command right in the model file
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
			if (line[0] == 's'):  # Step dimensions, for CSI
				stepNumber, filename, w, h, x, y = line[1:].split()
				if (not partDictionary.has_key(filename)):
					print "Warning: part dimension cache contains CSI images not present in model - suggest regenerating part dimension cache."
					continue
				
				p = partDictionary[filename]
				if (len(p.steps) < int(stepNumber)):
					print "Warning: part dimension cache contains CSI images not present in model - suggest regenerating part dimension cache."
					continue
				csi = p.steps[int(stepNumber) - 1].csi
				csi.box.width = max(1, int(w))
				csi.box.height = max(1, int(h))
				csi.centerOffset = Point(int(x), int(y))
				
			elif (line[0] == 'p'):  # Part dimensions, for PLI
				filename, w, h, x, y, l, b = line[1:].split()
				if (not partDictionary.has_key(filename)):
					print "Warning: part dimension cache contains parts not present in model - suggest regenerating part dimension cache."
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
			csiList.append(step.csi)
		return csiList

	def initPartDimensionsManually(self):
		"""
		Used to calculate each part's display width and height if no valid part dimension cache file exists.
		Creates GL FBOs to render a temp copy of each part, then use those raw pixels to determine size.
		Will create and store results in a part dimension cache file.
		"""
		
		imgList = [part for part in partDictionary.values() if not part.isPrimitive]
		imgList += self.buildCSIList(self.mainModel.partOGL)
		
		imgList2 = []
		lines = []
		sizes = [256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels
		
		for size in sizes:
			
			# Create a new FBO
			buffers = createFBO(size, size)
			if (buffers is None):
				print "ERROR: Failed to initialize FBO - aborting initPartDimensionsManually"
				return
			
			# Render each image and calculate their sizes
			for item in imgList:
				
				successfulDraw = item.initSize(size, size)  # Draw image and calculate its size
				
				if (successfulDraw):
					dimensionString = item.dimensionsToString()
					if (dimensionString):
						lines.append(dimensionString)
				else:
					imgList2.append(item)
			
			# Clean up created FBO
			destroyFBO(*buffers)
			
			if (len(imgList2) < 1):
				break  # All images initialized successfully
			else:
				imgList = imgList2  # Some images rendered out of frame - loop and try bigger frame
				imgList2 = []
		
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
	
	def __init__(self, topLeftCorner = Point(10, 10)):
		
		self.box = Box(topLeftCorner.x, topLeftCorner.y)
		self.qtyLabelFont = Font(size = 14, bold = True)
		self.qtyMultiplierChar = 'x'
		self.layout = {}  # {part filename: [count, part, bottomLeftCorner, qtyLabelReference]}
	
	def isEmpty(self):
		if (len(self.layout) > 0):
			return False
		return True

	def addPartOGL(self, part):
		
		if (part.filename in self.layout):
			self.layout[part.filename][0] += 1
		else:
			self.layout[part.filename] = [1, part, Point(0, 0), Point(0, 0)]

	def initLayout(self, context, csiBox, width, height):
		
		# TODO: This entire method places parts from left to right in the order they
		# were added to PLI. *Very* naive, and usually ugly.  After CSIs are properly
		# created and laid out, redo this algorithm to have PLIs flow around CSIs
		
		# If this PLI is empty, nothing to do here
		if (len(self.layout) < 1):
			return
		
		# Sort the list of parts in this PLI from widest to narrowest, with the tallest one first
		partList = self.layout.values()
		tallestPart = max(partList, key=findHighestItem)
		partList.remove(tallestPart)
		partList.sort(compareLayoutItemWidths)
		partList.insert(0, tallestPart)
		
		# Note that PLI box's top left corner must be set by container before this
		b = self.box
		overallX = b.x + b.internalGap
		b.width = b.height = UNINIT_PROP
		
		for i, (count, part, corner, labelCorner) in enumerate(partList):  # item: [count, part, bottomLeftCorner]
			
			# If this part has steps of its own, like any good submodel, initialize those PLIs
			for step in part.steps:
				step.initLayout(context, width, height)
			
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
	
	def drawParts(self, width, height):
		""" Must be called inside a valid gldrawable context. """
		
		if (len(self.layout) < 1):
			return  # No parts in this PLI - nothing to draw
		
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
			return
		
		pushAllGLMatrices()
		
		for (count, part, corner, labelCorner) in self.layout.values():
			adjustGLViewport(corner.x, corner.y - part.height, part.width, part.height)
			glLoadIdentity()
			rotateToDefaultView(part.center.x, part.center.y, 0.0)
			part.drawModel()
		
		popAllGLMatrices()

	def drawPageElements(self, context):
		""" Draw this PLI's background, border and quantity labels to the specified cairo context. """
		
		if (len(self.layout) < 1):
			return  # No parts in this PLI - nothing to draw
		
		if (self.box.width == UNINIT_PROP or self.box.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
		
		# Draw the PLIs overall bounding box
		self.box.draw(context)
		
		# Draw the quantity label for each part, if needed
		for (count, part, corner, labelCorner) in self.layout.values():
			
			# Draw part's quantity label
			self.qtyLabelFont.passToCairo(context)
			context.move_to(labelCorner.x, labelCorner.y)
			context.show_text(str(count) + self.qtyMultiplierChar)

def findHighestItem(item):
	return item[1].height

def compareLayoutItemWidths(item1, item2):
	""" Returns 1 if part 2 is wider than part 1, 0 if equal, -1 if narrower. """
	if (item1[1].width < item2[1].width):
		return 1
	if (item1[1].width == item2[1].width):
		return 0
	return -1

def compareLayoutItemHeights(item1, item2):
	""" Returns 1 if part 2 is taller than part 1, 0 if equal, -1 if shorter. """
	if (item1[1].height < item2[1].height):
		return 1
	if (item1[1].height == item2[1].height):
		return 0
	return -1

class CSI():
	"""
	Construction Step Image.  Includes border and positional info.
	"""
	
	def __init__(self, filename, step, buffers):
		self.box = Box(0, 0)
		self.centerOffset = Point(0, 0)
		self.filename = filename
		self.step = step
		self.buffers = buffers  # [(bufID, stepNumber)], set of buffers active inside this CSI
		
		self.oglDispIDs = []  # [(dispID, buffer)]
		self.oglDispID = UNINIT_OGL_DISPID
	
	def initSize(self, width, height):
		"""
		Initialize this CSI's display width, height and center point. To do
		this, draw this CSI to the already initialized GL Frame Buffer Object.
		These dimensions are required to properly lay out PLIs and CSIs.
		Note that an appropriate FBO *must* be initialized before calling initSize.
		
		Parameters:
			width: Width of FBO to render to, in pixels.
			height: Height of FBO to render to, in pixels.
		
		Returns:
			True if CSI rendered successfully.
			False if the CSI has been rendered partially or wholly out of frame.
		"""
		
		# TODO: update some kind of load status bar her - this function is *slow*
		#print "Initializing CSI %s, step %d - size %dx%d" % (self.filename, self.step.number, width, height)
		
		params = initImgSize(width, height, self.oglDispID, wantInsets = False, filename = self.filename + " - step " + str(self.step.number))
		if (params is None):
			return False
		
		self.box.width, self.box.height, self.centerOffset = params
		return True

	def dimensionsToString(self):
		return "s %d %s %d %d %d %d\n" % (self.step.number, self.filename, self.box.width, self.box.height, self.centerOffset.x, self.centerOffset.y)
	
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

	def getDefaultBox(self, width, height):
		b = Box(x = self.box.x, y = self.box.y)
		b.x = (width / 2.) - (self.box.width / 2.)
		b.y = (height / 2.) - (self.box.height / 2.)
		return b

	def createOGLDisplayList(self):
		if (self.oglDispIDs != []):
			# TODO: Ensure we don't ever call this, then remove this check
			return   # Have already initialized this Step's display list, so do nothing
		
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

	def drawModel(self, width, height):
		
		adjustGLViewport(0, 0, width, height)
		glLoadIdentity()
		rotateToDefaultView(self.centerOffset.x, self.centerOffset.y, 0.0)
		glCallList(self.oglDispID)

	def drawPageElements(self, context, width, height):
		b = self.box
		if (b.width == UNINIT_PROP or b.height == UNINIT_PROP):
			print "ERROR: Trying to draw an unitialized PLI layout!"
			return
		
		b.x = (width / 2.) - (b.width / 2.)
		b.y = (height / 2.) - (b.height / 2.)
		b.draw(context)

	def callOGLDisplayList(self):
		glCallList(self.oglDispIDs[0][0])
		
	def writeToFileArray(self, ldrawFileArray):
		line1 = "0 LIC CSI %d %d\n" % (self.centerOffset.x, self.centerOffset.y)
		line2 = "0 LIC BOX %d %d %d %d \n" % (self.box.x, self.box.y, self.box.width, self.box.height)

class Step():
	def __init__(self, filename, prevStep = None, buffers = []):
		self.parts = []
		self.prevStep = prevStep
		
		self.internalGap = 20
		self.stepNumberFont = Font(20)
		self.stepNumberRefPt = Point(0, 0)
		
		if (prevStep):
			self.number = prevStep.number + 1
		else:
			self.number = 1
		
		self.csi = CSI(filename, self, list(buffers))
		self.pli = PLI(Point(self.internalGap, self.internalGap))

	def addPart(self, part):
		self.parts.append(part)
		if (not part.ignorePLIState):
			self.pli.addPartOGL(part.partOGL)

	def initLayout(self, context, width, height):
		
		csiBox = self.csi.getDefaultBox(width, height)
		self.pli.initLayout(context, csiBox, width, height)
		
		# Figure out the display height of the step number label
		self.stepNumberFont.passToCairo(context)
		xbearing, ybearing, labelWidth, labelHeight, xa, ya = context.text_extents(str(self.number))
		
		# Initialize this step number's label position
		self.stepNumberRefPt.x = self.pli.box.x - xbearing
		if (self.pli.isEmpty()):
			self.stepNumberRefPt.y = self.internalGap - ybearing
		else:
			self.stepNumberRefPt.y = self.internalGap * 2 + self.pli.box.height	- ybearing

	def drawModel(self, width, height):
		""" Draw this step's CSI and PLI parts (not GUI elements, just the 3D GL bits) """
		self.pli.drawParts(width, height)
		self.csi.drawModel(width, height)

	def drawPageElements(self, context, width, height):
		""" Draw this step's PLI and CSI page elements, and this step's number label. """
		self.csi.drawPageElements(context, width, height)
		self.pli.drawPageElements(context)
		
		# Draw this step's number label
		self.stepNumberFont.passToCairo(context)
		context.move_to(self.stepNumberRefPt.x, self.stepNumberRefPt.y)
		context.show_text(str(self.number))

	def writeToFile(self):
		ignore = False
		buffers = []
		lines = ["0 STEP"]
		for part in self.parts:
			if part.ignorePLIState != ignore:
				if part.ignorePLIState:
					state = "BEGIN IGN"
				else:
					state = "END"
				lines.append("0 LPUB PLI " + state)
				ignore = part.ignorePLIState
			lines.append(part.writeToFile())
		
		# If we're still ignoring piece, stop - PLI IGN pairs shouldn't span Steps
		if ignore:
			lines.append("0 LPUB PLI END")
		return lines

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
		
		self.width = self.height = 1
		self.leftInset = self.bottomInset = 0
		self.center = Point(0, 0)
		
		if ((parentLDFile is not None) and (filename in parentLDFile.subModelsInFile)):
			self._loadFromSubModelArray(parentLDFile)
		else:
			self._loadFromFile(hasSteps)
		
		# Check if the last step in model is empty - occurs often, since we've implicitly
		# created a step before adding any parts and many models end with a Step.
		if (len(self.steps) > 0 and self.steps[-1].parts == []):
			self.steps.pop()
		
		self.createOGLDisplayList()
	
	def _loadFromSubModelArray(self, ldrawFile):
		
		self.currentStep = Step(self.filename)
		self.steps = [self.currentStep]
		self.ldrawFile = ldrawFile
		
		start, end = ldrawFile.subModelsInFile[self.filename]
		subModelArray = ldrawFile.fileArray[start + 1 : end]
		
		for line in subModelArray:
			self._loadOneLDrawLineCommand(line)

	def _loadFromFile(self, hasSteps):
		
		self.ldrawFile = LDrawFile(self.filename)
		if hasSteps:
			self.ldrawFile.addInitialStep()
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
			self.addPart(lineToPart(line), line)
		
		elif (isValidGhostLine(line)):
			self.addPart(lineToGhostPart(line), line)
		
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
		
		self.currentStep = Step(self.filename, self.currentStep, list(self.buffers))
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
		return "p %s %d %d %d %d %d %d\n" % (self.filename, self.width, self.height, self.center.x, self.center.y, self.leftInset, self.bottomInset)

	def initSize(self, width, height):
		"""
		Initialize this part's display width, height, empty corner insets and center point.
		To do this, draw this part to the already initialized GL Frame Buffer Object.
		These dimensions are required to properly lay out PLIs and CSIs.
		Note that an appropriate FBO *must* be initialized before calling initSize.
		
		Parameters:
			width: Width of FBO to render to, in pixels.
			height: Height of FBO to render to, in pixels.
		
		Returns:
			True if part rendered successfully.
			False if the part has been rendered partially or wholly out of frame.
		"""
		
		# Primitive parts need not be sized
		if (self.isPrimitive):
			return True
		
		# TODO: update some kind of load status bar her - this function is *slow*
		#print self.filename,
		
		params = initImgSize(width, height, self.oglDispID, wantInsets = True, filename = self.filename)
		if (params is None):
			return False
		
		self.width, self.height, self.leftInset, self.bottomInset, self.center = params
		return True

	def writeToFile(self):
		lines = []
		for step in self.steps:
			lines += step.writeToFile()

		f = open(self.ldrawFile.path + "test_" + self.ldrawFile.filename, 'w')
		for line in lines:
			f.write(line + "\n")
		f.close()

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
		self.fileLine = []
		
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
	
	def writeToFile(self):
		return ' '.join(self.fileLine[1:])
	
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
