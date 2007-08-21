
CurrentColor = 16
ComplimentColor = 24

# Array storing [R,G,B,name] values for each LDraw Color
colors = {
	0:  [0.13, 0.13, 0.13, 'Black'],
	1:  [0.00, 0.20, 0.70, 'Blue'],
	2:  [0.00, 0.55, 0.08, 'Green'],
	3:  [0.00, 0.60, 0.62, 'Teal'],
	4:  [0.77, 0.00, 0.15, 'Red'],
	5:  [0.87, 0.40, 0.58, 'Dark Pink'],
	6:  [0.36, 0.13, 0.00, 'Brown'],
	7:  [0.76, 0.76, 0.76, 'Grey'],
	8:  [0.39, 0.37, 0.32, 'Dark Grey'],
	9:  [0.42, 0.67, 0.86, 'Light Blue'],
	10: [0.42, 0.93, 0.56, 'Bright Green'],
	11: [0.20, 0.65, 0.65, 'Turquoise'],
	12: [1.00, 0.52, 0.48, 'Salmon'],
	13: [0.98, 0.64, 0.78, 'Pink'],
	14: [1.00, 0.86, 0.00, 'Yellow'],
	15: [1.00, 1.00, 1.00, 'White'],
	16: CurrentColor,
	17: [0.73, 1.00, 0.81, 'Pastel Green'],
	18: [0.99, 0.91, 0.59, 'Light Yellow'],
	19: [0.91, 0.81, 0.63, 'Tan'],	
	20: [0.84, 0.77, 0.90, 'Light Violet'],
	21: [0.88, 1.00, 0.69, 'Glow in the Dark'],
	22: [0.51, 0.00, 0.48, 'Violet'],
	23: [0.28, 0.20, 0.69, 'Violet Blue'],
	24: ComplimentColor,
	25: [0.98, 0.38, 0.00, 'Orange'],	
	26: [0.85, 0.11, 0.43, 'Magenta'],
	27: [0.84, 0.94, 0.00, 'Lime'],
	28: [0.77, 0.59, 0.31, 'Dark Tan'],
	
	32: [0.39, 0.37, 0.32, 0.90, 'Trans Gray'],
	33: [0.00, 0.13, 0.63, 0.90, 'Trans Blue'],
	34: [0.02, 0.39, 0.20, 0.90, 'Trans Green'],
	
	36: [0.77, 0.00, 0.15, 0.90, 'Trans Red'],
	37: [0.39, 0.00, 0.38, 'Trans Violet'], # missing alpha?
	
	40: [0.39, 0.37, 0.32, 0.90, 'Trans Gray'],
	41: [0.68, 0.94, 0.93, 0.95, 'Trans Light Cyan'],		
	42: [0.75, 1.00, 0.00, 0.90, 'Trans Flu Lime'],
	
	45: [0.87, 0.40, 0.58, 'Trans Pink'], # missing alpha?
	46: [0.79, 0.69, 0.00, 0.90, 'Trans Yellow'],
	47: [1.00, 1.00, 1.00, 0.90, 'Trans White'],
	
	57: [0.98, 0.38, 0.00, 0.80, 'Trans Flu Orange'],
	
	70: [0.41, 0.25, 0.15, 'Reddish Brown'],
	71: [0.64, 0.64, 0.64, 'Stone Gray'],
	72: [0.39, 0.37, 0.38, 'Dark Stone Gray'],
	
	134: [0.58, 0.53, 0.40, 'Pearl Copper'],
	135: [0.67, 0.68, 0.67, 'Pearl Gray'],
	
	137: [0.42, 0.48, 0.59, 'Pearl Sand Blue'],
	
	142: [0.84, 0.66, 0.29, 'Pearl Gold'],
	
	256: [0.13, 0.13, 0.13, 'Rubber Black'],
	
	272: [0.00, 0.11, 0.41, 'Dark Blue'],
	273: [0.00, 0.20, 0.70, 'Rubber Blue'],
	
	288: [0.15, 0.27, 0.17, 'Dark Green'],
	
	320: [0.47, 0.00, 0.11, 'Dark Red'],
	
	324: [0.77, 0.00, 0.15, 'Rubber Red'],
	
	334: [0.88, 0.43, 0.07, 'Chrome Gold'],
	335: [0.75, 0.53, 0.51, 'Sand Red'],
	
	366: [0.82, 0.51, 0.02, 'Earth Orange'],
	
	373: [0.52, 0.37, 0.52, 'Sand Violet'],
	
	375: [0.76, 0.76, 0.76, 'Rubber Gray'],
	
	378: [0.63, 0.74, 0.67, 'Sand Green'],
	379: [0.42, 0.48, 0.59, 'Sand Blue'],
	
	382: [0.91, 0.81, 0.63, 'Tan'],	

	431: [0.73, 1.00, 0.81, 'Pastel Green'],

	462: [1.00, 0.62, 0.02, 'Light Orange'],
	
	484: [0.70, 0.24, 0.00, 'Dark Orange'],
	
	494: [0.82, 0.82, 0.82, 'Electric Contact'],
	
	503: [0.90, 0.89, 0.85, 'Light Gray'],
	
	511: [1.00, 1.00, 1.00, 'Rubber White'],
}

