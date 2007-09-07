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
	
l3pCommands = {
	'inFile' : None,
	'outFile' : None,
	
	'camera position' : ['-cg', listToCSVStr],  # [20, -45, 0] = (lat, long, r)
	'background' : ['-b', listToCSVStr],   # [r, g, b] 0 <= r <= 1
	'light' : ['-lg', listToCSVStr],  # [45, -45, 0] = (lat, long, r)
		
	'seam width' : ['-sw', str],  # int
	'quality' : ['q', str],  # int
	'color' : ['-c', str],  # LDraw Color code
		
	'overwrite' : ['', lambda b: boolToCommand('-o', b)], # Boolean
	'bumps' : ['', lambda b: boolToCommand('-bu', b)],    # Boolean
	'LGEO' : ['', lambda b: boolToCommand('-lgeo', b)],   # Boolean
}

path = r'C:\LDraw\apps\l3p'
os.environ['LDRAWDIR'] = r'C:\LDraw'
	
# d: {'camera position' : [20,-45,0], 'inputFile' : 'hello.dat'}
def runCommand(d):
	l3pApp = path + '\\l3p.exe'
	args = [l3pApp]
	for key, value in d.items():
		command = l3pCommands[key]
		if command:
			args.append(command[0] + command[1](value))
		else:
			if key == 'inFile':
				args.insert(1, value)  # Ensure input file is first command (after l3p.exe itself)
			else:
				args.append(value)
	return (l3pApp, args, os.spawnv(os.P_WAIT, l3pApp, args))
	#return (l3pApp, args)
	
