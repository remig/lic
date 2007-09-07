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
	
povCommands = {
	'inFile' : None,
	'outFile' : ['+O', str],
	
	'output type' : ['+F', str],
	'width' : ['+W', str],  # int - image width in pixels
	'height' : ['+H', str],   # int - image height in pixels
	
	'render' : ['', lambda b: boolToCommand('/RENDER', b)], # Boolean
	'no restore' : ['', lambda b: boolToCommand('/NR', b)],    # Boolean
	
	'display' : ['Display=', str],   # Boolean
	'verbose' : ['Verbose=', str],   # Boolean
}

path = r'C:\Program Files\POV-Ray\bin'
	
# d: {'camera position' : [20,-45,0], 'inputFile' : 'hello.dat'}
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
	#return (povray, args, os.spawnv(os.P_WAIT, povray, args))
	return (l3pApp, args)
	
