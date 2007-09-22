import os      # for process creation

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
	
# camera = [(x, 20), (y, 45), (y, -90)] - needs to be reversed before calling
def fixPovFile(filename, imgWidth, imgHeight, camera):

	tmpFilename = filename + '.tmp'
	licHeader = "// Lic: Processed lights, camera and rotation\n"
	originalFile = open(filename, 'r')
	
	# Check if we've already processed this pov, abort if we have
	if originalFile.readline() == licHeader:
		originalFile.close()
		return

	lastObjectLine = ''
	inCamera = inLight = False
	copyFile = open(tmpFilename, 'w')
	copyFile.write(licHeader)

	for line in originalFile:
		
		if line.startswith('object { '):
			lastObjectLine = line
		
		elif line == 'light_source {\n':
			inLight = True
		
		elif line == '}\n' and inLight:
			inLight = False
			copyFile.write('\tshadowless\n')
		
		elif line == 'camera {\n':
			inCamera = True
			copyFile.write(line)
			copyFile.write('\torthographic\n')
			copyFile.write('\tlocation <0, 0, -1000>\n')
			copyFile.write('\tsky      -y\n')
			copyFile.write('\tright    -%d * x\n' % (imgWidth))
			copyFile.write('\tup        %d * y\n' % (imgHeight))
			copyFile.write('\tlook_at   <0, 0, 0>\n')
			copyFile.write('\trotate    <0, 1e-5, 0>\n')
		
		elif line == '}\n' and inCamera:
			inCamera = False
		
		if not inCamera:
			copyFile.write(line)
	
	originalFile.close()
	copyFile.close()
	
	# Need a second pass to fixup last object in file - could only determine last object on first pass, not fix it
	originalFile = open(tmpFilename, 'r')
	copyFile = open(filename, 'w')
	
	for line in originalFile:
		
		if line != lastObjectLine:
			copyFile.write(line)
		else:
			# Insert the main object line...
			split = lastObjectLine.partition('#if')
			copyFile.write(split[0] + '\n')
			
			# ... with proper rotations inserted...
			for axis, amount in camera:
				if axis == 'x':
					copyFile.write('\trotate <%f, 0, 0>\n' % amount)
				elif axis == 'y':
					copyFile.write('\trotate <0, %f, 0>\n' % amount)
				elif axis == 'z':				
					copyFile.write('\trotate <0, 0, %f>\n' % amount)
			
			# ... then the rest of the original object line
			copyFile.write(''.join(split[1:]))
	
	originalFile.close()
	copyFile.close()
	os.remove(tmpFilename)
