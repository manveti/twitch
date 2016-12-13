import httplib
import json
import re
import select
import socket
import ssl
import threading
import unicodedata
import urllib
import webbrowser


CLIENT_ID = "8ttcvo44qr7774zw9hounn1bcx2lnk2"

REDIRECT_ADDR = ("localhost", 14425)
REDIRECT_URI = "http://%s:%s" % REDIRECT_ADDR

AUTH_URL_BASE = "https://api.twitch.tv/kraken/oauth2/authorize"
AUTH_ARGS = "?response_type=token&client_id=%(cid)s&redirect_uri=%(redirect)s&scope=%(scope)s"
AUTH_FORCE_ARG = "&force_verify=true"

DEFAULT_SCOPES = ["user_read", "chat_login"]

API_ADDR = ("api.twitch.tv", 443)
API_URL_BASE = "https://%s/kraken" % API_ADDR[0]

CHAT_ADDR = ("irc.chat.twitch.tv", 6667)

BUF_SIZE = 1024
READ_INTERVAL = 0.1

AUTH_HTML = """<html>
<head>
<title>Authorizing</title>
<script language="javascript"><!--
function getAuthInfo(){
    var req = new XMLHttpRequest();
    req.onreadystatechange = function(){
	if ((this.readyState != 4) || (this.status != 200)){
	    return;
	}
	var progBox = document.getElementById('authProgress');
	progBox.innerHTML = "<big>Authorized</big><br>\\n<small>You may now close this page.</small>";
    };
    req.open("POST", "%s", true);
    req.send(document.location.hash);
}
--></script>
</head>
<body onLoad="getAuthInfo()">
<div style="position: absolute; top: 50%%; left: 50%%; transform: translate(-50%%, -50%%)">
 <div id="authProgress" style="text-align: center">
  <big>Authorizing...</big><br>
  <small>Please do not close this page until authorization complete.</small>
 </div>
</div>
</body>
</html>""" % REDIRECT_URI

LENGTH_EXP = re.compile("^Content-Length:\s*(?P<len>\d+)\s*$", re.I + re.M)

exp = "^(@(?P<tags>[^ \r\n]+) )?(:(?P<prefix>[^ \r\n]+) )?(?P<command>([a-zA-Z]+|[0-9]{3}))"
exp += "(?P<params>( [^: \r\n][^ \r\n]*){0,14})( :(?P<final>[^\r\n]+))?$"
IRC_MSG_EXP = re.compile(exp)
IRC_PREFIX_EXP = re.compile("[@!.]")


def getOauth(scopes=DEFAULT_SCOPES, force=False):
    args = {'cid':	urllib.quote(CLIENT_ID),
	    'redirect':	urllib.quote(REDIRECT_URI),
	    'scope':	urllib.quote(" ".join(scopes))}
    url = AUTH_URL_BASE + (AUTH_ARGS % args)
    if (force):
	url += AUTH_FORCE_ARG
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#####
##
    #timeout?
##
#####
    server.bind(REDIRECT_ADDR)
    server.listen(1)
    webbrowser.open(url)
    conn = server.accept()
    resp = ""
    while (True):
	s = conn[0].recv(BUF_SIZE)
	if (not s):
	    break
	resp += s
	if (resp.find("\r\n\r\n") >= 0):
	    break
#####
##
    #verify that resp is http request ("GET / HTTP/1.1\r\n")
##
#####
    msg = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: %s\r\n\r\n%s"
    conn[0].send(msg % (len(AUTH_HTML), AUTH_HTML))
    if (not re.search("^Connection:\s*keep-alive\s*$", resp, re.I + re.M)):
	conn[0].close()
	conn = server.accept()
    resp = ""
    bodyStart = None
    bodyLength = None
    while (True):
	s = conn[0].recv(BUF_SIZE)
	if (not s):
	    break
	resp += s
	if (not bodyStart):
	    idx = resp.find("\r\n\r\n")
	    if (idx >= 0):
		bodyStart = idx + 4
	if ((bodyStart) and (not bodyLength)):
	    m = LENGTH_EXP.search(resp)
	    if (m):
		bodyLength = int(m.group('len'))
	if ((bodyLength) and (len(resp) >= bodyStart + bodyLength)):
	    break
    resp = resp[bodyStart : (bodyStart + bodyLength)]
    if (resp[0] == '#'):
	resp = resp[1:]
    conn[0].send("HTTP/1.1 200 OK\r\nContent-type: text/html\r\nContent-Length: 0\r\n\r\n")
    conn[0].close()
    server.close()
    respVars = {}
    for tok in resp.split("&"):
	(var, val) = tok.split("=", 1)
	respVars[var] = urllib.unquote_plus(val)
    return (respVars.get('access_token'), respVars.get('scope'))

