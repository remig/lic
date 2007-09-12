import shutil  # for file copy / rename
import os
import re

def listToCSVStr(l):
	s = ''
	for i in l:
		s += str(i) + ','
	return s[:-1]
	
def boolToCommand(command, bool):
	if bool:
		return command
	return ''
	
defaultPOVCommand = {
	'output type': 'N',
	'width': 512,
	'height': 512,
	'render': False,
	'no restore': True,
	'jitter' : False,
	'anti-alias' : True,
	'quality' : 3,
	'output type' : 'N',
	'exit' : True,
}

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

path = r'C:\Program Files\POV-Ray\bin'
	
def runCommand(d):
	povray = path + '\\pvengine.exe'
	args = [povray]
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
	
def removeCamera(filename):	
	original = file(filename, 'r')
	copy = file(filename + '.tmp', 'w')
	
	found = False
	for line in original:
		if line == 'camera {\n':
			copy.write('#if (0)\n')
			found = True
		copy.write(line)		
	
	if found:
		copy.write('#end\n')
	
	copy.close()
	original.close()
	shutil.move(filename + '.tmp', filename)

def fixPovFile(filename, imgWidth, imgHeight):

	originalFile = file(filename, 'r')
	copyFile = file(filename + '.tmp', 'w')
	inCamera = inLight = False

	for line in originalFile:

		if line == 'light_source {\n':
			inLight = True
			copyFile.write(line)
			continue

		if line == '}\n' and inLight:
			inLight = False
			copyFile.write('\tshadowless\n')
			copyFile.write(line)
			continue

		if line == 'camera {\n':
			inCamera = True
			copyFile.write(line)
			copyFile.write('\torthographic\n')
			continue

 		if line == '}\n' and inCamera:
			inCamera = False
			copyFile.write(line)
			continue

		if not inCamera:
			copyFile.write(line)
			continue

		# If we're here, we're inside a camera declaration - only check for lines we care about and ignore the rest
		match = re.match(r'\tlocation vaxis_rotate\(<([-.\d]+),([-.\d]+),([-.\d]+)>', line)
		if match:
			if len(match.groups()) == 3:
				cx, cy, cz = [float(x) for x in match.groups()]
				copyFile.write('\tlocation <%f, %f, %f>\n' % (cx, cy, cz))
				copyFile.write('\tsky      -y\n')
				copyFile.write('\tright    -%d * x\n' % (imgWidth))
				copyFile.write('\tup        %d * y\n' % (imgHeight))
			else:
				print "Error: Badly formed location vaxis line in pov file: %s" % (filename)

		if line.startswith('\tlook_at') or line.startswith('\trotate'):
			copyFile.write(line)

	originalFile.close()
	copyFile.close()
	shutil.move(filename + '.tmp', filename)
	