complimentColors = [ 8, 9, 10, 11, 12, 13, 0, 8, 0, 1, 2, 3, 4, 5, 8, 8]

def convertToRGBA(LDrawColorCode):
	if (LDrawColorCode == CurrentColor):
		return CurrentColor
	if (LDrawColorCode == ComplimentColor):
		return ComplimentColor
	return colors[LDrawColorCode][0:-1]
	
def getColorName(LDrawColorCode):
	if (LDrawColorCode == CurrentColor):
		return CurrentColor
	if (LDrawColorCode == ComplimentColor):
		return ComplimentColor
	return colors[LDrawColorCode][-1]

def complimentColor(LDrawColorCode):
	if (LDrawColorCode > len(complimentColors)):
		return convertToRGBA(complimentColors[-1])
	return convertToRGBA(complimentColors[LDrawColorCode])

class Snippets():
	
	def stuff():
		for i in range(0, len(subModels)-1):
			subModels[i] = (subModels[i][0], [subModels[i][1], subModels[i+1][1]])
		subModels[-1] = (subModels[-1][0], [subModels[-1][1], len(self.fileArray)])
		
		subModels = []
		for i in range(0, len(self.fileArray)):
			l = self.fileArray[i]
			if ((len(l) > 2) and (l[0] == 0) and (l[1] == 'FILE')):
				subModels.append((l[2], i))
				
		for i in range(0, len(subModels)-1):
			subModels[i] = (subModels[i][0], [subModels[i][1], subModels[i+1][1]])
		subModels[-1] = (subModels[-1][0], [subModels[-1][1], len(self.fileArray)])
		
		# self.subModelsInFile = {"filename": [startline, endline]}
		self.subModelsInFile = dict(subModels)

	def hexme(str):
		r = str[:2]
		g = str[2:4]
		b = str[4:]
		r = int(r, 16)
		g = int(g, 16)
		b = int(b, 16)
		r /= 255.
		b /= 255.
		g /= 255.
		r = round(r, 4)
		g = round(g, 4)
		b = round(b, 4)
		return [r, g, b]
	
	def polyline( vertexes_list, closed = False):
		if closed:
			glBegin( GL_LINE_LOOP )
		else:
			glBegin( GL_LINE_STRIP )
		
		for vertex in vertexes_list:
			glVertex3f( vertex[0], vertex[1], vertex[2] )
		
		glEnd()

	def stf_safe(x):
		if (('.' in x) or ('e' in x)):
			try:
				return float(x)
			except ValueError:
				return x
		else:
			try:
				return int(x)
			except ValueError:
				return x