def getApi(path, oauth=None):
    if (not oauth):
	oauth = getOauth()
    if ((path) and (path[0] != "/")):
	path = "/" + path
    url = "%s%s" % (API_URL_BASE, path)
    headers = {'Accept': "application/vnd.twitchtv.v5+json", 'Authorization': "OAuth %s" % oauth}
    conn = httplib.HTTPSConnection(API_ADDR[0])
    conn.request("GET", url, headers=headers)
    httpResp = conn.getresponse()
    resp = httpResp.read()
    return json.loads(resp)

class ChatCallbacks:
    def userJoined(self, channel, user):
	pass

    def usersJoined(self, channel, users):
	for user in users:
	    self.userJoined(channel, user)

    def userLeft(self, channel, user):
	pass

    def chatMessage(self, channel, user, msg, userDisplay=None, userColor=None, userBadges=set(), emotes=[]):
	pass

    def otherCommand(self, command, tags, prefix, params):
	pass

class Chat:
    def __init__(self, callbacks, oauth=None, latinThresh=1, userHint=None, displayHint=None):
	if (not oauth):
	    oauth = getOauth()

	self.callbacks = callbacks
	self.oauth = oauth
	self.latinThresh = latinThresh

	try:
	    userInfo = getApi("/user", self.oauth)
	    self.userName = userInfo.get('name')
	    self.displayName = userInfo.get('display_name', self.userName)
	except ValueError:
	    self.userName = userHint
	    if (displayHint):
		self.displayName = displayHint
	    else:
		self.displayName = userHint

	self.socket = None
	self.running = False
	self.buf = ""
	self.channels = {}

    def connect(self):
	self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	self.socket.connect(CHAT_ADDR)
	self.socket.send("PASS oauth:%s\r\nNICK %s\r\n" % (self.oauth, self.displayName.lower()))
	self.channels = {}
	self.buf = ""
	self.running = True
	self.thread = threading.Thread(target=self.recvThread)
	self.thread.start()
	self.socket.send("CAP REQ :twitch.tv/membership\r\n")
	self.socket.send("CAP REQ :twitch.tv/commands\r\n")
	self.socket.send("CAP REQ :twitch.tv/tags\r\n")

    def disconnect(self):
	for channel in self.channels.keys():
	    self.leave(channel)
	self.running = False

    def recvThread(self):
	def decodeUser(s):
	    splits = IRC_PREFIX_EXP.split(s or "")
	    if ((splits) and (splits[0])):
		return splits[0]
	    return "<server>"
	def decodeChannel(s):
	    if (s[0] == "#"):
		return s[1:]
	    return s
	def unescapeTags(s):
	    s = s.replace("\\:", ";").replace("\\s", " ").replace("\\\\", "\\")
	    return s.replace("\\r", "\r").replace("\\n", "\n")
	charDict = {}
	def charIsLatin(c):
	    if (not c.isalpha()):
		return True
	    if (not charDict.has_key(c)):
		charDict[c] = unicodedata.name(c, "").startswith("LATIN")
	    return charDict[c]
	def isLatin(s):
	    if (not s):
		return True
	    if (type(s) != type(u"")):
		s = s.decode("utf-8")
	    return sum(1 for c in s if charIsLatin(c)) * self.latinThresh >= len(s)
	while (self.running):
	    if (not select.select([self.socket], [], [], READ_INTERVAL)[0]):
		continue
	    self.buf += self.socket.recv(BUF_SIZE)
	    lines = self.buf.replace("\r\n", "\n").split("\n")
	    self.buf = lines.pop()
	    for line in lines:
		m = IRC_MSG_EXP.match(line)
		cmd = m.group('command')
		params = m.group('params').split(" ")[1:]
		tags = map(unescapeTags, (m.group('tags') or "").split(";"))
		if (m.group('final')):
		    params.append(m.group('final'))
		if (cmd == "PING"):
		    self.socket.send("PONG :%s\r\n" % params[-1])
		    continue
		if (cmd == "PRIVMSG"):
		    if ((not params) or (not params[0])):
			continue
		    channel = decodeChannel(params[0])
		    user = decodeUser(m.group('prefix'))
		    display = None
		    color = None
		    badges = set()
		    emotes = []
		    for tag in tags:
			tagSplits = tag.split("=", 1)
			if (len(tagSplits) > 1):
			    if (tagSplits[0] == "display-name"):
				display = tagSplits[1]
				continue
			    if (tagSplits[0] == "color"):
				color = tagSplits[1]
				continue
			    if (tagSplits[0] == "badges"):
				badges = set(tagSplits[1].split(","))
				continue
			    if (tagSplits[0] == "emotes"):
				for spec in tagSplits[1].split("/"):
				    emoteSplits = spec.split(":")
				    if (len(emoteSplits) != 2):
					continue
				    emoteId = int(emoteSplits[0])
				    for loc in emoteSplits[1].split(","):
					locSplits = loc.split("-")
					if (len(locSplits) != 2):
					    continue
					emotes.append((int(locSplits[0]), int(locSplits[1]) + 1, emoteId))
				continue
		    if (not display):
			display = user
		    emotes.sort()
		    if (not isLatin(display)):
			display = "%s (%s)" % (display, user)
		    msg = " ".join(params[1:])
		    self.callbacks.chatMessage(channel, user, msg, display, color, badges, emotes)
		    continue
		if (cmd in ["JOIN", "PART"]):
		    if ((not params) or (not params[0])):
			continue
		    channel = decodeChannel(params[0])
		    user = decodeUser(m.group('prefix'))
		    if (cmd == "JOIN"):
			self.callbacks.userJoined(channel, user)
		    if (cmd == "PART"):
			self.callbacks.userLeft(channel, user)
		    continue
		if (cmd == "353"):
		    if ((len(params) < 4) or (not params[2])):
			continue
		    channel = decodeChannel(params[2])
		    users = set(" ".join(params[3:]).split())
		    self.callbacks.usersJoined(channel, users)
		if (cmd == "USERSTATE"):
		    if ((not params) or (not params[0])):
			continue
		    channel = decodeChannel(params[0])
		    if (not self.channels.has_key(channel)):
			continue
		    for tag in tags:
			tagSplits = tag.split("=", 1)
			if (len(tagSplits) > 1):
			    if (tagSplits[0] == "display-name"):
				self.channels[channel]['display'] = tagSplits[1]
				continue
			    if (tagSplits[0] == "color"):
				self.channels[channel]['color'] = tagSplits[1]
				continue
			    if (tagSplits[0] == "badges"):
				self.channels[channel]['badges'] = set(tagSplits[1].split(","))
				continue
