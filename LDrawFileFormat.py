import shutil  # for file copy / rename

LDrawPath = "C:\\LDrawParts\\"

Comment = '0'
PartCommand = '1'
LineCommand = '2'
TriangleCommand = '3'
QuadCommand = '4'
ConditionalLineCommand = '5'

StepMetaCommand = 'STEP'
FileMetaCommand = 'FILE'
ClearMetaCommand = 'CLEAR'
PauseMetaCommand = 'PAUSE'
SaveMetaCommand = 'SAVE'
GhostMetaCommand = 'GHOST'
BufferMetaCommand = 'BUFEXCHG'
BFCCommand = 'BFC'

BufferStore = 'STORE'
BufferRetrieve = 'RETRIEVE'

LPub = 'LPUB'
PLI = 'PLI'
BEGIN = 'BEGIN'
END = 'END'
IGN = 'IGN'
	
def LDToOGLMatrix(matrix):
	m = [float(x) for x in matrix]
	return [m[3], m[6], m[9], 0.0, m[4], m[7], m[10], 0.0, m[5], m[8], m[11], 0.0, m[0], m[1], m[2], 1.0]

def isValidTriangleLine(line):
	return ((len(line) == 12) and (line[1] == TriangleCommand))

def lineToTriangle(line):
	d = {}
	d['color'] = float(line[2])
	d['points'] = [float(x) for x in line[3:]]
	return d

def isValidQuadLine(line):
	return ((len(line) == 15) and (line[1] == QuadCommand))

def lineToQuad(line):
	d = {}
	d['color'] = float(line[2])
	d['points'] = [float(x) for x in line[3:]]
	return d

def isValidFileLine(line):
	return ((len(line) > 2) and (line[1] == Comment) and (line[2] == FileMetaCommand))

def isValidStepLine(line):
	return ((len(line) > 2) and (line[1] == Comment) and (line[2] == StepMetaCommand))

def isValidPartLine(line):
	return ((len(line) > 15) and (line[1] == PartCommand))

def lineToPart(line):
	d = {}
	d['filename'] = line[15]
	d['color'] = float(line[2])
	d['matrix'] = LDToOGLMatrix(line[3:15])
	d['ghost'] = False
	return d

def isValidGhostLine(line):
	return ((len(line) > 17) and (line[1] == Comment) and (line[2] == GhostMetaCommand) and (line[3] == PartCommand))

def lineToGhostPart(line):
	d = lineToPart(line[2:])
	d['ghost'] = True
	return d

def isValidBufferLine(line):
	return ((len(line) > 4) and (line[1] == Comment) and (line[2] == BufferMetaCommand))

def lineToBuffer(line):
	return {'buffer': line[3], 'state': line[4]}

def isValidPLIIGNLine(line):
	return ((len(line) == 6) and (line[1] == Comment) and (line[2] == LPub) and (line[3] == PLI) and (line[4] == BEGIN) and (line[5] == IGN))

def isValidPLIEndLine(line):
	return ((len(line) == 5) and (line[1] == Comment) and (line[2] == LPub) and (line[3] == PLI) and (line[4] == END))

def isValidBFCLine(line):
	# TODO: implement all BFC options
	return ((len(line) > 3) and (line[1] == Comment) and (line[2] == BFCCommand))

def lineToBFC(line):
	# TODO: implement all BFC options
	return {'command': line[3]}

class LDrawFile():
	def __init__(self, filename):
		#print "Creating file: ", filename
		self.filename = filename  # filename, like 3057.dat
		self.name = ""            # coloquial name, like 2 x 2 brick
		self.path = LDrawPath     # path where filename was found
		self.isPrimitive = False  # Anything in the 'P' directory
		
		self.fileArray = []
		self.subModelsInFile = {}
		
		self._loadFileArray()
		self._findSubModelsInFile()

	def saveFile(self, filename = None):
		if (filename is None):
			filename = self.filename
			
		print "saving: ", self.path + filename
		
		# First, make a backup copy of the existing file
		shutil.move(self.path + filename, self.path + filename + ".bak")
		
		f = open(self.path + filename, 'w')
		for line in self.fileArray:
			f.write(' '.join(line[1:]) + '\n')
		f.close()

	def _loadFileArray(self):
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
		
		# Loop through the file array searching for sub model declarations
		# subModels[0] = (filename, start line number)
		
		subModels = []
		for i in range(0, len(self.fileArray)):
			l = self.fileArray[i]
			if (isValidFileLine(l)):
				subModels.append((l[3], i))
		
		if (len(subModels) < 1):
			return  # No subModels in file - we're done
		
		# Fixup subModel array by calculating the ending line number from the file
		for i in range(0, len(subModels)-1):
			subModels[i] = (subModels[i][0], [subModels[i][1], subModels[i+1][1]])
		
		# Last subModel is special case: its ending line is end of file array
		subModels[-1] = (subModels[-1][0], [subModels[-1][1], len(self.fileArray)])
		
		# self.subModelsInFile = {"filename": [startline, endline]}
		self.subModelsInFile = dict(subModels)