class OGLPart():
	def __init__(self, filename):
		self.filename = filename
		self.name = ''
		self.oglDispID = 0
		self._loadContents()

	def _loadContents(self):
		self.oglDispID = glGenLists(1)
		glNewList(self.oglDispID, GL_COMPILE)
		self._loadLDrawFile(self.filename)
		glEndList()

	# TODO: If needed for performance, can merge subsequent tris/quads into one strip
	def _postProcessArrays(self):
		pass
		
	def _loadLDrawFile(self, filename):
		
		try:
			f = file(LDrawPath + "PARTS\\" + filename)
		except IOError:
			try:
				f = file(LDrawPath + "P\\" + filename)
			except IOError:
				try:
					f = file(LDrawPath + "MODELS\\" + filename)
				except IOError:
					print "No such file or directory: ", filename
					return
		
		title = f.readline().strip()
		if (title[0] == '0'):
			self.name = title[1:].strip()
			
		for line in f:
			self._loadOneLDrawLineCommand(line)
		f.close()
	
	def _loadOneLDrawLineCommand(self, line):
		a = [stf_safe(x) for x in line.split()]
		
		if (len(a) < 2):
			return
		
		command = a[0]
		
		if ((command != 1) and (command != 3) and (command != 4)):
			return
	
		# If this piece has its own color, use it.
		color = LDrawColors.convertToRGBA(a[1])
		if (color != LDrawColors.CurrentColor):
			
			if (color == LDrawColors.ComplimentColor):
				color = LDrawColors.complimentColor(self.color)
				
			glPushAttrib(GL_CURRENT_BIT)
			if (len(color) == 3):
				glColor3fv(color)
			elif (len(color) == 4):
				glColor4fv(color)

		a = a[2:]
		if (command == 1):
			matrix = LDrawMatrixToOGLMatrix(a)
			glPushMatrix()
			glMultMatrixf(matrix)
			self._loadLDrawFile(a[12])
			glPopMatrix()
			
		elif (command == 3):
			self._loadLDrawTriangleCommand(a)
	
		elif (command == 4):
			self._loadLDrawQuadCommand(a)

		# Restore color if necessary
		if (color != LDrawColors.CurrentColor):
			glPopAttrib()

	def _loadLDrawTriangleCommand(self, a):
		glBegin( GL_TRIANGLES )
		glVertex3f( a[0], a[1], a[2] )
		glVertex3f( a[3], a[4], a[5] )
		glVertex3f( a[6], a[7], a[8] )
		glEnd()
	
	def _loadLDrawQuadCommand(self, a):
		glBegin( GL_QUADS )
		glVertex3f( a[0], a[1],  a[2] )
		glVertex3f( a[3], a[4],  a[5] )
		glVertex3f( a[6], a[7],  a[8] )
		glVertex3f( a[9], a[10], a[11] )
		glEnd()
	
class OGLPart():
	def __init__(self, filename):
		self.filename = filename
		self.name = ''
		self.oglDispID = 0
		self._loadContents()

	def _loadContents(self):
		self.oglDispID = glGenLists(1)
		glNewList(self.oglDispID, GL_COMPILE)
		self._loadLDrawFile(self.filename)
		glEndList()

	def _loadLDrawFile(self, filename):
		
		try:
			f = file(LDrawPath + "PARTS\\" + filename)
		except IOError:
			try:
				f = file(LDrawPath + "P\\" + filename)
			except IOError:
				try:
					f = file(LDrawPath + "MODELS\\" + filename)
				except IOError:
					print "No such file or directory: ", filename
					return
		
		title = f.readline().strip()
		if (title[0] == '0'):
			self.name = title[1:].strip()
			
		for line in f:
			self._loadOneLDrawLineCommand(line)
		f.close()
	
	def _loadOneLDrawLineCommand(self, line):
		a = [stf_safe(x) for x in line.split()]
		
		if (len(a) < 2):
			return
		
		command = a[0]
		
		if ((command != 1) and (command != 3) and (command != 4)):
			return
		
		# If this piece has its own color, use it.
		color = LDrawColors.convertToRGBA(a[1])
		if (color != LDrawColors.CurrentColor):
			
			if (color == LDrawColors.ComplimentColor):
				color = LDrawColors.complimentColor(self.color)
				
			glPushAttrib(GL_CURRENT_BIT)
			if (len(color) == 3):
				glColor3fv(color)
			elif (len(color) == 4):
				glColor4fv(color)

		a = a[2:]
		if (command == 1):
			matrix = LDrawMatrixToOGLMatrix(a)
			glPushMatrix()
			glMultMatrixf(matrix)
			self._loadLDrawFile(a[12])
			glPopMatrix()
			
		elif (command == 3):
			self._loadLDrawTriangleCommand(a)
	
		elif (command == 4):
			self._loadLDrawQuadCommand(a)

		# Restore color if necessary
		if (color != LDrawColors.CurrentColor):
			glPopAttrib()

	def _loadLDrawTriangleCommand(self, a):
		glBegin( GL_TRIANGLES )
		glVertex3f( a[0], a[1], a[2] )
		glVertex3f( a[3], a[4], a[5] )
		glVertex3f( a[6], a[7], a[8] )
		glEnd()
	
	def _loadLDrawQuadCommand(self, a):
		glBegin( GL_QUADS )
		glVertex3f( a[0], a[1],  a[2] )
		glVertex3f( a[3], a[4],  a[5] )
		glVertex3f( a[6], a[7],  a[8] )
		glVertex3f( a[9], a[10], a[11] )
		glEnd()
		
	def shouldBeDrawn(self, currentBuffer):
		
		if (len(self.buffers) < 1):
			return True  # Piece not in any buffer - draw always
		
		# So, this piece is in a buffer
		if ((currentBuffer is None) or (len(currentBuffer) < 1)):
			return False  # Piece in a buffer, but no current buffer - don't draw
		
		for buffer in self.buffers:
			if (buffer in currentBuffer):
				return True  # Piece in a buffer, and buffer in current buffer stack - draw
		
		return False # Piece in a buffer, but buffer not in current stack - don't draw

	def BFCcrap(self):
		if ((len(a) == 4) and (a[0] == 0) and (a[1] == 'BFC')):
			if (a[3] == 'CW'):
				self.order = GL_CW
			else:
				self.order = GL_CCW
			return
		
		if ((len(a) > 2) and (a[0] == 0) and (a[1] == 'BFC')):
			if (a[2] == 'INVERTNEXT'):
				self.invertNext = True
				return
			if ((len(a) == 4) and (a[3] == 'CW')):
				self.inverted = True
			else:
				self.inverted = False
			return
		
