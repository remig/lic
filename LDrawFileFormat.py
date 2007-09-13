import shutil  # for file copy / rename
import os      # for path creation

from Drawables import *

import l3p
import povray

LDrawPath = "C:\\LDrawParts\\"

Comment = '0'
PartCommand = '1'
LineCommand = '2'
TriangleCommand = '3'
QuadCommand = '4'
ConditionalLineCommand = '5'

StepCommand = 'STEP'
FileCommand = 'FILE'
ClearCommand = 'CLEAR'
PauseCommand = 'PAUSE'
SaveCommand = 'SAVE'
GhostCommand = 'GHOST'
BufferCommand = 'BUFEXCHG'
BFCCommand = 'BFC'

BufferStore = 'STORE'
BufferRetrieve = 'RETRIEVE'

LPubCommand = 'LPUB'
LICCommand = 'LIC'
CSICommand  = 'CSI'
PLICommand  = 'PLI'
PLIItemCommand  = 'PLIi'
BEGINCommand  = 'BEGIN'
ENDCommand  = 'END'
IGNCommand  = 'IGN'

def LDToOGLMatrix(matrix):
	m = [float(x) for x in matrix]
	return [m[3], m[6], m[9], 0.0, m[4], m[7], m[10], 0.0, m[5], m[8], m[11], 0.0, m[0], m[1], m[2], 1.0]

def isValidTriangleLine(line):
	return (len(line) == 12) and (line[1] == TriangleCommand)

def lineToTriangle(line):
	d = {}
	d['color'] = float(line[2])
	d['points'] = [float(x) for x in line[3:]]
	return d

def isValidQuadLine(line):
	return (len(line) == 15) and (line[1] == QuadCommand)

def lineToQuad(line):
	d = {}
	d['color'] = float(line[2])
	d['points'] = [float(x) for x in line[3:]]
	return d

def isValidFileLine(line):
	return (len(line) > 2) and (line[1] == Comment) and (line[2] == FileCommand)

def isValidStepLine(line):
	return (len(line) > 2) and (line[1] == Comment) and (line[2] == StepCommand)

def isValidPartLine(line):
	return (len(line) > 15) and (line[1] == PartCommand)

def lineToPart(line):
	return {'filename': line[15],
			'color': float(line[2]),
			'matrix': LDToOGLMatrix(line[3:15]),
			'ghost': False}

def isValidGhostLine(line):
	return (len(line) > 17) and (line[1] == Comment) and (line[2] == GhostCommand) and (line[3] == PartCommand)

def lineToGhostPart(line):
	d = lineToPart(line[2:])
	d['ghost'] = True
	return d

def isValidBufferLine(line):
	return (len(line) > 4) and (line[1] == Comment) and (line[2] == BufferCommand)

def lineToBuffer(line):
	return {'buffer': line[3], 'state': line[4]}

def isValidBFCLine(line):
	# TODO: implement all BFC options
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == BFCCommand)

def lineToBFC(line):
	# TODO: implement all BFC options
	return {'command': line[3]}

def isValidLPubLine(line):
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == LPubCommand)

def isValidLPubPLILine(line):
	return isValidLPubLine(line) and (len(line) > 4) and (line[3] == PLICommand)

def lineToLPubPLIState(line):
	if line[4] == BEGINCommand:
		return True
	return False

def isValidLICLine(line):
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == LICCommand)

def isValidCSILine(line):
	return isValidLICLine(line) and (len(line) > 9) and (line[3] == CSICommand)

def lineToCSI(line):
	# [index, Comment, LICCommand, CSICommand, self.box.x, self.box.y, self.box.width, self.box.height, self.centerOffset.x, self.centerOffset.y]
	return {'box': Box(float(line[4]), float(line[5]), float(line[6]), float(line[7])),
			'offset': Point(float(line[8]), float(line[9]))}

def isValidPLILine(line):
	return isValidLICLine(line) and (len(line) > 10) and (line[3] == PLICommand)

