#!/usr/bin/env python

import base64
import cPickle
import os.path
import shelve
import threading
import Tkinter
import tkColorChooser
import tkFileDialog
import tkFont
import tkMessageBox
import tkSimpleDialog
import time
import Tix
import ttk

import Tkx
import Twitch


DEFAULT_PREFERENCES = {
    'brightnessThreshold':	80,
    'latinThreshold':		1,
    'maxInputHistory':		100,
    'maxScratchWidth':		50,
    'showTimestamps':		True,
    'timestampFormat':		"%H:%M",
    'userPaneVisible':		True,
    'wrapChatText':		True,
}

CHAT_PREFERENCES = set(['chatColor', 'chatBgColor', 'chatFontFamily', 'chatFontSize', 'chatFontBold',
			'chatFontItalic', 'timestampColor', 'timestampBgColor', 'brightnessThreshold',
			'showTimestamps', 'timestampFormat', 'latinThreshold'])

TIMESTAMP_FORMATS = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p",
		    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:S", "%m/%d/%y %I:%M %p", "%X", "%c"]

EVENT_MSG = 0
EVENT_JOIN = 1
EVENT_LEAVE = 2

ACTION_PREFIX = "%cACTION " % 1
ACTION_SUFFIX = "%c" % 1

CHAT_POPULATE_INTERVAL = 0.1


def getColorBrightness(c):
#####
##
    #return int(round((0.299 * c[0] * c[0] + 0.587 * c[1] * c[1] + 0.114 * c[2] * c[2]) ** 0.5))
    return int(round(0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]))
##
#####

def hexToRgb(c):
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))

def rgbToHex(c):
    return "#%02x%02x%02x" % c


class ChatCallbackFunctions(Twitch.ChatCallbacks):
    def __init__(self, master):
	self.master = master

    def userJoined(self, channel, user):
	if (not self.master.channels.has_key(channel)):
	    return
	if (self.master.channels[channel]['users'].has_key(user)):
	    return
	self.master.channels[channel]['userLock'].acquire()
	self.master.channels[channel]['users'][user] = {'display': user}
	self.master.channels[channel]['userLock'].release()
	self.master.channels[channel]['log'].append((EVENT_JOIN, time.time(), user))
	if (channel != self.master.curChannel):
	    return
	userSort = self.master.getSortedUsers(channel)
	idx = userSort.index(user)
	self.master.userListLock.acquire()
	self.master.userList.insert(idx, user)
	self.master.userListLock.release()

    def usersJoined(self, channel, users):
	if (not self.master.channels.has_key(channel)):
	    return
	if (len(users) < len(self.master.channels[channel]['users']) / 2):
	    return Twitch.ChatCallbacks.usersJoined(self, channel, users)
	self.master.channels[channel]['userLock'].acquire()
	for user in users:
	    self.master.channels[channel]['users'][user] = {'display': user}
	    self.master.channels[channel]['log'].append((EVENT_JOIN, time.time(), user))
	self.master.channels[channel]['userLock'].release()
	if (channel != self.master.curChannel):
	    return
	self.master.userListLock.acquire()
	self.master.userList.delete(0, Tkinter.END)
	for user in self.master.getSortedUsers(channel):
	    self.master.userList.insert(Tkinter.END, user)
	self.master.userListLock.release()

    def userLeft(self, channel, user):
	if (not self.master.channels.has_key(channel)):
	    return
	if (not self.master.channels[channel]['users'].has_key(user)):
	    return
	self.master.channels[channel]['log'].append((EVENT_LEAVE, time.time(), user))
	if (channel == self.master.curChannel):
	    userSort = self.master.getSortedUsers(channel)
	    idx = userSort.index(user)
	    self.master.userListLock.acquire()
	    self.master.userList.delete(idx)
	    self.master.userListLock.release()
	self.master.channels[channel]['userLock'].acquire()
	del self.master.channels[channel]['users'][user]
	self.master.channels[channel]['userLock'].release()

    def chatMessage(self, channel, user, msg, userDisplay=None, userColor=None, userBadges=set(), emotes=[]):
	if (not self.master.channels.has_key(channel)):
	    return
	updateUserList = False
	if (not self.master.channels[channel]['users'].has_key(user)):
	    self.master.channels[channel]['userLock'].acquire()
	    self.master.channels[channel]['users'][user] = {'display': user}
	    self.master.channels[channel]['userLock'].release()
	    updateUserList = True
	if (not userDisplay):
	    userDisplay = self.master.channels[channel]['users'][user].get('display')
	if (self.master.channels[channel]['users'][user]['display'] != userDisplay):
	    if ((channel == self.master.curChannel) and (not updateUserList)):
		self.master.userListLock.acquire()
		userSort = self.master.getSortedUsers(channel)
		idx = userSort.index(user)
		self.master.userList.delete(idx)
		self.master.userListLock.release()
	    self.master.channels[channel]['users'][user]['display'] = userDisplay
	    updateUserList = True
	if (not userColor):
	    userColor = self.master.channels[channel]['users'][user].get('color')
	self.master.channels[channel]['users'][user]['color'] = userColor
#####
##
	#update self.master.channels[channel]['users'][user] badges
##
#####
	ts = time.time()
	logLine = (EVENT_MSG, ts, user, msg, userDisplay, userColor, userBadges, emotes)
	self.master.channels[channel]['log'].append(logLine)
	if (channel != self.master.curChannel):
	    return
	if (updateUserList):
	    self.master.userListLock.acquire()
	    userSort = self.master.getSortedUsers(channel)
	    idx = userSort.index(user)
	    self.master.userList.insert(idx, self.master.channels[channel]['users'][user].get('display', user))
	    self.master.userListLock.release()
	if (userColor):
	    self.master.setupTag(channel, userColor)
	tsTags = []
	userTags = []
	msgTags = []
	if (userColor):
	    userTags.append(userColor)
	if (self.master.useTsTag):
	    tsTags.append("tsColor")
	if (self.master.useMsgTag):
	    msgTags.append("msgColor")
	if (self.master.useFontTag):
	    tsTags.append("msgFont")
	    userTags.append("msgFont")
	    msgTags.append("msgFont")
	tsTags = tuple(tsTags)
	userTags = tuple(userTags)
	msgTags = tuple(msgTags)
	self.master.chatBoxLock.acquire()
	oldPos = self.master.chatBox.yview()
	if (self.master.preferences.get('showTimestamps')):
	    tsFmt = self.master.getPreference('timestampFormat')
	    self.master.chatBox.insert(Tkinter.END, "%s " % time.strftime(tsFmt, time.localtime(ts)), tsTags)
#####
##
	#deal with badges
##
#####
	self.master.chatBox.insert(Tkinter.END, userDisplay, userTags)
#####
##
	#deal with emotes
	if ((msg.startswith(ACTION_PREFIX)) and (msg.endswith(ACTION_SUFFIX))):
	    msgTags = userTags
	    msg = " %s\n" % msg[len(ACTION_PREFIX):-len(ACTION_SUFFIX)]
	else:
	    msg = ": %s\n" % msg
	self.master.chatBox.insert(Tkinter.END, msg, msgTags)
##
#####
	if ((type(oldPos) != type(())) or (len(oldPos) != 2) or (oldPos[1] == 1)):
	    self.master.chatBox.see(Tkinter.END)
	self.master.chatBoxLock.release()


class MainGui(Tkinter.Frame):
    def __init__(self, master=None):
	Tkinter.Frame.__init__(self, master)

	self.loadPreferences()

	self.channels = {}
	self.channelOrder = []
	self.curChannel = None
	self.chat = None
	self.chatToPopulate = []
	self.chatPopulateThread = None
	self.chatTags = {}
	self.useTsTag = False
	self.useMsgTag = False
	self.useFontTag = False
	self.msgFont = None
	self.searchString = None
	self.lastSearchString = ""
	self.searchBackwards = False
	self.scratchMsgs = []
	self.inputHistory = []
	self.inputHistoryPos = 0
#####
##
	#stuff