class ModelOGL_old_works():
	def __init__(self):
		self.oglDispID = UNINITIALIZED_OGL_DISPID
		
		self.currentStep = Step()
		self.steps = [self.currentStep]
		self.buffers = []  #[(bufID, stepNumber)]
		
		# Model Title is generally the last entry on the first line in the file
		self.name = ldrawFile.fileArray[0][-1]
		print "New SubModel: ", self.name
		
		self.loadParts()
		self.createOGLDisplayList()

	def loadParts(self):
		start, end = ldrawFile.subModelsInFile[self.name]
		subModelArray = ldrawFile.fileArray[start+1:end]
		
		for line in subModelArray:
			if (isValidFileLine(line)):
				return  # hit the first subModel - main Model is fully loaded
			
			elif (isValidStepLine(line)):
				self.addStep()
			
			elif (isValidPartLine(line)):
				self.addPart(lineToPart(line))
				
			elif (isValidGhostLine(line)):
				self.addPart(lineToGhostPart(line))
			
			elif (isValidBufferLine(line)):
				buffer, state = lineToBuffer(line).values()
				
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

	def addStep(self):
		if (self.currentStep.parts == []): # Current step is empty - remove it and warn
			print "Step Warning: Empty step found.  Ignoring Step #", self.currentStep.number
			self.steps.pop()
			self.currentStep = self.currentStep.prevStep
		
		self.currentStep = Step(self.currentStep, list(self.buffers))
		self.steps.append(self.currentStep)

	def addPart(self, p):
		try:
			part = Part(p['filename'], p['color'], p['matrix'], p['ghost'], list(self.buffers))
		except IOError:
			print "In ModelOGL, Ignoring file: %s" % p['filename']
			return
		
		self.currentStep.addPart(part)

	def draw(self):
		glCallList(self.oglDispID)

	def createOGLDisplayList(self):
		
		# Create the display lists for all parts in the dictionary
		for partOGL in partDictionary.values():
			partOGL.createOGLDisplayList()
		
		# Create a display list for each step
		for step in self.steps:
			step.createOGLDisplayList()
		
		self.oglDispID = glGenLists(1);
		glNewList(self.oglDispID, GL_COMPILE)
		
		for step in self.steps:
			step.callOGLDisplayList()
		
		glEndList()
		
		# TODO: Handle BFC statements PROPERLY.  This is a mess.
#		if (isValidBFCLine(line)):
#			if (line[2] == 'INVERTNEXT'):
#				self.invertNext = True
#				return
#			if ((len(line) == 4) and (line[3] == 'CW')):
#				self.inverted = True
#			else:
#				self.inverted = False
#			return
		
		# remove any empty or too-short lines
		#self.fileArray = [x for x in self.fileArray if x != [] and len(x) > 1]

#		im.save("C:\\" + self.filename + "_cropped.png")
	
	def stf_safe(x):
		try:
			return float(x)
		except ValueError:
			return x

	def cairo_samples():
		cr = self.cairo_context
		if (len(args) > 1):
			area = args[1].area
			cr.rectangle(area.x, area.y, area.width, area.height)
			cr.clip()
		
		x = self.width / 2
		y = self.height / 2
		radius = min(x, y) - 5
		cr.arc(x, y, radius, 0, 2 * math.pi)
		#cr.set_source_rgb(1,1,1)
		#cr.fill_preserve()
		cr.set_source_rgb(0,0,0)
		cr.stroke()
	
def restoreGLViewport():
	# restoreGLViewport.width & height set by on_configure_event, when window resized
	adjustGLViewport(0, 0, restoreGLViewport.width, restoreGLViewport.height)
	
