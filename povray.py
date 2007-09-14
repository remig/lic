import shutil  # for file copy / rename
import os      # for process creation
import re      # for pov file parsing

def listToCSVStr(l):
	s = ''
	for i in l:
		s += str(i) + ','
	return s[:-1]
	
def boolToCommand(command, bool):
	if bool:
		return command
	return ''
	
def getDefaultCommand():
	return dict({
		'output type': 'N',
		'width': 512,
		'height': 512,
		'render': False,
		'no restore': True,
		'jitter' : False,
		'anti-alias' : True,
		'alpha' : True,
		'quality' : 3,
		'output type' : 'N',
		'exit' : True,
	})

povCommands = {
	'inFile' : ['+I', str],
	'outFile' : ['+O', str],
	
	'output type' : ['+F', str],  # Either N (png) or S (system - BMP on win32)
	'width' : ['+W', str],  # int - image width in pixels
	'height' : ['+H', str],   # int - image height in pixels
	
	'render' : ['', lambda b: boolToCommand('/RENDER', b)], # Boolean - Render the specified scene (useless with inFile specified)
	'no restore' : ['', lambda b: boolToCommand('/NR', b)], # Boolean - Do not open any previous files 
	'exit' : ['', lambda b: boolToCommand('/EXIT', b)],     # Boolean - Close this pov-ray instance after rendering
	
	'display' : ['Display=', str],      # Boolean - Turns graphic display preview on/off
	'verbose' : ['Verbose=', str],      # Boolean - Turns verbose messages on/off
	'alpha'   : ['Output_Alpha=', str], # Boolean - Turns alpha channel on/off
	'anti-alias' : ['Antialias=', str], # Boolean - Turns anti-aliasing on/off
	'jitter'  : ['Jitter=', str],        # Boolean - Turns aa-jitter on/off

	'quality' : ['+Q', str], # Render quality - integer from (0 <= n <= 11)
	
	'include' : ['+HI', str], # Include any extra files - specify full filename
}


def runCommand(d):

	path = r'C:\Program Files\POV-Ray\bin'
	if not os.path.isdir(path):
		path = r'C:\Program Files\POV-Ray for Windows v3.6\bin'
	if not os.path.isdir(path):
		# TODO: provide user a way to specify Pov-Ray path
		print "Error: Could not find Pov-Ray."
		return

	povray = path + '\\pvengine.exe'

	args = ['"' + povray + '"']
	for key, value in d.items():
		command = povCommands[key]
		if command:
			args.append(command[0] + command[1](value))
		else:
			if key == 'inFile':
				args.insert(1, value)  # Ensure input file is first command (after l3p.exe itself)
			else:
				args.append(value)
	return (povray, args, os.spawnv(os.P_WAIT, povray, args))
	#return (povray, args)
	
def fixPovFile(filename, imgWidth, imgHeight):

	licHeader = "// Lic: Processed lights and camera\n"	
	originalFile = open(filename, 'r')
	
	# Check if we've already processed this pov, abort if we have
	if originalFile.readline() == licHeader:
		originalFile.close()
		return

	# Unfortunately, we need to know where the part's center is, but that info
	# is at the end of the file.  Need to read entire file looking for that...
	lookAtVector = ''
	for line in originalFile:
		if line.startswith('// Center: <'):
			lookAtVector = line[11:].strip()
	originalFile.close()
	
	if lookAtVector == '':
		print "Error: No Center line in POV File: %s" % (filename)
		return
	
	inCamera = inLight = False
	originalFile = open(filename, 'r')
	copyFile = open(filename + '.tmp', 'w')
	copyFile.write(licHeader)
	
	for line in originalFile:
		
		if line == 'light_source {\n':
			inLight = True
		
		if line == '}\n' and inLight:
			inLight = False
			copyFile.write('\tshadowless\n')
		
		if line == 'camera {\n':
			inCamera = True
			copyFile.write(line)
			copyFile.write('\torthographic\n')
			copyFile.write('\tlocation (<-28, -14.5, -28> * 1000) + ' + lookAtVector + '\n')
			copyFile.write('\tsky      -y\n')
			copyFile.write('\tright    -%d * x\n' % (imgWidth))
			copyFile.write('\tup        %d * y\n' % (imgHeight))
			copyFile.write( '\tlook_at   ' + lookAtVector + '\n')
			copyFile.write('\trotate    <0, 1e-5, 0>\n')
		
		if line == '}\n' and inCamera:
			inCamera = False
		
		if not inCamera:
			copyFile.write(line)
	
	originalFile.close()
	copyFile.close()
	shutil.move(filename + '.tmp', filename)
	
