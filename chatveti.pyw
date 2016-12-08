#!/usr/bin/env python

import base64
import cPickle
import os.path
import shelve
import threading
import Tkinter
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
    'maxInputHistory':		100,
    'maxScratchWidth':		50,
    'showTimestamps':		True,
    'timestampFormat':		"%H:%M",
    'userPaneVisible':		True,
    'wrapChatText':		True,
}

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
	    tsFmt = self.master.preferences.get('timestampFormat', DEFAULT_PREFERENCES['timestampFormat'])
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

	self.chatBoxLock = threading.Lock()
	self.userListLock = threading.Lock()

	self.master.title("ChatVeti")
	self.menuBar = Tkinter.Menu(self)
	master.config(menu=self.menuBar)

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

#####
##
	#other menus
	#  config (account...; show/hide timestamps; ?show/hide user list?; preferences...)
##
#####

	# favorites menu
	self.favoritesMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.favoritesMen.add_command(label="Add Favorite", command=self.addFavorite)
	self.favoritesMen.add_command(label="Edit Favorites...", command=self.editFavorites)
	self.favoritesMen.add_separator()
	for channel in self.preferences.get('favorites', []):
	    self.favoritesMen.add_command(label=channel, command=lambda c=channel: self.doChannelOpen(c))
	self.menuBar.add_cascade(label="Favorites", menu=self.favoritesMen)

#####
##
	#macros menu (edit macros..., -, macro1, macro2, ...)
##
#####

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
	kwargs = {}
	if (self.preferences.get('chatFontFamily')):
	    kwargs['family'] = self.preferences.get('chatFontFamily')
	if (self.preferences.get('chatFontSize')):
	    kwargs['size'] = self.preferences.get('chatFontSize')
	if (self.preferences.get('chatFontBold')):
	    kwargs['weight'] = "bold"
	if (self.preferences.get('chatFontItalic')):
	    kwargs['slant'] = "italic"
	if (kwargs):
	    defaultAttrs = tkFont.nametofont(self.chatBox.cget('font')).actual()
	    for kw in ['family', 'weight', 'slant', 'overstrike', 'underline', 'size']:
		if ((not kwargs.has_key(kw)) and (defaultAttrs.has_key(kw))):
		    kwargs[kw] = defaultAttrs[kw]
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

#####
##
    #other menu handlers
##
#####

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

#####
##
    #macros menu handlers
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

    def toggleUserPane(self):
	w = self.master.winfo_width()
	h = self.master.winfo_height()
	x = self.master.winfo_x()
	y = self.master.winfo_y()
	if (self.preferences.get('userPaneVisible')):
	    self.panes.remove(self.userPane)
	    self.userPaneToggle.configure(text="<")
	    self.preferences['userPaneVisible'] = False
	else:
	    self.panes.add(self.userPane, stretch="always")
	    self.userPaneToggle.configure(text=">")
	    self.preferences['userPaneVisible'] = True
	self.master.geometry("%sx%s+%s+%s" % (w, h, x, y))
	self.savePreferences()

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
	maxWidth = self.preferences.get('maxScratchWidth', DEFAULT_PREFERENCES['maxScratchWidth'])
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
##
#####

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
	    self.chat = Twitch.Chat(ChatCallbackFunctions(self), oauth)
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

    def adjustColor(self, c, ref):
	threshold = self.preferences.get('brightnessThreshold', DEFAULT_PREFERENCES['brightnessThreshold'])
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

    def adjustHexColor(self, c, ref):
	return rgbToHex(self.adjustColor(hexToRgb(c), hexToRgb(ref)))

    def translateColor(self, c):
	if (not c):
	    return "#000000"
	t16 = self.winfo_rgb(c)
	return rgbToHex((t16[0] / 256, t16[1] / 256, t16[2] / 256))

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
		tsFmt = self.preferences.get('timestampFormat', DEFAULT_PREFERENCES['timestampFormat'])
		self.chatBox.insert(Tkinter.END, "%s " % time.strftime(tsFmt, time.localtime(ts)), tsTags)
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


mainWin = MainGui(Tix.Tk())
mainWin.mainloop()