#####
##
			    #maybe handle emote-sets, mod, subscriber
##
#####
		    if (not self.channels[channel]['pending']):
			continue
		    msg = self.channels[channel]['pending'].pop(0)
		    if (msg.startswith("/me ")):
			msg = "%cACTION %s%c" % (1, msg[4:], 1)
		    display = self.channels[channel].get('display', self.displayName)
		    color = self.channels[channel].get('color')
		    badges = self.channels[channel].get('badges')
#####
##
		    #figure out emotes in msg
		    emotes=[]
##
#####
		    self.callbacks.chatMessage(channel, self.userName, msg, display, color, badges, emotes)
		    continue
#####
##
		#probably handle:
		#  NOTICE: ["#${channel}", explanation]; event info in tags
		#  RECONNECT (requires CAP REQ :twitch.tv/commands): disconnect, reconnect, and rejoin channels
		#maybe handle:
		#  MODE (user gained/lost moderator): ["#${channel}", "+o"|"-o", user]
		#  HOSTTARGET (start/stop host): ["#${hosting_channel}", "${-|hosted_channel} ${number_of_viewers}"]
		#  CLEARCHAT: ["#${channel}", optional_banned_user]; duration and reason in tags
		#  USERNOTICE (resub): ["#${channel}", optional_message]; tags give user, sub length, etc.
##
#####
		self.callbacks.otherCommand(cmd, tags, m.group('prefix'), params)
	self.socket.close()
	self.socket = None

    def join(self, channel):
	if (not self.socket):
	    self.connect()
	if (channel[0] == "#"):
	    channel = channel[1:]
	if (self.channels.has_key(channel)):
	    return
	self.channels[channel] = {'pending': []}
	self.socket.send("JOIN #%s\r\n" % channel)

    def leave(self, channel):
	if (channel[0] == "#"):
	    channel = channel[1:]
	if ((not self.socket) or (not self.channels.has_key(channel))):
	    return
	self.socket.send("PART #%s\r\n" % channel)
	del self.channels[channel]

    def send(self, channel, msg):
	if (channel[0] == "#"):
	    channel = channel[1:]
	if ((not self.socket) or (not self.channels.has_key(channel))):
	    return
	self.channels[channel]['pending'].append(msg)
	self.socket.send("PRIVMSG #%s :%s\r\n" % (channel, msg))