##
#####
	self.prefsToSet = {}
	self.macrosMenus = []
	self.curMacro = ()

	self.chatBoxLock = threading.Lock()
	self.userListLock = threading.Lock()

	self.accountWin = None
	self.preferencesWin = None
	self.favoritesWin = None
	self.macrosWin = None

	self.master.title("ChatVeti")
	self.menuBar = Tkinter.Menu(self)
	master.config(menu=self.menuBar)

	ttk.Style().configure("TCombobox", fieldbackground="SystemWindow")
	ttk.Style().configure("Treeview", fieldbackground="SystemWindow")

	# file menu
	self.fileMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.fileMen.add_command(label="Open Channel...", command=self.openChannel)
	self.fileMen.add_command(label="Open Log...", command=self.openLog)
	self.fileMen.add_separator()
	self.fileMen.add_command(label="Save Log", command=self.saveLog)
	self.fileMen.add_command(label="Save Log As...", command=self.saveLogAs)
	self.fileMen.add_command(label="Export Log...", command=self.exportLog)
	self.fileMen.add_separator()
	self.fileMen.add_command(label="Close Channel", command=self.closeChannel)
	self.fileMen.add_command(label="Exit", command=self.interceptExit)
	self.menuBar.add_cascade(label="File", menu=self.fileMen)

	# config menu
	self.configMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.configTimestampVar = Tkinter.IntVar()
	self.configTimestampVar.set(int(self.getPreference('showTimestamps')))
	self.configMen.add_checkbutton(label="Chat Timestamps", variable=self.configTimestampVar, indicatoron=True,
					onvalue=1, offvalue=0, command=self.toggleChatTimestamps)
	self.configWrapVar = Tkinter.IntVar()
	self.configWrapVar.set(int(self.getPreference('wrapChatText')))
	self.configMen.add_checkbutton(label="Wrap Chat", variable=self.configWrapVar, indicatoron=True,
					onvalue=1, offvalue=0, command=self.toggleChatWrap)
	self.configUserVar = Tkinter.IntVar()
	self.configUserVar.set(int(self.getPreference('userPaneVisible')))
	self.configMen.add_checkbutton(label="User Pane", variable=self.configUserVar, indicatoron=True,
					onvalue=1, offvalue=0, command=self.toggleUserPane)
	self.configMen.add_separator()
	self.configMen.add_command(label="Account...", command=self.openAccountWin)
	self.configMen.add_command(label="Preferences...", command=self.openPreferencesWin)
	self.menuBar.add_cascade(label="Config", menu=self.configMen)

	# favorites menu
	self.favoritesMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.favoritesMen.add_command(label="Add Favorite", command=self.addFavorite)
	self.favoritesMen.add_command(label="Edit Favorites...", command=self.editFavorites)
	self.favoritesMen.add_separator()
	for channel in self.preferences.get('favorites', []):
	    self.favoritesMen.add_command(label=channel, command=lambda c=channel: self.doChannelOpen(c))
	self.menuBar.add_cascade(label="Favorites", menu=self.favoritesMen)

	# macros menu
	self.macrosMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.macrosMen.add_command(label="Edit Macros...", command=self.editMacros)
	self.macrosMen.add_separator()
	self.populateMacrosMenu(self.macrosMen, self.macrosMenus, self.preferences.get('macros', []))
	self.menuBar.add_cascade(label="Macros", menu=self.macrosMen)

	self.panes = Tkinter.PanedWindow(self, sashrelief=Tkinter.GROOVE)

	# chat pane
	self.chatPane = Tkinter.Frame(self.panes)
	self.channelTabs = Tkx.ClosableNotebook(self.chatPane, height=0)
	self.channelTabs.bind("<<NotebookTabChanged>>", self.channelTabChanged)
	self.channelTabs.onClose = self.channelTabClosed
	self.channelTabs.grid(row=0, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.S))
	self.userPaneToggle = Tkinter.Button(self.chatPane, text=">", command=self.toggleUserPane)
	self.userPaneToggle.grid(row=0, column=2, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatGrid = Tkinter.Frame(self.chatPane)
	kwargs = {}
	if (self.preferences.get('chatColor')):
	    kwargs['foreground'] = self.preferences.get('chatColor')
	if (self.preferences.get('chatBgColor')):
	    kwargs['background'] = self.preferences.get('chatBgColor')
	if (self.preferences.get('wrapChatText')):
	    kwargs['wrap'] = Tkinter.WORD
	else:
	    kwargs['wrap'] = Tkinter.NONE
	self.chatBox = Tkinter.Text(self.chatGrid, **kwargs)
	self.chatBox.bind("<Control-c>", self.copyChat)
	self.chatBox.bind("<Control-f>", self.startChatSearch)
	self.chatBox.bind("<Control-b>", self.startBackwardsChatSearch)
	self.chatBox.bind("<Key>", self.handleChatKey)
	self.chatBox.bind("<FocusOut>", self.stopChatSearch)
	self.chatBox.bind("<Button>", self.stopChatSearch)
	self.chatBox.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatVScroll = Tkinter.Scrollbar(self.chatGrid, command=self.chatBox.yview)
	self.chatVScroll.grid(row=0, column=1, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatHScroll = Tkinter.Scrollbar(self.chatGrid, orient=Tkinter.HORIZONTAL, command=self.chatBox.xview)
	self.chatHScroll.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	self.chatBox.configure(xscrollcommand=self.chatHScroll.set, yscrollcommand=self.chatVScroll.set)
	self.chatGrid.columnconfigure(0, weight=1)
	self.chatGrid.rowconfigure(0, weight=1)
	self.chatGrid.grid(row=1, column=0, columnspan=3, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.scratchBut = Tkinter.Menubutton(self.chatPane, text="Scratch", relief=Tkinter.RAISED)
	self.scratchMen = Tkinter.Menu(self.scratchBut, tearoff=False)
	self.scratchMen.add_command(label="Scratch Input", command=self.scratchInput)
	self.scratchMen.add_separator()
	self.scratchBut.config(menu=self.scratchMen)
	self.scratchBut.grid(row=2, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	kwargs = {}
	if (self.preferences.get('chatColor')):
	    kwargs['foreground'] = self.preferences.get('chatColor')
	if (self.preferences.get('chatBgColor')):
	    kwargs['background'] = self.preferences.get('chatBgColor')
	self.chatInputBox = Tkinter.Entry(self.chatPane, **kwargs)
	self.chatInputBox.bind("<Return>", self.submitChatInput)
	self.chatInputBox.bind("<Up>", self.inputUpHistory)
	self.chatInputBox.bind("<Down>", self.inputDownHistory)
	self.chatInputBox.grid(row=2, column=1, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
#####
##
	#?emotes menu?
	#?macro buttons?
##
#####
	self.chatPane.columnconfigure(1, weight=1)
	self.chatPane.rowconfigure(1, weight=1)
	self.panes.add(self.chatPane, stretch="always")

	# users pane
	self.userPane = Tkinter.Frame(self.panes)
	self.userGrid = Tkinter.Frame(self.userPane)
	kwargs = {'activestyle': "none"}
	if (self.preferences.get('userColor')):
	    kwargs['foreground'] = self.preferences.get('userColor')
	elif (self.preferences.get('chatColor')):
	    kwargs['foreground'] = self.preferences.get('chatColor')
	if (self.preferences.get('userBgColor')):
	    kwargs['background'] = self.preferences.get('userBgColor')
	elif (self.preferences.get('chatBgColor')):
	    kwargs['background'] = self.preferences.get('chatBgColor')
	self.userList = Tkinter.Listbox(self.userGrid, **kwargs)
	self.userList.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.userVScroll = Tkinter.Scrollbar(self.userGrid, command=self.userList.yview)
	self.userVScroll.grid(row=0, column=1, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	self.userHScroll = Tkinter.Scrollbar(self.userGrid, orient=Tkinter.HORIZONTAL, command=self.userList.xview)
	self.userHScroll.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	self.userList.configure(xscrollcommand=self.userHScroll.set, yscrollcommand=self.userVScroll.set)
	self.userGrid.columnconfigure(0, weight=1)
	self.userGrid.rowconfigure(0, weight=1)
	self.userGrid.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
#####
##
	#optional user admin area
##
#####
	self.userPane.columnconfigure(0, weight=1)
	self.userPane.rowconfigure(0, weight=1)
	if (self.preferences.get('userPaneVisible')):
	    self.panes.add(self.userPane, stretch="always")

	self.panes.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))

#####
##
	#(maybe) minimizable macro area
##
#####

	self.columnconfigure(0, weight=1)
	self.rowconfigure(0, weight=1)
	self.pack(fill="both", expand=True)

	# configure global text tags
	kwargs = {}
	if (self.preferences.get('timestampColor')):
	    kwargs['foreground'] = self.preferences.get('timestampColor')
	elif (self.preferences.get('chatColor')):
	    kwargs['foreground'] = self.preferences.get('chatColor')
	if (self.preferences.get('timestampBgColor')):
	    kwargs['background'] = self.preferences.get('timestampBgColor')
	elif (self.preferences.get('chatBgColor')):
	    kwargs['background'] = self.preferences.get('chatBgColor')
	if (kwargs):
	    self.chatBox.tag_configure("tsColor", **kwargs)
	    self.useTsTag = True
	kwargs = {}
	if (self.preferences.get('chatColor')):
	    kwargs['foreground'] = self.preferences.get('chatColor')
	if (self.preferences.get('chatBgColor')):
	    kwargs['background'] = self.preferences.get('chatBgColor')
	if (kwargs):
	    self.chatBox.tag_configure("msgColor", **kwargs)
	    self.useMsgTag = True
	kwargs = self.getFontArgs()
	if (kwargs):
	    self.msgFont = tkFont.Font(**kwargs)
	    self.chatBox.tag_configure("msgFont", font=self.msgFont)
	    self.useFontTag = True

	self.master.protocol("WM_DELETE_WINDOW", self.interceptExit)

    def loadPreferences(self):
	self.preferences = shelve.open(os.path.join(os.path.dirname(__file__), ".config"), protocol=1)

	for pref in DEFAULT_PREFERENCES.keys():
	    if (not self.preferences.has_key(pref)):
		self.preferences[pref] = DEFAULT_PREFERENCES[pref]

    def savePreferences(self):
	self.preferences.sync()

    def interceptExit(self):
#####
##
	#prevent exit and return if necessary
##
#####
	self.chatToPopulate = []
	if (self.chat):
	    if (self.chat.callbacks):
		self.chat.callbacks = Twitch.ChatCallbacks()
	    self.chat.disconnect()
	self.preferences.close()
	self.master.destroy()

    def openChannel(self):
	self.doChannelOpen(tkSimpleDialog.askstring("Channel", "Enter channel to join"))

    def openLog(self):
	path = tkFileDialog.askopenfilename(filetypes=[("All Files", "*"), ("Log Files", "*.log")])
	if (not path):
	    return
	f = None
	try:
	    try:
		f = open(path, "rb")
	    except IOError:
		tkMessageBox.showerror("Error", "Unable to open file.")
		return
	    channelName = f.readline().strip()
	    if (not channelName):
		tkMessageBox.showerror("Error", "Unable to load file.")
		return
	    try:
		log = cPickle.load(f)
	    except cPickle.PickleError:
		tkMessageBox.showerror("Error", "Unable to load file.")
		return
	finally:
	    if (f):
		f.close()
	if (not log):
	    tkMessageBox.showerror("Error", "Unable to load file.")
	    return
	channelDict = {'logPath': path, 'channelName': channelName, 'log': log, 'users': {}}
#####
##
	#channel=something to identify tab as a log of channel channelName from date log[0][1]
	channel = "%s_%s" % (channelName, time.strftime("%y%m%d_%H%M%S", time.localtime(log[0][1])))
	#verify channel is unique
	if (self.channels.has_key(channel)):
	    #raise channel tab
	    return
##
######
	self.channels[channel] = channelDict
	self.channelOrder.append(channel)
	self.channels[channel]['frame'] = Tkinter.Frame(self.channelTabs)
	self.channelTabs.add(self.channels[channel]['frame'], text=channel)
	self.channelTabs.select(len(self.channelOrder) - 1)
	self.curChannel = channel
	self.userListLock.acquire()
	self.userList.delete(0, Tkinter.END)
	self.userListLock.release()
	self.populateChat(log)

    def saveLog(self):
	if ((not self.curChannel) or (not self.channels.get(self.curChannel, {}).get('log'))):
	    return
	if (not self.channels[self.curChannel].get('logPath')):
	    return self.saveLogAs()
	channelName = self.channels[self.curChannel].get('channelName', self.curChannel)
	f = None
	try:
	    f = open(self.channels[self.curChannel]['logPath'], "wb")
	    f.write("%s\n" % channelName)
	    cPickle.dump(self.channels[self.curChannel]['log'], f)
	finally:
	    if (f):
		f.close()

    def saveLogAs(self):
	if ((not self.curChannel) or (not self.channels.get(self.curChannel, {}).get('log'))):
	    return
	startTime = time.localtime(self.channels[self.curChannel]['log'][0][1])
	channelName = self.channels[self.curChannel].get('channelName', self.curChannel)
	args = {
	    'filetypes': [("All Files", "*"), ("Log Files", "*.log")],
	    'initialfile': "%s_%s.log" % (channelName, time.strftime("%y%m%d_%H%M%S", startTime))
	}
	path = tkFileDialog.asksaveasfilename(**args)
	if (not path):
	    return
	self.channels[self.curChannel]['logPath'] = path
	self.saveLog()

    def exportLog(self):
	if ((not self.curChannel) or (not self.channels.get(self.curChannel, {}).get('log'))):
	    return
	startTime = time.localtime(self.channels[self.curChannel]['log'][0][1])
	channelName = self.channels[self.curChannel].get('channelName', self.curChannel)
	args = {
	    'filetypes': [("All Files", "*"), ("Text Files", "*.txt")],
	    'initialfile': "%s_%s.txt" % (channelName, time.strftime("%y%m%d_%H%M%S", startTime))
	}
	path = tkFileDialog.asksaveasfilename(**args)
	if (not path):
	    return
	f = None
	try:
	    f = open(path, "w")
	    for logLine in self.channels[self.curChannel]['log']:
		if (logLine[0] != EVENT_MSG):
		    continue
		(e, ts, user, msg, userDisplay, userColor, userBadges, emotes) = logLine
#####
##
		f.write("%s %s: %s\n" % (time.strftime("%H:%M:%S", time.localtime(ts)), userDisplay, msg))
##
######
	finally:
	    if (f):
		f.close()

    def closeChannel(self):
	if (not self.curChannel):
	    return
	try:
	    idx = self.channelOrder.index(self.curChannel)
	except ValueError:
	    return
	self.channelTabs.forget(idx)

    def toggleChatTimestamps(self):
	self.preferences['showTimestamps'] = not self.getPreference('showTimestamps')
	self.configTimestampVar.set(int(self.preferences['showTimestamps']))
	self.savePreferences()
	if (self.curChannel):
	    self.populateChat(self.channels[self.curChannel]['log'])

    def toggleChatWrap(self):
	self.preferences['wrapChatText'] = not self.getPreference('wrapChatText')
	self.configWrapVar.set(int(self.preferences['wrapChatText']))
	self.savePreferences()
	if (self.preferences['wrapChatText']):
	    wrap = Tkinter.WORD
	else:
	    wrap = Tkinter.NONE
	self.chatBox.config(wrap=wrap)

	if (self.curChannel):
	    self.populateChat(self.channels[self.curChannel]['log'])

    def toggleUserPane(self):
	w = self.master.winfo_width()
	h = self.master.winfo_height()
	x = self.master.winfo_x()
	y = self.master.winfo_y()
	if (self.preferences.get('userPaneVisible')):
	    self.panes.remove(self.userPane)
	    self.userPaneToggle.configure(text="<")
	    self.preferences['userPaneVisible'] = False
	    self.configUserVar.set(0)
	else:
	    self.panes.add(self.userPane, stretch="always")
	    self.userPaneToggle.configure(text=">")
	    self.preferences['userPaneVisible'] = True
	    self.configUserVar.set(1)
	self.master.geometry("%sx%s+%s+%s" % (w, h, x, y))
	self.savePreferences()

    def openAccountWin(self):
	if (not self.accountWin):
	    def closeAccountWin():
		self.accountWin.withdraw()
	    self.accountWin = Tkinter.Toplevel()
	    self.accountWin.protocol("WM_DELETE_WINDOW", closeAccountWin)
	    self.accountWin.title("Account")
#####
##
	    #login stuff:
	    #account name (read-only)
	    #permissions (for admin features, not yet added)
	    #login button
##
#####
	self.accountWin.state(newstate=Tkinter.NORMAL)
	self.accountWin.lift()

    def openPreferencesWin(self):
	if (not self.preferencesWin):
	    self.preferencesWin = Tkinter.Toplevel()
	    self.preferencesWin.protocol("WM_DELETE_WINDOW", self.preferencesCancel)
	    self.preferencesWin.title("Preferences")
	    self.prefTabs = Tix.NoteBook(self.preferencesWin)
	    self.prefTabs.grid(row=0, column=0, columnspan=4, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    # font & colors tab
	    self.prefTabs.add("fntClrTab", label="Font & Colors")
	    fntClrTab = self.prefTabs.fntClrTab
	    self.prefChatGrp = Tkinter.LabelFrame(fntClrTab, text="Chat Colors")
	    self.prefChatColorLbl = Tkinter.Label(self.prefChatGrp, text="Foreground:")
	    self.prefChatColorLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefChatColorEx = Tkinter.Label(self.prefChatGrp, text="   ")
	    self.prefChatColorEx.grid(row=0, column=1, padx=3, pady=5,
					sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.prefChatColorBut = Tkinter.Button(self.prefChatGrp, text="Choose...", command=self.chooseChatColor)
	    self.prefChatColorBut.grid(row=0, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefChatBgColorLbl = Tkinter.Label(self.prefChatGrp, text="Background:")
	    self.prefChatBgColorLbl.grid(row=1, column=0, sticky=Tkinter.W)
	    self.prefChatBgColorEx = Tkinter.Label(self.prefChatGrp, text="   ")
	    self.prefChatBgColorEx.grid(row=1, column=1, padx=3, pady=5,
					sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.prefChatBgColorBut = Tkinter.Button(self.prefChatGrp, text="Choose...",
							command=self.chooseChatBgColor)
	    self.prefChatBgColorBut.grid(row=1, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefChatGrp.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefTsClrGrp = Tkinter.LabelFrame(fntClrTab, text="Timestamp Colors")
	    self.prefTsColorLbl = Tkinter.Label(self.prefTsClrGrp, text="Foreground:")
	    self.prefTsColorLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefTsColorEx = Tkinter.Label(self.prefTsClrGrp, text="   ")
	    self.prefTsColorEx.grid(row=0, column=1, padx=3, pady=5,
					sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.prefTsColorBut = Tkinter.Button(self.prefTsClrGrp, text="Choose...", command=self.chooseTsColor)
	    self.prefTsColorBut.grid(row=0, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefTsBgColorLbl = Tkinter.Label(self.prefTsClrGrp, text="Background:")
	    self.prefTsBgColorLbl.grid(row=1, column=0, sticky=Tkinter.W)
	    self.prefTsBgColorEx = Tkinter.Label(self.prefTsClrGrp, text="   ")
	    self.prefTsBgColorEx.grid(row=1, column=1, padx=3, pady=5,
					sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.prefTsBgColorBut = Tkinter.Button(self.prefTsClrGrp, text="Choose...",
						    command=self.chooseTsBgColor)
	    self.prefTsBgColorBut.grid(row=1, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefTsClrGrp.grid(row=0, column=1, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefFontGrp = Tkinter.LabelFrame(fntClrTab, text="Chat Font")
	    self.prefFontFamLbl = Tkinter.Label(self.prefFontGrp, text="Family:")
	    self.prefFontFamLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefFontFam = Tkinter.StringVar()
	    self.prefFontFam.trace("w", self.updateFontFamily)
	    families = [fam for fam in tkFont.families() if (fam) and (not fam.startswith("@"))]
	    families.sort()
	    self.prefFontFamLst = ttk.Combobox(self.prefFontGrp, textvariable=self.prefFontFam, values=families,
						state="readonly")
	    self.prefFontFamLst.grid(row=0, column=1, columnspan=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefFontSizeLbl = Tkinter.Label(self.prefFontGrp, text="Size:")
	    self.prefFontSizeLbl.grid(row=0, column=3, sticky=Tkinter.E)
	    self.prefFontSize = Tkinter.IntVar()
	    self.prefFontSizeBox = Tix.Control(self.prefFontGrp, variable=self.prefFontSize, integer=True,
						min=3, max=144, autorepeat=False)
	    self.prefFontSizeBox.grid(row=0, column=4, sticky=(Tkinter.W, Tkinter.E))
	    self.prefFontBold = Tkinter.IntVar()
	    self.prefFontBoldBox = Tkinter.Checkbutton(self.prefFontGrp, text="Bold",
							variable=self.prefFontBold)
	    self.prefFontBoldBox.grid(row=1, column=0, sticky=Tkinter.W)
	    self.prefFontItalic = Tkinter.IntVar()
	    self.prefFontItalicBox = Tkinter.Checkbutton(self.prefFontGrp, text="Italic",
							variable=self.prefFontItalic)
	    self.prefFontItalicBox.grid(row=1, column=1, sticky=Tkinter.W)
	    kwargs = self.getFontArgs(force=True)
	    self.prefFontFont = tkFont.Font(**kwargs)
	    self.prefFontExampleBox = Tkinter.Text(self.prefFontGrp, height=1, width=28, font=self.prefFontFont)
	    self.prefFontExampleBox.grid(row=1, column=2, columnspan=3, sticky=(Tkinter.W, Tkinter.E))
	    self.prefFontExampleBox.tag_configure("exTsColor")
	    self.prefFontExampleBox.tag_configure("exMsgColor")
	    self.prefFontExampleBox.insert(Tkinter.END, "12:34 ", "exTsColor")
	    self.prefFontExampleBox.insert(Tkinter.END, "SomeUser: Some message", "exMsgColor")
	    self.prefFontExampleBox.config(state=Tkinter.DISABLED)
	    self.prefFontGrp.columnconfigure(2, weight=1)
	    self.prefFontGrp.grid(row=1, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefBrightGrp = Tkinter.LabelFrame(fntClrTab, text="Brightness Difference Threshold")
	    self.prefBrightExampleBox = Tkinter.Text(self.prefBrightGrp, height=1, width=26, font=self.prefFontFont)
	    for i in xrange(0, 26):
		br = (i * 255) / 25
		self.prefBrightExampleBox.tag_configure("ex%s" % i, foreground="#%02x%02x%02x" % (br, br, br))
		self.prefBrightExampleBox.insert(Tkinter.END, "%c" % (ord('a') + i), "ex%s" % i)
	    self.prefBrightExampleBox.config(state=Tkinter.DISABLED)
	    self.prefBrightExampleBox.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E))
	    self.prefBrightThresh = Tkinter.IntVar()
	    self.prefBrightThreshBox = Tix.Control(self.prefBrightGrp, variable=self.prefBrightThresh,
						    integer=True, min=0, max=128, autorepeat=False)
	    self.prefBrightThreshBox.grid(row=0, column=1, sticky=Tkinter.W)
	    self.prefBrightGrp.grid(row=2, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefUserGrp = Tkinter.LabelFrame(fntClrTab, text="User List Colors")
	    self.prefUserColorLbl = Tkinter.Label(self.prefUserGrp, text="Foreground:")
	    self.prefUserColorLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefUserColorEx = Tkinter.Label(self.prefUserGrp, text="   ")
	    self.prefUserColorEx.grid(row=0, column=1, padx=3, pady=5,
					sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.prefUserColorBut = Tkinter.Button(self.prefUserGrp, text="Choose...", command=self.chooseUserColor)
	    self.prefUserColorBut.grid(row=0, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefUserBgColorLbl = Tkinter.Label(self.prefUserGrp, text="Background:")
	    self.prefUserBgColorLbl.grid(row=1, column=0, sticky=Tkinter.W)
	    self.prefUserBgColorEx = Tkinter.Label(self.prefUserGrp, text="   ")
	    self.prefUserBgColorEx.grid(row=1, column=1, padx=3, pady=5,
					sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.prefUserBgColorBut = Tkinter.Button(self.prefUserGrp, text="Choose...",
							command=self.chooseUserBgColor)
	    self.prefUserBgColorBut.grid(row=1, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefUserListEx = Tkinter.Listbox(self.prefUserGrp, height=3, activestyle="none")
	    self.prefUserListEx.insert(Tkinter.END, "AUsefulUser")
	    self.prefUserListEx.insert(Tkinter.END, "SomeOtherUser")
	    self.prefUserListEx.insert(Tkinter.END, "YetAnotherUser")
	    self.prefUserListEx.config(state=Tkinter.DISABLED)
	    self.prefUserListEx.grid(row=0, column=3, rowspan=2, padx=3, sticky=Tkinter.E)
	    self.prefUserGrp.grid(row=3, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefFntClrDefGrp = Tkinter.LabelFrame(fntClrTab, text="Reset to Default")
	    self.prefColorResetBut = Tkinter.Button(self.prefFntClrDefGrp, text="Reset Colors",
						    command=self.prefColorReset)
	    self.prefColorResetBut.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E))
	    self.prefFontResetBut = Tkinter.Button(self.prefFntClrDefGrp, text="Reset Font",
						    command=self.prefFontReset)
	    self.prefFontResetBut.grid(row=0, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.prefBrightResetBut = Tkinter.Button(self.prefFntClrDefGrp, text="Reset Brightness",
						    command=self.prefBrightReset)
	    self.prefBrightResetBut.grid(row=0, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.prefFntClrDefGrp.columnconfigure(0, weight=1)
	    self.prefFntClrDefGrp.columnconfigure(1, weight=1)
	    self.prefFntClrDefGrp.columnconfigure(2, weight=1)
	    self.prefFntClrDefGrp.grid(row=4, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    fntClrTab.columnconfigure(0, weight=1)
	    fntClrTab.columnconfigure(1, weight=1)
	    # formatting & misc tab
	    self.prefTabs.add("fmtMiscTab", label="Formatting & Misc")
	    fmtMiscTab = self.prefTabs.fmtMiscTab
	    self.prefTsGrp = Tkinter.LabelFrame(fmtMiscTab, text="Timestamps")
	    self.prefTsFmtLbl = Tkinter.Label(self.prefTsGrp, text="Format:")
	    self.prefTsFmtLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefTsFmt = Tkinter.StringVar()
	    self.prefTsFmt.trace("w", self.updateTsFormat)
	    self.prefTsFmtBox = ttk.Combobox(self.prefTsGrp, textvariable=self.prefTsFmt, values=TIMESTAMP_FORMATS)
	    self.prefTsFmtBox.grid(row=0, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.prefTsFmtEx = Tkinter.Label(self.prefTsGrp, text="")
	    self.prefTsFmtEx.grid(row=1, column=0, columnspan=2, sticky=Tkinter.W)
	    self.prefTsShow = Tkinter.IntVar()
	    self.prefTsShowBox = Tkinter.Checkbutton(self.prefTsGrp, text="Show Chat Timestamps",
							variable=self.prefTsShow, command=self.updateTsShow)
	    self.prefTsShowBox.grid(row=2, column=0, columnspan=2, sticky=Tkinter.W)
	    self.prefTsGrp.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefFmtGrp = Tkinter.LabelFrame(fmtMiscTab, text="Other Formatting")
	    self.prefLatinLbl = Tkinter.Label(self.prefFmtGrp,
						text="Annotate display name if proportion of Latin chars <")
	    self.prefLatinLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefLatinThresh = Tkinter.DoubleVar()
	    self.prefLatinThreshBox = Tix.Control(self.prefFmtGrp, variable=self.prefLatinThresh,
						    min=0, max=1, step=0.01, command=self.updateLatinThresh)
	    self.prefLatinThreshBox.grid(row=0, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.prefWrapChat = Tkinter.IntVar()
	    self.prefWrapChatBox = Tkinter.Checkbutton(self.prefFmtGrp, text="Wrap Chat Lines",
							variable=self.prefWrapChat, command=self.updateWrapChat)
	    self.prefWrapChatBox.grid(row=1, column=0, columnspan=2, sticky=Tkinter.W)
	    self.prefFmtGrp.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefMiscGrp = Tkinter.LabelFrame(fmtMiscTab, text="Miscellaneous")
	    self.prefMaxHistoryLbl = Tkinter.Label(self.prefMiscGrp, text="Maximum Input History Retained:")
	    self.prefMaxHistoryLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.prefMaxHistory = Tkinter.IntVar()
	    self.prefMaxHistoryBox = Tix.Control(self.prefMiscGrp, variable=self.prefMaxHistory,
						    min=0, command=self.updateMaxHistory)
	    self.prefMaxHistoryBox.grid(row=0, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.prefMaxScratchLbl = Tkinter.Label(self.prefMiscGrp, text="Maximum Scratch Menu Entry Width:")
	    self.prefMaxScratchLbl.grid(row=1, column=0, sticky=Tkinter.W)
	    self.prefMaxScratch = Tkinter.IntVar()
	    self.prefMaxScratchBox = Tix.Control(self.prefMiscGrp, variable=self.prefMaxScratch,
						    min=5, command=self.updateMaxScratch)
	    self.prefMaxScratchBox.grid(row=1, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.prefShowUser = Tkinter.IntVar()
	    self.prefShowUserBox = Tkinter.Checkbutton(self.prefMiscGrp, text="Show User Pane",
							variable=self.prefShowUser, command=self.updateShowUser)
	    self.prefShowUserBox.grid(row=2, column=0, columnspan=2, sticky=Tkinter.W)
	    self.prefMiscGrp.grid(row=2, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefFmtMiscResetBut = Tkinter.Button(fmtMiscTab, text="Reset Page to Default",
							command=self.prefFmtMiscReset)
	    self.prefFmtMiscResetBut.grid(row=3, column=0, sticky=Tkinter.E)
	    fmtMiscTab.columnconfigure(0, weight=1)
	    self.prefResetBut = Tkinter.Button(self.preferencesWin, text="Reset All to Default",
						command=self.preferencesReset)
	    self.prefResetBut.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.N))
	    self.prefOkBut = Tkinter.Button(self.preferencesWin, text="OK", command=self.preferencesOK)
	    self.prefOkBut.grid(row=1, column=1, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefCancelBut = Tkinter.Button(self.preferencesWin, text="Cancel", command=self.preferencesCancel)
	    self.prefCancelBut.grid(row=1, column=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.prefApplyBut = Tkinter.Button(self.preferencesWin, text="Apply", command=self.preferencesApply)
	    self.prefApplyBut.grid(row=1, column=3, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.preferencesWin.columnconfigure(0, weight=1)
	    self.preferencesWin.rowconfigure(0, weight=1)
	    self.prefFontSizeBox.configure(command=self.updateFontSize)
	    self.prefFontBoldBox.configure(command=self.updateFontBold)
	    self.prefFontItalicBox.configure(command=self.updateFontItalic)
	    self.prefBrightThreshBox.configure(command=self.updateBrightThresh)
	fgColor = self.getPreference('chatColor', self.translateColor(self.chatBox.cget('fg')))
	self.prefChatColorEx.config(background=fgColor)
	bgColor = self.getPreference('chatBgColor', self.translateColor(self.chatBox.cget('bg')))
	self.prefChatBgColorEx.config(background=bgColor)
	tsClr = self.getPreference('timestampColor', fgColor)
	self.prefTsColorEx.config(background=tsClr)
	tsBgClr = self.getPreference('timestampBgColor', bgColor)
	self.prefTsBgColorEx.config(background=tsBgClr)
	fontAttrs = tkFont.nametofont(self.chatBox.cget('font')).actual()
	fFam = self.getPreference('chatFontFamily', fontAttrs.get('family', tkFont.families()[0]))
	self.prefFontFam.set(fFam)
	fSize = self.getPreference('chatFontSize', fontAttrs.get('size', 12))
	self.prefFontSize.set(fSize)
	fWeight = fontAttrs.get('weight', "normal")
	if (self.preferences.has_key('chatFontBold')):
	    if (self.preferences['chatFontBold']):
		fWeight = "bold"
	    else:
		fWeight = "normal"
	self.prefFontBold.set(int(fWeight == "bold"))
	fSlant = fontAttrs.get('slant', "roman")
	if (self.preferences.has_key('chatFontItalic')):
	    if (self.preferences['chatFontItalic']):
		fSlant = "italic"
	    else:
		fSlant = "roman"
	self.prefFontItalic.set(int(fSlant == "italic"))
	self.prefFontFont.config(family=fFam, size=fSize, weight=fWeight, slant=fSlant)
	self.prefFontExampleBox.config(bg=bgColor)
	self.prefFontExampleBox.tag_configure("exTsColor", foreground=tsClr, background=tsBgClr)
	self.prefFontExampleBox.tag_configure("exMsgColor", foreground=fgColor, background=bgColor)
	self.prefBrightThresh.set(self.getPreference('brightnessThreshold'))
	self.updateBrightExampleBox(bgColor)
	userFg = self.getPreference('userColor', self.translateColor(self.userList.cget('fg')))
	self.prefUserColorEx.config(background=userFg)
	userBg = self.getPreference('userBgColor', self.translateColor(self.userList.cget('bg')))
	self.prefUserBgColorEx.config(background=userBg)
	self.prefUserListEx.config(fg=userFg, bg=userBg, disabledforeground=userFg)
	tsFmt = self.getPreference('timestampFormat')
	self.prefTsFmtBox.set(tsFmt)
	self.prefTsFmtEx.config(text=time.strftime(tsFmt))
	self.prefTsShow.set(int(self.getPreference('showTimestamps')))
	self.prefLatinThresh.set(self.getPreference('latinThreshold'))
	self.prefWrapChat.set(int(self.getPreference('wrapChatText')))
	self.prefMaxHistory.set(self.getPreference('maxInputHistory'))
	self.prefMaxScratch.set(self.getPreference('maxScratchWidth'))
	self.prefShowUser.set(int(self.getPreference('userPaneVisible')))
	self.prefApplyBut.config(state=Tkinter.DISABLED)
	self.prefsToSet = {}
	self.preferencesWin.state(newstate=Tkinter.NORMAL)
	self.preferencesWin.lift()

    def addFavorite(self):
	if ((not self.curChannel) or (self.curChannel in self.preferences.get('favorites', []))):
	    return
	favorites = self.preferences.get('favorites', [])
	favorites.append(self.curChannel)
	favorites.sort(key=lambda c: c.lower())
	self.preferences['favorites'] = favorites
	self.preferences.sync()
	idx = self.preferences['favorites'].index(self.curChannel)
	cmd = lambda c=self.curChannel: self.doChannelOpen(c)
	self.favoritesMen.insert_command(idx + 3, label=self.curChannel, command=cmd)

    def editFavorites(self):
#####
##
	pass
##
#####

    def editMacros(self):
	if (not self.macrosWin):
	    self.macrosWin = Tkinter.Toplevel()
	    self.macrosWin.protocol("WM_DELETE_WINDOW", self.macrosWin.withdraw)
	    self.macrosWin.title("Macros")
	    self.macrosPanes = Tkinter.PanedWindow(self.macrosWin, sashrelief=Tkinter.GROOVE)
	    self.macroTreePane = Tkinter.Frame(self.macrosPanes)
	    self.macroTreeGrid = Tkinter.Frame(self.macroTreePane)
	    self.macroTree = ttk.Treeview(self.macroTreeGrid, selectmode="browse", show="tree")
	    self.macroTree.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.macroTreeVScroll = Tkinter.Scrollbar(self.macroTreeGrid, command=self.macroTree.yview)
	    self.macroTreeVScroll.grid(row=0, column=1, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	    self.macroTreeHScroll = Tkinter.Scrollbar(self.macroTreeGrid, orient=Tkinter.HORIZONTAL,
							command=self.macroTree.xview)
	    self.macroTreeHScroll.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	    self.macroTree.configure(xscrollcommand=self.macroTreeHScroll.set,
				    yscrollcommand=self.macroTreeVScroll.set)
	    self.macroTreeGrid.columnconfigure(0, weight=1)
	    self.macroTreeGrid.rowconfigure(0, weight=1)
	    self.macroTreeGrid.grid(row=0, column=0, columnspan=2,
				    sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.macroTreeUpBut = Tkinter.Button(self.macroTreePane, text="Move Up", command=self.macroTreeUp,
						    state=Tkinter.DISABLED)
	    self.macroTreeUpBut.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E))
	    self.macroTreeDownBut = Tkinter.Button(self.macroTreePane, text="Move Down", command=self.macroTreeDown,
						    state=Tkinter.DISABLED)
	    self.macroTreeDownBut.grid(row=1, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.macroTreeOutBut = Tkinter.Button(self.macroTreePane, text="Move Out", command=self.macroTreeOut,
						    state=Tkinter.DISABLED)
	    self.macroTreeOutBut.grid(row=2, column=0, sticky=(Tkinter.W, Tkinter.E))
	    self.macroTreeInBut = Tkinter.Button(self.macroTreePane, text="Move In", command=self.macroTreeIn,
						    state=Tkinter.DISABLED)
	    self.macroTreeInBut.grid(row=2, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.macroTreePane.columnconfigure(0, weight=1)
	    self.macroTreePane.columnconfigure(1, weight=1)
	    self.macroTreePane.rowconfigure(0, weight=1)
	    self.macrosPanes.add(self.macroTreePane, stretch="always")
	    self.macroDefPane = Tkinter.Frame(self.macrosPanes)
	    macroDefNameGrid = Tkinter.Frame(self.macroDefPane)
	    self.macroDefNameLbl = Tkinter.Label(macroDefNameGrid, text="Name:")
	    self.macroDefNameLbl.grid(row=0, column=0, sticky=Tkinter.W)
	    self.macroDefNameBox = Tkinter.Entry(macroDefNameGrid, state=Tkinter.DISABLED)
	    self.macroDefNameBox.grid(row=0, column=1, sticky=(Tkinter.W, Tkinter.E))
	    self.macroDefUpdateBut = Tkinter.Button(macroDefNameGrid, text="Update", command=self.macroDefUpdate,
						    state=Tkinter.DISABLED)
	    self.macroDefUpdateBut.grid(row=0, column=2, sticky=(Tkinter.W, Tkinter.E))
	    self.macroDefCopyBut = Tkinter.Button(macroDefNameGrid, text="Copy", command=self.macroDefCopy,
						    state=Tkinter.DISABLED)
	    self.macroDefCopyBut.grid(row=0, column=3, sticky=(Tkinter.W, Tkinter.E))
	    macroDefNameGrid.columnconfigure(1, weight=1)
	    macroDefNameGrid.grid(row=0, column=0, columnspan=6,
				    sticky=(Tkinter.E, Tkinter.W, Tkinter.N, Tkinter.S))
	    self.macroDefBodyLbl = Tkinter.Label(self.macroDefPane, text="Body:")
	    self.macroDefBodyLbl.grid(row=1, column=0, sticky=Tkinter.W)
	    self.macroPromptInsBut = Tkinter.Button(self.macroDefPane, text="Insert Prompt",
						    command=self.macroPromptIns, state=Tkinter.DISABLED)
	    self.macroPromptInsBut.grid(row=1, column=2, sticky=Tkinter.E)
	    self.macroPromptEditBut = Tkinter.Button(self.macroDefPane, text="Edit Prompt",
						    command=self.macroPromptEdit, state=Tkinter.DISABLED)
	    self.macroPromptEditBut.grid(row=1, column=3, sticky=(Tkinter.E, Tkinter.W))
	    self.macroDefGrid = Tkinter.Frame(self.macroDefPane)
	    self.macroDefBox = Tkinter.Text(self.macroDefGrid, wrap=Tkinter.WORD, width=40, height=3,
					    state=Tkinter.DISABLED)
	    self.macroDefBox.grid(row=0, column=0, sticky=(Tkinter.E, Tkinter.W, Tkinter.N, Tkinter.S))
	    self.macroDefVScroll = Tkinter.Scrollbar(self.macroDefGrid, command=self.macroDefBox.yview)
	    self.macroDefVScroll.grid(row=0, column=1, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	    self.macroDefBox.configure(yscrollcommand=self.macroDefVScroll.set)
	    self.macroDefGrid.columnconfigure(0, weight=1)
	    self.macroDefGrid.rowconfigure(0, weight=1)
	    self.macroDefGrid.grid(row=2, column=0, columnspan=4,
				    sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.macroDefDelBut = Tkinter.Button(self.macroDefPane, text="Delete", command=self.macroDefDel,
						    state=Tkinter.DISABLED)
	    self.macroDefDelBut.grid(row=3, column=0, pady=3, sticky=Tkinter.W)
	    self.macroMenuAddBut = Tkinter.Button(self.macroDefPane, text="New Menu", command=self.macroMenuAdd)
	    self.macroMenuAddBut.grid(row=3, column=2, pady=3, sticky=(Tkinter.W, Tkinter.E))
	    self.macroMacroAddBut = Tkinter.Button(self.macroDefPane, text="New Macro", command=self.macroMacroAdd)
	    self.macroMacroAddBut.grid(row=3, column=3, pady=3, sticky=(Tkinter.W, Tkinter.E))
	    self.macrosDoneBut = Tkinter.Button(self.macroDefPane, text="Done", command=self.macrosWin.withdraw)
	    self.macrosDoneBut.grid(row=4, column=3, sticky=(Tkinter.E, Tkinter.S))
	    self.macroDefPane.columnconfigure(1, weight=1)
	    self.macroDefPane.rowconfigure(2, weight=1)
	    self.macrosPanes.add(self.macroDefPane, stretch="always")
	    self.macrosPanes.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	    self.macrosWin.columnconfigure(0, weight=1)
	    self.macrosWin.rowconfigure(0, weight=1)
	    def populateMacroTree(macros, prefix=()):
		prefixKey = ".".join(map(str, prefix))
		for i in xrange(len(macros)):
		    path = prefix + (i,)
		    pathKey = ".".join(map(str, path))
		    self.macroTree.insert(prefixKey, Tkinter.END, pathKey, text=macros[i][0])
		    if (len(macros[i]) == 2):
			populateMacroTree(macros[i][1], path)
	    populateMacroTree(self.preferences.get('macros', []))
	    self.macroTree.bind("<<TreeviewSelect>>", self.macroTreeSelect)
	self.macrosWin.state(newstate=Tkinter.NORMAL)
	self.macrosWin.lift()

    def executeMacro(self, format, prompts):
#####
##
	pass
	print "macro: '%s', %s"%(format,prompts)
##
######

    def channelTabChanged(self, e=None):
	tabId = self.channelTabs.select()
	if (not tabId):
	    return
	idx = self.channelTabs.index(tabId)
	if ((idx < 0) or (idx >= len(self.channelOrder)) or (self.channelOrder[idx] == self.curChannel)):
	    return
	self.curChannel = self.channelOrder[idx]
	self.populateChat(self.channels[self.curChannel]['log'])
	self.userListLock.acquire()
	self.userList.delete(0, Tkinter.END)
	self.channels[self.curChannel]['userLock'].acquire()
	for user in self.getSortedUsers(self.curChannel):
	    self.userList.insert(Tkinter.END, self.channels[self.curChannel]['users'][user].get('display',user))
	self.channels[self.curChannel]['userLock'].release()
	self.userListLock.release()

    def channelTabClosed(self, idx):
	if ((idx < 0) or (idx >= len(self.channelOrder))):
	    return
	channel = self.channelOrder[idx]
#####
##
	#maybe prompt to confirm leaving without saving log; return True to abort
##
######
	self.chat.leave(channel)
	self.channelOrder = self.channelOrder[:idx] + self.channelOrder[idx + 1:]
	del self.channels[channel]
	self.curChannel = None
	if (not self.channels):
	    self.chatBoxLock.acquire()
	    self.chatBox.delete("1.0", Tkinter.END)
	    self.chatBoxLock.release()
	    self.userListLock.acquire()
	    self.userList.delete(0, Tkinter.END)
	    self.userListLock.release()
	self.removeTags(channel)

    def copyChat(self, e):
	self.chatBox.clipboard_clear()
	self.chatBox.clipboard_append(self.chatBox.get("sel.first", "sel.last"))

    def startChatSearch(self, e):
	self.searchBackwards = False
	if (self.searchString is None):
	    self.searchString = ""
	else:
	    if (not self.searchString):
		self.searchString = self.lastSearchString
	    self.doSearch(skip=True)
	return "break"

    def startBackwardsChatSearch(self, e):
	self.searchBackwards = True
	if (self.searchString is None):
	    self.searchString = ""
	else:
	    if (not self.searchString):
		self.searchString = self.lastSearchString
	    self.doSearch(skip=True)
	return "break"

    def handleChatKey(self, e):
	if (e.keysym in ["Up", "Down", "Left", "Right", "Home", "End"]):
	    self.stopChatSearch()
	    return
	if (self.searchString is None):
	    return "break"
	if (e.keysym == "Escape"):
	    self.stopChatSearch()
	    return "break"
	if (e.keysym == "BackSpace"):
	    self.searchString = self.searchString[:-1]
	    return "break"
	if ((not hasattr(e, 'char')) or (not e.char)):
	    return "break"
	self.searchString += e.char
	self.doSearch()
	return "break"

    def stopChatSearch(self, e=None):
	if (self.searchString):
	    self.lastSearchString = self.searchString
	self.searchString = None

    def scratchInput(self):
	s = self.chatInputBox.get()
	if ((not s) or (s in self.scratchMsgs)):
	    return
	self.scratchMsgs.append(s)
	maxWidth = self.getPreference('maxScratchWidth')
	if (len(s) <= maxWidth):
	    shortS = s
	else:
	    shortS = s[:maxWidth / 2 - 1] + "..." + s[-((maxWidth - 1) / 2 - 1):]
	self.scratchMen.add_command(label=shortS, command=lambda cmd=s: self.scratchCmd(cmd))
	self.chatInputBox.delete(0, Tkinter.END)

    def scratchCmd(self, s):
	if (not s):
	    return
	self.chatInputBox.delete(0, Tkinter.END)
	self.chatInputBox.insert(0, s)
	try:
	    idx = self.scratchMsgs.index(s)
	except ValueError:
	    return
	self.scratchMsgs = self.scratchMsgs[:idx] + self.scratchMsgs[idx + 1:]
	self.scratchMen.delete(idx + 2)

    def submitChatInput(self, e=None):
	s = self.chatInputBox.get()
	if (not s):
	    return
	self.inputHistory.append(s)
	self.inputHistory = self.inputHistory[-self.preferences.get('maxInputHistory'):]
	self.inputHistoryPos = len(self.inputHistory)
	self.chatInputBox.delete(0, Tkinter.END)
	if ((not self.chat) or (not self.curChannel) or (not self.channels.has_key(self.curChannel))):
	    return
	self.chat.send(self.curChannel, s)

    def inputUpHistory(self, e=None):
	if (self.inputHistoryPos > len(self.inputHistory)):
	    self.inputHistoryPos = len(self.inputHistory)
	if (self.inputHistoryPos <= 0):
	    return
	self.inputHistoryPos -= 1
	self.chatInputBox.delete(0, Tkinter.END)
	self.chatInputBox.insert(0, self.inputHistory[self.inputHistoryPos])

    def inputDownHistory(self, e=None):
	if (self.inputHistoryPos >= len(self.inputHistory)):
	    return
	self.inputHistoryPos += 1
	if (self.inputHistoryPos >= len(self.inputHistory)):
	    s = ""
	else:
	    s = self.inputHistory[self.inputHistoryPos]
	self.chatInputBox.delete(0, Tkinter.END)
	self.chatInputBox.insert(0, s)

#####
##
    #other handlers
    #account window handlers
##
#####

    def chooseColor(self, title, pref, default, example, tagName=None, tagProp=None):
	val = tkColorChooser.askcolor(default, parent=self.preferencesWin, title=title)
	if ((not val) or (type(val) != type(())) or (len(val) != 2) or (not val[1])):
	    return
	self.prefsToSet[pref] = val[1]
	example.config(bg=val[1])
	if ((tagName) and (tagProp)):
	    kwargs = {tagProp: val[1]}
	    self.prefFontExampleBox.tag_configure(tagName, **kwargs)
	self.prefApplyBut.config(state=Tkinter.NORMAL)
	return val[1]

    def chooseChatColor(self):
	clr = self.getPreference('chatColor', self.translateColor(self.chatBox.cget('fg')))
	clr = self.prefsToSet.get('chatColor', clr)
	clr = self.chooseColor("Chat Foreground", 'chatColor', clr, self.prefChatColorEx,
				"exMsgColor", 'foreground')
	if ((clr) and (not self.getPreference('timestampColor'))):
	    self.prefTsColorEx.config(bg=clr)
	    self.prefFontExampleBox.tag_configure("exTsColor", foreground=clr)

    def chooseChatBgColor(self):
	clr = self.getPreference('chatBgColor', self.translateColor(self.chatBox.cget('bg')))
	clr = self.prefsToSet.get('chatBgColor', clr)
	clr = self.chooseColor("Chat Background", 'chatBgColor', clr, self.prefChatBgColorEx,
				"exMsgColor", 'background')
	if (clr):
	    self.prefFontExampleBox.config(bg=clr)
	    self.updateBrightExampleBox(clr)
	    if (not self.getPreference('timestampBgColor')):
		self.prefTsBgColorEx.config(bg=clr)
		self.prefFontExampleBox.tag_configure("exTsColor", background=clr)

    def chooseTsColor(self):
	chatClr = self.getPreference('chatColor', self.translateColor(self.chatBox.cget('fg')))
	chatClr = self.prefsToSet.get('chatColor', chatClr)
	clr = self.getPreference('timestampColor', chatClr)
	clr = self.prefsToSet.get('timestampColor', clr)
	self.chooseColor("Timestamp Foreground", 'timestampColor', clr, self.prefTsColorEx,
			    "exTsColor", 'foreground')

    def chooseTsBgColor(self):
	chatClr = self.getPreference('chatBgColor', self.translateColor(self.chatBox.cget('bg')))
	chatClr = self.prefsToSet.get('chatBgColor', clr)
	clr = self.getPreference('timestampBgColor', chatClr)
	clr = self.prefsToSet.get('timestampBgColor', clr)
	self.chooseColor("Timestamp Background", 'timestampBgColor', clr, self.prefTsBgColorEx,
			    "exTsColor", 'background')

    def updateFontFamily(self, *args, **kwargs):
	self.prefsToSet['chatFontFamily'] = self.prefFontFam.get()
	self.prefFontFont.config(family=self.prefsToSet['chatFontFamily'])
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateFontSize(self, *args, **kwargs):
	self.prefsToSet['chatFontSize'] = self.prefFontSize.get()
	self.prefFontFont.config(size=self.prefsToSet['chatFontSize'])
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateFontBold(self, *args, **kwargs):
	self.prefsToSet['chatFontBold'] = bool(self.prefFontBold.get())
	if (self.prefsToSet['chatFontBold']):
	    self.prefFontFont.config(weight="bold")
	else:
	    self.prefFontFont.config(weight="normal")
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateFontItalic(self, *args, **kwargs):
	self.prefsToSet['chatFontItalic'] = bool(self.prefFontItalic.get())
	if (self.prefsToSet['chatFontItalic']):
	    self.prefFontFont.config(slant="italic")
	else:
	    self.prefFontFont.config(slant="roman")
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateBrightExampleBox(self, bgColor=None):
	if (not bgColor):
	    bgColor = self.getPreference('chatBgColor', self.translateColor(self.chatBox.cget('bg')))
	    bgColor = self.prefsToSet.get('chatBgColor', bgColor)
	self.prefBrightExampleBox.config(bg=bgColor)
	threshold = self.prefsToSet.get('brightnessThreshold', self.getPreference('brightnessThreshold'))
	for i in xrange(0, 26):
	    br = (i * 255) / 25
	    clr = self.adjustHexColor(bgColor, "#%02x%02x%02x" % (br, br, br), threshold)
	    self.prefBrightExampleBox.tag_configure("ex%s" % i, background=clr)

    def updateBrightThresh(self, *args, **kwargs):
	self.prefsToSet['brightnessThreshold'] = self.prefBrightThresh.get()
	self.updateBrightExampleBox()
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def chooseUserColor(self):
	clr = self.getPreference('userColor', self.translateColor(self.userList.cget('fg')))
	clr = self.prefsToSet.get('userColor', clr)
	clr = self.chooseColor("User List Foreground", 'userColor', clr, self.prefUserColorEx)
	self.prefUserListEx.config(fg=clr, disabledforeground=clr)

    def chooseUserBgColor(self):
	clr = self.getPreference('userBgColor', self.translateColor(self.userList.cget('bg')))
	clr = self.prefsToSet.get('userBgColor', clr)
	clr = self.chooseColor("User List Background", 'userBgColor', clr, self.prefUserBgColorEx)
	self.prefUserListEx.config(bg=clr)

    def prefColorReset(self):
	fgColor = self.translateColor("SystemWindowText")
	bgColor = self.translateColor("SystemWindow")
	userColor = self.translateColor("SystemButtonText")
	changed = False
	opts = [('chatColor', fgColor, self.prefChatColorEx, self.prefTsColorEx,
			"exMsgColor", "exTsColor", 'foreground'),
		('chatBgColor', bgColor, self.prefChatBgColorEx, self.prefTsBgColorEx,
			"exMsgColor", "exTsColor", 'background'),
		('timestampColor', fgColor, self.prefTsColorEx, None,
			"exTsColor", None, 'foreground'),
		('timestampBgColor', bgColor, self.prefTsBgColorEx, None,
			"exTsColor", None, 'background')]
	for (pref, color, example, subExample, tagName, subTagName, tagProp) in opts:
	    changeIt = False
	    if (self.prefsToSet.has_key(pref)):
		if (self.prefsToSet[pref] != color):
		    changeIt = True
	    elif (self.preferences.has_key(pref)):
		if (self.preferences[pref] != color):
		    changeIt = True
	    if (changeIt):
		self.prefsToSet[pref] = color
		example.config(bg=color)
		if (subExample):
		    subExample.config(bg=color)
		kwargs = {tagProp: color}
		self.prefFontExampleBox.tag_configure(tagName, **kwargs)
		if (subTagName):
		    self.prefFontExampleBox.tag_configure(subTagName, **kwargs)
		changed = True
	if (changed):
	    self.prefFontExampleBox.config(bg=bgColor)
	    self.updateBrightExampleBox(bgColor)
	opts = [('userColor', userColor, self.prefUserColorEx, 'fg', 'disabledforeground'),
		('userBgColor', bgColor, self.prefUserBgColorEx, 'bg', None)]
	for (pref, color, example, prop, subProp) in opts:
	    changeIt = False
	    if (self.prefsToSet.has_key(pref)):
		if (self.prefsToSet[pref] != color):
		    changeIt = True
	    if (self.preferences.has_key(pref)):
		if (self.preferences[pref] != color):
		    changeIt = True
	    if (changeIt):
		self.prefsToSet[pref] = color
		example.config(bg=color)
		kwargs = {prop: color}
		if (subProp):
		    kwargs[subProp] = color
		self.prefUserListEx.config(**kwargs)
		changed = True
	if (changed):
	    self.prefApplyBut.config(state=Tkinter.NORMAL)

    def prefFontReset(self):
	font = tkFont.nametofont(self.chatBox.cget('font')).actual()
	for (prefKey, fontKey, var) in [('chatFontFamily', 'family', self.prefFontFam),
					('chatFontSize', 'size', self.prefFontSize)]:
	    if (self.prefsToSet.has_key(prefKey)):
		if (self.prefsToSet[prefKey] != font[fontKey]):
		    var.set(font[fontKey])
	    elif (self.preferences.has_key(prefKey)):
		if (self.preferences[prefKey] != font[fontKey]):
		    var.set(font[fontKey])
	opts = [('chatFontBold', 'weight', "bold", "normal", self.prefFontBold),
		('chatFontItalic', 'slant', "italic", "roman", self.prefFontItalic)]
	updateArgs = {}
	for (prefKey, fontKey, fontTrue, fontFalse, var) in opts:
	    if (self.prefsToSet.has_key(prefKey)):
		if (((self.prefsToSet[prefKey]) and (font[fontKey] != fontTrue)) or
			((not self.prefsToSet[prefKey]) and (font[fontKey] != fontTrue))):
		    var.set(int(not self.prefsToSet[prefKey]))
		    updateArgs[fontKey] = font[fontKey]
	    elif (self.preferences.has_key(prefKey)):
		if (((self.preferences[prefKey]) and (font[fontKey] != fontTrue)) or
			((not self.preferences[prefKey]) and (font[fontKey] != fontFalse))):
		    var.set(int(not self.preferences[prefKey]))
		    updateArgs[fontKey] = font[fontKey]
	if (updateArgs):
	    self.prefFontFont.config(**updateArgs)

    def prefBrightReset(self):
	if (self.prefsToSet.get('brightnessThreshold') == DEFAULT_PREFERENCES['brightnessThreshold']):
	    return
	if ((not self.prefsToSet.has_key('brightnessThreshold')) and
		(self.getPreference('brightnessThreshold') == DEFAULT_PREFERENCES['brightnessThreshold'])):
	    return
	self.prefBrightThresh.set(DEFAULT_PREFERENCES['brightnessThreshold'])

    def updateTsFormat(self, *args, **kwargs):
	newFmt = self.prefTsFmt.get()
	try:
	    example = time.strftime(newFmt)
	except ValueError:
	    return
	self.prefsToSet['timestampFormat'] = newFmt
	self.prefTsFmtEx.config(text=example)
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateTsShow(self, *args, **kwargs):
	self.prefsToSet['showTimestamps'] = bool(self.prefTsShow.get())
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateLatinThresh(self, *args, **kwargs):
	self.prefsToSet['latinThreshold'] = self.prefLatinThresh.get()
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateWrapChat(self, *args, **kwargs):
	self.prefsToSet['wrapChatText'] = bool(self.prefWrapChat.get())
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateMaxHistory(self, *args, **kwargs):
	self.prefsToSet['maxInputHistory'] = self.prefMaxHistory.get()
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateMaxScratch(self, *args, **kwargs):
	self.prefsToSet['maxScratchWidth'] = self.prefMaxScratch.get()
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def updateShowUser(self, *args, **kwargs):
	self.prefsToSet['userPaneVisible'] = bool(self.prefShowUser.get())
	self.prefApplyBut.config(state=Tkinter.NORMAL)

    def prefFmtMiscReset(self):
	for (pref, var, cast) in [('timestampFormat', self.prefTsFmt, str),
				    ('showTimestamps', self.prefTsShow, int),
				    ('latinThreshold', self.prefLatinThresh, float),
				    ('wrapChatText', self.prefWrapChat, int),
				    ('maxInputHistory', self.prefMaxHistory, int),
				    ('maxScratchWidth', self.prefMaxScratch, int),
				    ('userPaneVisible', self.prefShowUser, int)]:
	    if (self.prefsToSet.has_key(pref)):
		if (self.prefsToSet[pref] != DEFAULT_PREFERENCES[pref]):
		    var.set(cast(DEFAULT_PREFERENCES[pref]))
	    elif (self.preferences.has_key(pref)):
		if (self.preferences[pref] != DEFAULT_PREFERENCES[pref]):
		    var.set(cast(DEFAULT_PREFERENCES[pref]))

    def preferencesReset(self):
	self.prefColorReset()
	self.prefFontReset()
	self.prefBrightReset()
	self.prefFmtMiscReset()

    def preferencesOK(self):
	self.preferencesApply()
	self.preferencesWin.withdraw()

    def preferencesCancel(self):
	self.preferencesWin.withdraw()

    def preferencesApply(self):
	self.prefFontSizeBox.update()
	if (not self.prefsToSet):
	    return
	updateChat = False
	for pref in self.prefsToSet.keys():
	    self.preferences[pref] = self.prefsToSet[pref]
	    if (pref in CHAT_PREFERENCES):
		updateChat = True
	    elif (pref == 'userColor'):
		self.userList.config(fg=self.prefsToSet[pref])
	    elif (pref == 'userBgColor'):
		self.userList.config(bg=self.prefsToSet[pref])
	    elif (pref == 'wrapChatText'):
		self.configWrapVar.set(int(self.prefsToSet['wrapChatText']))
		if (self.prefsToSet['wrapChatText']):
		    wrap = Tkinter.WORD
		else:
		    wrap = Tkinter.NONE
		self.chatBox.config(wrap=wrap)
#####
##
	    #maxScratchWidth: repopulate self.scratchMen
##
#####
	    elif (pref == 'userPaneVisible'):
		w = self.master.winfo_width()
		h = self.master.winfo_height()
		x = self.master.winfo_x()
		y = self.master.winfo_y()
		if (self.prefsToSet['userPaneVisible']):
		    self.panes.add(self.userPane, stretch="always")
		    self.userPaneToggle.configure(text=">")
		    self.configUserVar.set(1)
		else:
		    self.panes.remove(self.userPane)
		    self.userPaneToggle.configure(text="<")
		    self.configUserVar.set(0)
		self.master.geometry("%sx%s+%s+%s" % (w, h, x, y))
	self.savePreferences()
	if ((updateChat) and (self.curChannel)):
	    self.populateChat(self.channels[self.curChannel]['log'])
	self.prefApplyBut.config(state=Tkinter.DISABLED)

#####
##
    #favorites window handlers
##
#####

#####
##
    def macroTreeUp(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	pass
	#move macro or menu up in tree and list

    def macroTreeDown(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	pass
	#move macro or menu down in tree and list

    def macroTreeOut(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	pass
	#move macro or menu up out of submenu

    def macroTreeIn(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	pass
	#move macro or menu down into submenu
##
#####

    def macroDefUpdate(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	macro = parent[self.curMacro[-1]]
	itemName = self.macroDefNameBox.get()
	if (not itemName):
	    return
	offset = 0
	if (parentMen[0] == self.macrosMen):
	    offset = 2
	parentMen[0].entryconfigure(self.curMacro[-1] + offset, label=itemName)
	if (len(macro) == 2):
	    macro = (itemName, macro[1])
	else:
	    macroBody = self.macroDefBox.get("1.0", Tkinter.END).strip()
#####
##
	    prompts = []
	    #deal with prompts
##
#####
	    handler = lambda f=macroBody, p=prompts: self.executeMacro(f, p)
	    parentMen[0].entryconfigure(self.curMacro[-1] + offset, command=handler)
	    macro = (itemName, macroBody, prompts)
	parent[self.curMacro[-1]] = macro
	self.preferences['macros'] = macros
	self.savePreferences()

#####
##
    def macroDefCopy(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	macro = parent[self.curMacro[-1]]
	pass
	#copy macro or menu

    def macroPromptIns(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	macro = parent[self.curMacro[-1]]
	pass
	#insert new prompt into macro

    def macroPromptEdit(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	macro = parent[self.curMacro[-1]]
	pass
	#edit prompt selected in macro
##
#####

    def macroDefDel(self):
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen) or (self.curMacro[-1] >= len(parent))):
	    return
	if (len(parent[self.curMacro[-1]]) == 2):
	    confirmMsg = "Are you sure you want to delete this menu?"
	else:
	    confirmMsg = "Are you sure you want to delete this macro?"
	if (not tkMessageBox.askyesno("Confirm", confirmMsg, parent=self.macrosWin)):
	    return
	itemKey = ".".join(map(str, self.curMacro))
	parent.pop(self.curMacro[-1])
	offset = 0
	if (parentMen[0] == self.macrosMen):
	    offset = 2
	parentMen[0].delete(self.curMacro[-1] + offset)
	parentMen[1].pop(self.curMacro[-1])
	self.macroTreeDeselect()
	self.preferences['macros'] = macros
	self.savePreferences()
	self.macroTree.delete(itemKey)

    def macroMenuAdd(self):
	self.macroItemAdd("macro menu", ([],), True)

    def macroMacroAdd(self):
	self.macroItemAdd("macro", ("", []), False)

    def macroItemAdd(self, itemType, itemBody, submenu=False):
	itemName = tkSimpleDialog.askstring("Name", "Enter name for new %s" % itemType, parent=self.macrosWin)
	if (not itemName):
	    return
	if (self.curMacro):
	    (macros, parent, parentMen) = self.getCurMacroParent()
	else:
	    macros = self.preferences.get('macros', [])
	    parent = macros
	    parentMen = (self.macrosMen, self.macrosMenus)
	if ((macros is None) or (parent is None) or (not parentMen)):
	    return
	parentPath = self.curMacro[:-1]
	if ((self.curMacro) and (self.curMacro[-1] >= 0) and (self.curMacro[-1] < len(parent))):
	    if (len(parent[self.curMacro[-1]]) == 2):
		parent = parent[self.curMacro[-1]][1]
		parentMen = parentMen[1][self.curMacro[-1]]
		parentPath = parentPath + (self.curMacro[-1],)
#####
##
#	    maybe an else to insert at self.curMacro[-1]+1 instead of end
##
#####
	itemPath = parentPath + (len(parent),)
	parentKey = ".".join(map(str, parentPath))
	itemKey = ".".join(map(str, itemPath))
	parent.append((itemName,) + itemBody)
	self.preferences['macros'] = macros
	self.savePreferences()
	if (submenu):
	    subMen = Tkinter.Menu(parentMen[0], tearoff=False)
	    parentMen[0].add_cascade(label=itemName, menu=subMen)
	    parentMen[1].append((subMen, []))
	else:
	    parentMen[0].add_command(label=itemName, command=lambda: None)
	    parentMen[1].append(None)
	self.macroTree.insert(parentKey, Tkinter.END, itemKey, text=itemName)
	self.macroTree.see(itemKey)
	self.macroTree.focus(itemKey)
	self.macroTree.selection_set(itemKey)

    def macroTreeDeselect(self):
	self.curMacro = ()
	self.macroTreeUpBut.config(state=Tkinter.DISABLED)
	self.macroTreeDownBut.config(state=Tkinter.DISABLED)
	self.macroTreeOutBut.config(state=Tkinter.DISABLED)
	self.macroTreeInBut.config(state=Tkinter.DISABLED)
	self.macroDefNameBox.delete(0, Tkinter.END)
	self.macroDefNameBox.config(state=Tkinter.DISABLED)
	self.macroDefUpdateBut.config(state=Tkinter.DISABLED)
	self.macroDefCopyBut.config(state=Tkinter.DISABLED)
	self.macroPromptInsBut.config(state=Tkinter.DISABLED)
	self.macroPromptEditBut.config(state=Tkinter.DISABLED)
	self.macroDefBox.delete("1.0", Tkinter.END)
	self.macroDefBox.config(state=Tkinter.DISABLED)
	self.macroDefDelBut.config(state=Tkinter.DISABLED)

    def macroTreeSelect(self, *args, **kwargs):
	self.macroTreeDeselect()
	selected = self.macroTree.focus()
	if (not hasattr(selected, 'split')):
	    return
	try:
	    self.curMacro = tuple(map(int, selected.split(".")))
	except ValueError:
	    return
	(macros, parent, parentMen) = self.getCurMacroParent()
	if ((macros is None) or (parent is None) or (not parentMen)):
	    return
	macro = parent[self.curMacro[-1]]
	self.macroTreeUpBut.config(state=Tkinter.NORMAL)
	self.macroTreeDownBut.config(state=Tkinter.NORMAL)
	self.macroTreeOutBut.config(state=Tkinter.NORMAL)
	self.macroTreeInBut.config(state=Tkinter.NORMAL)
	self.macroDefNameBox.config(state=Tkinter.NORMAL)
	self.macroDefNameBox.insert(Tkinter.END, macro[0])
	self.macroDefUpdateBut.config(state=Tkinter.NORMAL)
	self.macroDefCopyBut.config(state=Tkinter.NORMAL)
	if (len(macro) == 3):
	    self.macroPromptInsBut.config(state=Tkinter.NORMAL)
	    self.macroPromptEditBut.config(state=Tkinter.NORMAL)
	    self.macroDefBox.config(state=Tkinter.NORMAL)
	    self.macroDefBox.insert(Tkinter.END, macro[1])
	self.macroDefDelBut.config(state=Tkinter.NORMAL)

#####
##
    #other macro window handlers
##
#####

    def populateMacrosMenu(self, menu, menuLst, macros):
	for macro in macros:
	    if (len(macro) == 2):
		subMen = Tkinter.Menu(menu, tearoff=False)
		subLst = []
		self.populateMacrosMenu(subMen, subLst, macro[1])
		menuLst.append((subMen, subLst))
		menu.add_cascade(label=macro[0], menu=subMen)
	    else:
		menuLst.append(None)
#####
##
		menu.add_command(label=macro[0], command=lambda f=macro[1], p=macro[2]: self.executeMacro(f, p))
	    #macro is (name, format, prompts)
	    #  prompt is (optional name, prompt string, type, optional default, optional type args (e.g. min/max))
	    #    prompt should probably be dictionary because of all the optional values
	    #    type is one of user, string, integer, float
	    #macro list is (name, children)

##
#####

    def getPreference(self, pref, default=None):
	return self.preferences.get(pref, DEFAULT_PREFERENCES.get(pref, default))

    def doChannelOpen(self, channel):
	if (not channel):
	    return
#####
##
	if (self.channels.has_key(channel)):
	    #maybe warn about already connected and/or raise channel tab
	    return
	#get oauth (logging in if necessary)
	oauth=base64.b64decode(self.preferences.get('token'))
##
######
	if (not self.chat):
	    latinThresh = self.getPreference('latinThreshold')
	    userHint = self.getPreference('userName')
	    displayHint = self.getPreference('userDisplay')
	    self.chat = Twitch.Chat(ChatCallbackFunctions(self), oauth, latinThresh, userHint, displayHint)
	    if (self.chat.userName):
		self.preferences['userName'] = self.chat.userName
	    if (self.chat.displayName):
		self.preferences['userDisplay'] = self.chat.displayName
	self.channels[channel] = {'users': {}, 'log': [], 'userLock': threading.Lock()}
	self.channelOrder.append(channel)
	self.channels[channel]['frame'] = Tkinter.Frame(self.channelTabs)
	self.channelTabs.add(self.channels[channel]['frame'], text=channel)
	self.channelTabs.select(len(self.channelOrder) - 1)
	self.curChannel = channel
	self.chatBoxLock.acquire()
	self.chatBox.delete("1.0", Tkinter.END)
	self.chatBoxLock.release()
	self.userListLock.acquire()
	self.userList.delete(0, Tkinter.END)
	self.userListLock.release()
	self.chat.join(channel)

    def getSortedUsers(self, channel):
	if ((not channel) or (not self.channels.has_key(channel))):
	    return
	users = self.channels[channel]['users'].keys()
	users.sort(key=lambda u: self.channels[channel]['users'][u].get('display', u).lower())
	return users

    def adjustColor(self, c, ref, threshold=None):
	if (type(threshold) != type(0)):
	    threshold = self.getPreference('brightnessThreshold')
	cBr = getColorBrightness(c)
	rBr = getColorBrightness(ref)
	if (abs(cBr - rBr) >= threshold):
	    return c
	if (cBr != 0):
	    if (cBr < rBr):
		# see if we can push c darker without pushing below 0
		f = float(rBr - threshold) / cBr
		t = (c[0] * f, c[1] * f, c[2] * f)
		if ((t[0] >= 0) and (t[0] < 256) and (t[1] >=0) and (t[1] < 256) and (t[2] >= 0) and (t[2] < 256)):
		    return t
	    else:
		# see if we can push c lighter without pushing above 255
		f = float(rBr + threshold) / cBr
		t = (c[0] * f, c[1] * f, c[2] * f)
		if ((t[0] >= 0) and (t[0] < 256) and (t[1] >=0) and (t[1] < 256) and (t[2] >= 0) and (t[2] < 256)):
		    return t
	# if we got here, we'll have to push the other direction
	if (rBr < 128):
	    # ref is dark, so push c lighter
	    if (cBr == 0):
		return (255, 255, 255)
	    f = float(rBr + threshold) / cBr
	    return (min(c[0] * f, 255), min(c[1] * f, 255), min(c[2] * f, 255))
	else:
	    # ref is light, so push c darker
	    if (cBr == 0):
		return (0, 0, 0)
	    f = max(float(rBr - threshold) / cBr, 0)
	    return (min(c[0] * f, 255), min(c[1] * f, 255), min(c[2] * f, 255))

    def adjustHexColor(self, c, ref, threshold=None):
	return rgbToHex(self.adjustColor(hexToRgb(c), hexToRgb(ref), threshold))

    def translateColor(self, c):
	if (not c):
	    return "#000000"
	t16 = self.winfo_rgb(c)
	return rgbToHex((t16[0] / 256, t16[1] / 256, t16[2] / 256))

    def getFontArgs(self, force=False):
	retval = {}
	if (self.preferences.get('chatFontFamily')):
	    retval['family'] = self.preferences.get('chatFontFamily')
	if (self.preferences.get('chatFontSize')):
	    retval['size'] = self.preferences.get('chatFontSize')
	if (self.preferences.get('chatFontBold')):
	    retval['weight'] = "bold"
	if (self.preferences.get('chatFontItalic')):
	    retval['slant'] = "italic"
	if ((retval) or (force)):
	    defaultAttrs = tkFont.nametofont(self.chatBox.cget('font')).actual()
	    for kw in ['family', 'weight', 'slant', 'overstrike', 'underline', 'size']:
		if ((not retval.has_key(kw)) and (defaultAttrs.has_key(kw))):
		    retval[kw] = defaultAttrs[kw]
	return retval

    def populateChat(self, log):
	self.chatBoxLock.acquire()
	self.chatBox.delete("1.0", Tkinter.END)
	self.chatToPopulate = log[:]
	self.chatBoxLock.release()
	if (not self.chatPopulateThread):
	    self.chatPopulateThread = threading.Thread(target=self.populateChatThreadHandler)
	    self.chatPopulateThread.daemon = True
	    self.chatPopulateThread.start()

    def populateChatThreadHandler(self):
	while (True):
	    if (not self.chatToPopulate):
		time.sleep(CHAT_POPULATE_INTERVAL)
		continue
	    self.chatBoxLock.acquire()
	    if (not self.chatToPopulate):
		self.chatBoxLock.release()
		continue
	    logLine = self.chatToPopulate.pop()
	    if (logLine[0] != EVENT_MSG):
		self.chatBoxLock.release()
		continue
	    (e, ts, user, msg, userDisplay, userColor, userBadges, emotes) = logLine
	    if (userColor):
		self.setupTag(self.curChannel, userColor)
	    tsTags = []
	    userTags = []
	    msgTags = []
	    if (userColor):
		userTags.append(userColor)
	    if (self.useTsTag):
		tsTags.append("tsColor")
	    if (self.useMsgTag):
		msgTags.append("msgColor")
	    if (self.useFontTag):
		tsTags.append("msgFont")
		userTags.append("msgFont")
		msgTags.append("msgFont")
	    tsTags = tuple(tsTags)
	    userTags = tuple(userTags)
	    msgTags = tuple(msgTags)
#####
##
	    #deal with emotes
	    if ((msg.startswith(ACTION_PREFIX)) and (msg.endswith(ACTION_SUFFIX))):
		msgTags = userTags
		msg = " %s\n" % msg[len(ACTION_PREFIX):-len(ACTION_SUFFIX)]
	    else:
		msg = ": %s\n" % msg
	    self.chatBox.insert("1.0", msg, msgTags)
	    #deal with badges
	    self.chatBox.insert("1.0", userDisplay, userTags)
	    if (self.preferences.get('showTimestamps')):
		tsFmt = self.getPreference('timestampFormat')
		self.chatBox.insert("1.0", "%s " % time.strftime(tsFmt, time.localtime(ts)), tsTags)
##
#####
	    self.chatBoxLock.release()

    def doSearch(self, skip=False):
	idx = Tkinter.INSERT
	if (bool(self.searchBackwards) != bool(skip)):
	    idx += " + %s chars" % len(self.searchString)
	nocase = (self.searchString == self.searchString.lower())
	pos = self.chatBox.search(self.searchString, idx, backwards=self.searchBackwards, nocase=nocase)
	if (not pos):
	    if (self.searchBackwards):
		idx = Tkinter.END
	    else:
		idx = "1.0"
	    pos = self.chatBox.search(self.searchString, idx, backwards=self.searchBackwards, nocase=nocase)
	if (pos):
	    self.chatBox.tag_remove(Tkinter.SEL, "1.0", Tkinter.END)
	    self.chatBox.mark_set(Tkinter.SEL_FIRST, pos)
	    self.chatBox.mark_set(Tkinter.SEL_LAST, pos + " + %s chars" % len(self.searchString))
	    self.chatBox.tag_add(Tkinter.SEL, Tkinter.SEL_FIRST, Tkinter.SEL_LAST)
	    self.chatBox.mark_set(Tkinter.INSERT, pos)
	    self.chatBox.see(pos)

    def setupTag(self, channel, color):
	if (not color):
	    return
	if (self.chatTags.has_key(color)):
	    self.chatTags[color].add(channel)
	    return
	self.chatTags[color] = set([color])
	kwargs = {'foreground': color}
	bgColor = self.preferences.get('chatBgColor')
	needBg = True
	if (not bgColor):
	    needBg = False
	    bgColor = self.translateColor(self.chatBox.cget('bg'))
	adjustedBg = self.adjustHexColor(bgColor, color)
	if (adjustedBg != bgColor):
	    needBg = True
	if (needBg):
	    kwargs['background'] = adjustedBg
	self.chatBox.tag_configure(color, **kwargs)

    def removeTags(self, channel):
	for color in self.chatTags.keys():
	    if (channel not in self.chatTags[color]):
		continue
	    self.chatTags[color].remove(channel)
	    if (not self.chatTags[color]):
		self.chatBox.tag_delete(color)

    def getCurMacroParent(self):
	if ((not self.curMacro) or (self.curMacro[-1] < 0)):
	    return (None, None, None)
	macros = self.preferences.get('macros', [])
	parentMen = (self.macrosMen, self.macrosMenus)
	parent = macros
	for i in self.curMacro[:-1]:
	    if ((i < 0) or (i >= len(parent)) or (len(parent[i]) != 2) or (type(parent[i][1]) != type([]))):
		return (None, None, None)
	    parent = parent[i][1]
	    if ((i >= len(parentMen[1])) or (type(parentMen[1][i]) != type(())) or (not parentMen[1][i])):
		return (None, None, None)
	    parentMen = parentMen[1][i]
	return (macros, parent, parentMen)


mainWin = MainGui(Tix.Tk())
mainWin.mainloop()
