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
	
	# Temp debug - draw bottom left empty triangle
	context.set_source_rgb(1.0, 0.0, 0.0)
	context.move_to(corner.x, corner.y)
	context.line_to(corner.x + part.bottomInset, corner.y)
	context.line_to(corner.x, corner.y - part.leftInset)
	context.close_path()
	context.stroke()
	
	# Temp debug - draw rectangle bounding calculated 'x'
	context.rectangle(dx + xbearing, labelTopLeftY, width, height)
	context.stroke()

def debugInfoInInitSize():
	#print self.filename
	#print "old t: %d, b: %d, l: %d, r: %d" % (top, bottom, left, right)
	#print "displacing by x: %d, y: %d" % (x, y)
	#print "new t: %d, b: %d, l: %d, r: %d" % (top, bottom, left, right)

def writeStepToFile(self):
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
	return line	

def writePartOGLToFile(self):
	lines = []
	for step in self.steps:
		lines += step.writeToFile()
		
	f = open(self.ldrawFile.path + "test_" + self.ldrawFile.filename, 'w')
	for line in lines:
		f.write(line + "\n")
	f.close()

def writePartToFile(self):
	return ' '.join(self.fileLine[1:])

