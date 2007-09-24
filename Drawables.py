import cairo

class Point():
	def __init__(self, x = 0, y = 0):
		self.x = x
		self.y = y

	def __repr__(self):
		return "Point(%d, %d)" % (self.x, self.y)

	def __getitem(self, key):
		if key == 1:
			return self.x
		if key == 2:
			return self.y
		raise IndexError, "index %d out of range" % key

	def __eq__(self, item):
		if (self.x == item[0]) and (self.y == item[1]):
			return True
		return False

	def moveBy(self, x, y):
		self.x += x
		self.y += y

class Point3D():
	def __init__(self, x = 0, y = 0, z = 0):
		self.x = x
		self.y = y
		self.z = z

	def __repr__(self):
		return "Point3D(%d, %d, %d)" % (self.x, self.y, self.z)

	def __getitem(self, key):
		if key == 1:
			return self.x
		if key == 2:
			return self.y
		if key == 3:
			return self.z
		raise IndexError, "index %d out of range" % key

	def __eq__(self, item):
		if (self.x == item[0]) and (self.y == item[1]) and (self.z == item[2]):
			return True
		return False

	def moveBy(self, x, y, z):
		self.x += x
		self.y += y
		self.z += z

class Font():
	def __init__(self, size, face = "Arial", color = [0, 0, 0], bold = False, italic = False):
		self.size = size
		self.face = face
		self.color = color
		self.bold = bold
		self.italic = italic

	def passToCairo(self, context):
		""" 
		Set the specified cairo context's current font info to the info stored in this Font. 
		This overwrites any current cairo font settings - caller is responsible for caching, if needed.
		"""
		
		if self.bold:
			bold = cairo.FONT_WEIGHT_BOLD
		else:
			bold = cairo.FONT_WEIGHT_NORMAL
		
		if self.italic:
			italic = cairo.FONT_SLANT_ITALIC
		else:
			italic = cairo.FONT_SLANT_NORMAL
			
		context.select_font_face(self.face, italic, bold)
		context.set_font_size(self.size)
		context.set_source_rgb(*self.color)
	
class Line():
	"""
	Drawing properties for any given line an instruction book.
	"""

	# TODO: Define all members and their units in this class
	def __init__(self, red = 0, green = 0, blue = 0, thickness = 0, dash = 0):
		self.color = [red, green, blue]  # [red, green, blue], 0.0 - 1.0
		self.thickness = thickness
		self.dash = dash

class Fill():
	# TODO: Define all members and their units in this class
	def __init__(self):
		self.color = [0.0, 0.0, 0.0]  # [red, green, blue], 0.0 - 1.0
		self.pattern = 0
		self.image = 0
	
class Box():
	"""
	Represents a border and fill drawn around a PLI / CSI / page,
	and the position and size info needed to draw the border.
	"""
	
	def __init__(self, x = -1, y = -1, width = -1, height = -1, box = None):
		self.line = Line(0, 0, 0)
		self.fill = Fill()
		
		# TODO: Convert all of these to relative values (from 0..1, % of overall width | height)
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		
		self.cornerRadius = 0 # Radius for rounded corners. 0 = square
		self.internalGap = 10  # Distance from inside edge of border to outside edge of contents
		
		if box:
			self.clone(box)
	
	def clone(self, box):
		self.x = box.x
		self.y = box.y
		self.width = box.width
		self.height = box.height
	
	def __repr__(self):
		return "Box(x: %d, y: %d, w: %d, h: %d)" % (self.x, self.y, self.width, self.height)
	
	def draw(self, context):
		context.set_source_rgb(*self.line.color)
		context.rectangle(self.x, self.y, self.width, self.height)
		context.stroke()

	def drawAsSelection(self, context):
		context.set_line_width(2.0)
		context.rectangle(self.x - 0.5, self.y - 0.5, self.width + 1, self.height + 1)
		context.set_source_rgba(0, 0, 0, 0.75)
		context.stroke_preserve()
		context.set_source_rgb(1.0, 1.0, 1.0)
		context.set_dash([5, 5])
		context.stroke()
	
	def growBy(self, gap):
		self.x -= gap
		self.y -= gap
		self.width += 2 * gap
		self.height += 2 * gap
	
	def growByXY(self, x, y):
		if x < self.x:
			self.width += self.x - x
			self.x = x
		elif x > self.x + self.width:
			self.width = x - self.x
		
		if y < self.y:
			self.height += self.y - y
			self.y = y
		elif y > self.y + self.height:
			self.height = y - self.y
	
	def growByPoint(self, point):
		self.growByXY(point.x, point.y)
	
	def __add__(self, b):
		c = Box(self.x, self.y, self.width, self.height)
		c.growByXY(b.x, b.y)
		c.growByXY(b.x + b.width, b.y)
		c.growByXY(b.x, b.y + b.height)
		c.growByXY(b.x + b.width, b.y + b.height)
		return c
	
	def ptInBox(self, x, y):
		return (self.x < x) and (self.x + self.width > x) and (self.y < y) and (self.y + self.height > y)
	
	def moveBy(self, x, y):
		self.x += x
		self.y += y
