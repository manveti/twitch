import Tkinter
import Tix
import ttk
import tkMessageBox
import tkSimpleDialog


TYPE_STRING = 0
TYPE_BOOL = 1
TYPE_INT = 2
TYPE_FLOAT = 3
TYPE_LIST = 4


class ClosableNotebook(ttk.Notebook):
    _initialized = False

    def __init__(self, *args, **kwargs):
	if (not self._initialized):
	    self.initImages()
	kwargs['style'] = "ClosableNotebook"
	ttk.Notebook.__init__(self, *args, **kwargs)
	self._active = None
	self.bind("<ButtonPress-1>", self.closePressed, True)
	self.bind("<ButtonRelease-1>", self.closeReleased)

    def initImages(self):
	self.images = (
		Tkinter.PhotoImage("img_cn_close", data='''
				R0lGODlhCAAIAMIBAAAAADs7O4+Pj9nZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
				d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
				5kEJADs='''),
		Tkinter.PhotoImage("img_cn_close_active", data='''
				R0lGODlhCAAIAMIEAAAAAP/SAP/bNNnZ2cbGxsbGxsbGxsbGxiH5BAEKAAQALAAA
				AAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU5kEJADs='''),
		Tkinter.PhotoImage("img_cn_close_pressed", data='''
				R0lGODlhCAAIAMIEAAAAAOUqKv9mZtnZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
				d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
				5kEJADs='''))
	style = ttk.Style()
	style.element_create("close", "image", "img_cn_close",
				    ("active", "pressed", "!disabled", "img_cn_close_pressed"),
				    ("active", "!disabled", "img_cn_close_active"), border=8, sticky="")
	style.layout("ClosableNotebook", [("ClosableNotebook.client", {'sticky': "nswe"})])
	focusSpec = {'side': "top",
		    'sticky': "nswe",
		    'children': [
			("ClosableNotebook.label", {'side': "left", 'sticky': ""}),
			("ClosableNotebook.close", {'side': "left", 'sticky': ""})
		    ]}
	paddingSpec = {'side': "top",
			'sticky': "nswe",
			'children': [("ClosableNotebook.focus", focusSpec)]}
	tabSpec = {'sticky': "nswe", 'children': [("ClosableNotebook.padding", paddingSpec)]}
	style.layout("ClosableNotebook.Tab", [("ClosableNotebook.tab", tabSpec)])

    def closePressed(self, event):
	element = self.identify(event.x, event.y)
	if ((not element) or ("close" not in element)):
	    return
	idx = self.index("@%d,%d" % (event.x, event.y))
	self.state(["pressed"])
	self._active = idx

    def closeReleased(self, event):
	if (not self.instate(["pressed"])):
	    return
	self.state(["!pressed"])
	active = self._active
	self._active = None

	element = self.identify(event.x, event.y)
	if ((not element) or ("close" not in element)):
	    return
	idx = self.index("@%d,%d" % (event.x, event.y))
	if (active != idx):
	    return
	self.forget(idx)

    def forget(self, idx):
	if (self.onClose(idx)):
	    return
	ttk.Notebook.forget(self, idx)

    def onClose(self, idx):
	pass

class _QueryList(tkSimpleDialog._QueryDialog):
    def __init__(self, title, prompt, values, *args, **kwargs):
	self.values = values
	self.roState = "normal"
	if (kwargs.has_key('readonly')):
	    if (kwargs['readonly']):
		self.roState = "readonly"
	    del kwargs['readonly']
	self.entryVar = Tkinter.StringVar()
	tkSimpleDialog._QueryDialog.__init__(self, title, prompt, *args, **kwargs)

    def body(self, master):
	w = Tkinter.Label(master, text=self.prompt, justify=Tkinter.LEFT)
	w.grid(row=0, padx=5, sticky=Tkinter.W)
	self.entry = ttk.Combobox(master, textvariable=self.entryVar, values=self.values, state=self.roState)
	self.entry.grid(row=1, padx=5, sticky=(Tkinter.W, Tkinter.E))
	if (self.initialvalue is not None):
	    self.entryVar.set(self.initialvalue)
	return self.entry

    def getresult(self):
	return self.entryVar.get()

def asklist(title, prompt, values, **kwargs):
    d = _QueryList(title, prompt, values, **kwargs)
    return d.result

class _QueryCompound(tkSimpleDialog.Dialog):
    def __init__(self, title, prompts, parent=None):
	if (not parent):
	    parent = Tkinter._default_root
	self.prompts = prompts
	tkSimpleDialog.Dialog.__init__(self, parent, title)

    def body(self, master):
	self.entries = []
	for i in xrange(len(self.prompts)):
	    p = self.prompts[i]
	    if ((not p.has_key('prompt')) or (not p.has_key('type'))):
		continue
	    w = Tkinter.Label(master, text=p['prompt'], justify=Tkinter.LEFT)
	    w.grid(row=i, padx=5, sticky=Tkinter.W)
	    cast = lambda v: v
	    if (p['type'] == TYPE_STRING):
		entryVar = Tkinter.StringVar()
		entry = Tkinter.Entry(master, textvariable=entryVar)
	    elif (p['type'] == TYPE_BOOL):
		entryVar = Tkinter.IntVar()
		entry = Tkinter.Checkbutton(master, variable=entryVar, anchor=Tkinter.W)
		cast = bool
	    elif (p['type'] == TYPE_INT):
		entryVar = Tkinter.IntVar()
		kwargs = {}
		if (p.has_key('minvalue')):
		    kwargs['min'] = p['minvalue']
		if (p.has_key('maxvalue')):
		    kwargs['max'] = p['maxvalue']
		if (p.has_key('step')):
		    kwargs['step'] = p['step']
		entry = Tix.Control(master, variable=entryVar, selectmode="immediate", integer=True, **kwargs)
	    elif (p['type'] == TYPE_FLOAT):
		entryVar = Tkinter.DoubleVar()
		kwargs = {}
		if (p.has_key('minvalue')):
		    kwargs['min'] = p['minvalue']
		if (p.has_key('maxvalue')):
		    kwargs['max'] = p['maxvalue']
		if (p.has_key('step')):
		    kwargs['step'] = p['step']
		entry = Tix.Control(master, variable=entryVar, selectmode="immediate", **kwargs)
	    elif (p['type'] == TYPE_LIST):
		entryVar = Tkinter.StringVar()
		kwargs = {'values': p.get('values', [])}
		if (p.get('readonly')):
		    kwargs['state'] = "readonly"
		entry = ttk.Combobox(master, textvariable=entryVar, **kwargs)
	    else:
		continue
	    entry.grid(row=i, column=1, padx=5, pady=3, sticky=(Tkinter.W, Tkinter.E))
	    if (p.get('initialvalue') is not None):
		entryVar.set(p['initialvalue'])
	    self.entries.append((entry, entryVar, cast))
	if (self.entries):
	    return self.entries[0][0]

    def validate(self):
	result = []
	for (entry, entryVar, cast) in self.entries:
	    try:
		res = cast(entryVar.get())
	    except ValueError:
		tkMessageBox.showwarning("Illegal value", "Not a valid value. Please try again.", parent=self)
		return 0
	    result.append(res)
	self.result = tuple(result)
	return 1

def askcompound(title, prompts, **kwargs):
    d = _QueryCompound(title, prompts, **kwargs)
    return d.result
