import shutil  # for file copy / rename
import os

def listToCSVStr(l):
	s = ''
	for i in l:
		s += str(i) + ','
	return s[:-1]
	
def boolToCommand(command, bool):
	if bool:
		return command
	return ''
	
defaultPOVCommands = {
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
	
def fixOrthographicCamera(filename):
	original = file(filename, 'r')
	copy = file(filename + '.tmp', 'w')
	
	for line in original:
		if line == '\t//orthographic\n':
			continue
		
		copy.write(line)		
		if line == 'camera {\n':
			copy.write('\torthographic\n')
	
	original.close()
	copy.close()
	shutil.move(filename + '.tmp', filename)
	