def lineToPLI(line):
	# [index, Comment, LICCommand, PLICommand, self.box.x, self.box.y, self.box.width, self.box.height, self.qtyMultiplierChar, self.qtyLabelFont.size, self.qtyLabelFont.face]
	return {'box': Box(float(line[4]), float(line[5]), float(line[6]), float(line[7])),
			'qtyLabel': line[8],
			'font': Font(float(line[9]), line[10])}

def isValidPLIItemLine(line):
	return isValidLICLine(line) and (len(line) > 9) and (line[3] == PLIItemCommand)

def lineToPLIItem(line):
	# [index, Comment, LICCommand, PLIItemCommand, filename, item[0], item[2].x, item[2].y, item[3].x, item[3].y]
	# {part filename: [count, part, bottomLeftCorner, qtyLabelReference]}
	return {'filename': line[4],
			'count': int(line[5]),
			'corner': Point(float(line[6]), float(line[7])),
			'labelCorner': Point(float(line[8]), float(line[9]))}

class LDrawFile():
	def __init__(self, filename):
		
		self.filename = filename  # filename, like 3057.dat
		self.name = ""            # coloquial name, like 2 x 2 brick
		self.path = LDrawPath     # path where filename was found
		self.isPrimitive = False  # Anything in the 'P' directory
		
		self.fileArray = []
		self.subModelArray = {}
		
		self._loadFileArray()
		self._findSubModelsInFile()

	def addLICHeader(self):
		
		for i, line in enumerate(self.fileArray):
			if isValidLICLine(line):
				return True
			if isValidStepLine(line) or isValidPartLine(line) or isValidGhostLine(line) or isValidBufferLine(line) or isValidLPubPLILine(line):  
				break  # Stuff that should be in a Step isn't - add new Step
		
		self.insertLine(i, [Comment, LICCommand, 'Initialized'])
		return False

	def addInitialSteps(self):
		
		lines = []
		currentFileLine = False
		for line in self.fileArray:
			if isValidFileLine(line):
				currentFileLine = True
					 
			if isValidStepLine(line):   # Already have initial step - nothing to do here
				currentFileLine = False
			
			if isValidPartLine(line) or isValidGhostLine(line) or isValidBufferLine(line) or isValidLPubPLILine(line):
				if currentFileLine:
					lines.append(line)
					currentFileLine = False
		
		for line in lines:
			self.insertLine(line[0] - 1, [Comment, StepCommand])
	
	def insertLine(self, index, line):
		"""
		Insert the specified line into the file array at the specified index (0-based).
		line is expected to be an array of various types, making up the overall LDraw line to be added.
		Do not prepend the line number - line should start with one of the LDraw commands listed above.
		line will be modified to include the appropriate line index, and all entries converted to strings.
		"""
		
		# Convert line entries to strings, and prepend line number to the line command, as the file array expects
		line = [str(x) for x in line]
		line.insert(0, index+1)
		
		# Insert the new line
		self.fileArray.insert(index, line)
		
		# Adjust all subsequent line numbers
		for line in self.fileArray[index+1:]:
			line[0] += 1
		
		# Adjust all line numbers in the subModel array too, if we inserted the line before their indices
		# self.subModelArray = {"filename": [startline, endline]}
		for line in self.subModelArray.values():
			if line[0] >= index:
				line[0] += 1
			if line[1] >= index:
				line[1] += 1

	def saveFile(self, filename = None):
		
		# TODO: Need to better and fully handle file paths here
		if filename is None:
			filename = self.filename
		
		print "saving: ", self.path + filename
		
		# First, make a backup copy of the existing file
		shutil.move(self.path + filename, self.path + filename + ".bak")
		
		# Dump the current file array to the chosen file
		f = open(self.path + filename, 'w')
		for line in self.fileArray:
			f.write(' '.join(line[1:]) + '\n')
		f.close()

	def _loadFileArray(self):
		
		# TODO: Need to better define part file search path, to include the current
		# working directory, the directory of the main model, etc
		try:
			f = file(LDrawPath + "MODELS\\" + self.filename)
			self.path += "MODELS\\"
		except IOError:
			try:
				f = file(LDrawPath + "PARTS\\" + self.filename)
				self.path += "PARTS\\"
				if (self.filename[:2] == 's\\'):
					self.isPrimitive = True
			except IOError:
				f = file(LDrawPath + "P\\" + self.filename)
				self.path += "P\\"
				self.isPrimitive = True
		
		# copy the file into an internal array, for easier access
		i = 1
		for l in f:
			self.fileArray.append([i] + l.split())
			i += 1
		f.close()
		
		self.name = ' '.join(self.fileArray[0][2:])

	def _findSubModelsInFile(self):
		
		# Loop through the file array searching for sub model FILE declarations
		subModels = []  # subModels[0] = (filename, start line number)
		for i, l in enumerate(self.fileArray):
			if isValidFileLine(l):
				subModels.append((l[3], i))
		
		if len(subModels) < 1:
			return  # No subModels in file - we're done
		
		# Fixup subModel array by calculating the ending line number from the file
		for i in range(0, len(subModels)-1):
			subModels[i] = (subModels[i][0], [subModels[i][1], subModels[i+1][1]])
		
		# Last subModel is special case: its ending line is end of file array
		subModels[-1] = (subModels[-1][0], [subModels[-1][1], len(self.fileArray)])
		
		# self.subModelArray = {"filename": [startline, endline]}
		self.subModelArray = dict(subModels)

	def writeLinesToDat(self, filename, start, end):
		
		path = os.getcwd() + '\DATs\\'
		if os.path.isfile(path + filename):
			return   # DAT already exists - nothing to do
		
		if not os.path.isdir(path):
			os.mkdir(path)   # Create DAT directory if needed
		
		print "Creating dat for: %s, line %d to %d" % (filename, start, end)
		f = open(path + filename, 'w')
		for line in self.fileArray[start:end]:
			f.write(' '.join(line[1:]) + '\n')
		f.close()
		
		return path + filename
	
	def splitStepDats(self, filename = None, start = 0, end = -1):
		
		if end == -1:
			end = len(self.fileArray)
		
		path = os.getcwd() + '\DATs\\'
		if not os.path.isdir(path):
			os.mkdir(path)   # Create DAT directory if needed
		
		if filename is None:
			filename = self.filename
		rawFilename = os.path.splitext(os.path.basename(filename))[0]
		
		stepList = []
		for line in self.fileArray[start:end]:
			if isValidStepLine(line):
				stepList.append(line[0] - 1)
		stepList.append(end)
		
		for i, stepIndex in enumerate(stepList[1:]):
			
			datFilename = path + rawFilename + '_step_%d' % (i+1) + '.dat'
			f = open(datFilename, 'w')
			for line in self.fileArray[start:stepIndex]:
				f.write(' '.join(line[1:]) + '\n')
			f.close()
	
	def createPov(self, datFile = None):
		
		path = os.getcwd() + '\POVs\\'
		if not os.path.isdir(path):
			os.mkdir(path)
		
		if datFile is None:
			datFile = self.path + self.filename
		
		rawFilename = os.path.splitext(os.path.basename(datFile))[0]
		povFile = path + rawFilename + ".pov"
		
		if not os.path.isfile(povFile):
			# Create a pov from the specified dat via l3p
			l3pCommand = l3p.getDefaultCommand()
			l3pCommand['inFile'] = datFile
			l3pCommand['outFile'] = povFile
			l3p.runCommand(l3pCommand)
		
		# Convert the generated pov into a nice png
		path = os.getcwd() + '\PNGs\\'
		if not os.path.isdir(path):
			os.mkdir(path)
		
		pngFile = path + rawFilename + ".png"
		
		if not os.path.isfile(pngFile):
			povray.fixPovFile(povFile, 256, 256)
			povCommand = povray.getDefaultCommand()
			povCommand['inFile'] = povFile
			povCommand['outFile'] = pngFile
			povCommand['width'] = 256
			povCommand['height'] = 256
			povCommand['alpha'] = False
			povray.runCommand(povCommand)
