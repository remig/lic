import os

def listToCSVStr(l):
	s = ''
	for i in l:
		s += str(i) + ','
	return s[:-1]
	
l3pCommands = {
	'camera position' : ['-cg', listToCSVStr],  # [lat 20, long -45, r 0]
	'color' : ['-c', str],  # LDraw Color code
	'light' : ['-lg', listToCSVStr],  # [lat 45, long -45, r 0]
	'seam width' : ['-sw', str],
	'inputFile' : ''
}

class l3p:
	
	def __init__(self, LDrawPath = r'C:\LDraw', l3pPath = r'C:\LDraw\apps\l3p'):
		os.environ['LDRAWDIR'] = LDrawPath
		self.path = l3pPath
	
	def runCommand(self, d):
		l3pApp = self.path + '\\l3p.exe'
		args = []
		for command, value in d.items():
			args.append(l3pCommands[command][0] + l3pCommands[command][1](value)) 
		#os.spawnl(os.P_WAIT, l3pApp, l3pApp, d['inputFile'])
		return args
