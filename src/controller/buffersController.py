# -*- coding: utf-8 -*-
import wx
import widgetUtils
import arrow
import webbrowser
import output
import config
import sound
import messages
import languageHandler
import logging
from twitter import compose, utils
from wxUI import buffers, dialogs, commonMessageDialogs
from mysc.thread_utils import call_threaded
from twython import TwythonError

log = logging.getLogger("controller.buffers")
class bufferController(object):
 def __init__(self, parent=None, function=None, session=None, *args, **kwargs):
  super(bufferController, self).__init__()
  self.function = function
  self.compose_function = None
  self.args = args
  self.kwargs = kwargs
  self.buffer = None
  self.account = ""
  self.needs_init = True
  self.invisible = False # False if the buffer will be ignored on the invisible interface.

 def get_event(self, ev):
  if ev.GetKeyCode() == wx.WXK_RETURN and ev.ControlDown(): event = "audio"
  elif ev.GetKeyCode() == wx.WXK_RETURN: event = "url"
  elif ev.GetKeyCode() == wx.WXK_F5: event = "volume_down"
  elif ev.GetKeyCode() == wx.WXK_F6: event = "volume_up"
  elif ev.GetKeyCode() == wx.WXK_DELETE and ev.ShiftDown(): event = "clear_list"
  elif ev.GetKeyCode() == wx.WXK_DELETE: event = "destroy_status"
  else:
   event = None
   ev.Skip()
  if event != None:
#   try:
   getattr(self, event)()
#   except AttributeError:
   #pass
 
 def volume_down(self):
  if self.session.settings["sound"]["volume"] > 0.0:
   if self.session.settings["sound"]["volume"] <= 0.05:
    self.session.settings["sound"]["volume"] = 0.0
   else:
    self.session.settings["sound"]["volume"] -=0.05
  if hasattr(sound.URLPlayer, "stream"):
   sound.URLPlayer.stream.volume = self.session.settings["sound"]["volume"]
  self.session.sound.play("volume_changed.ogg")

 def volume_up(self):
  if self.session.settings["sound"]["volume"] < 1.0:
   if self.session.settings["sound"]["volume"] >= 0.95:
    self.session.settings["sound"]["volume"] = 1.0
   else:
    self.session.settings["sound"]["volume"] +=0.05
  if hasattr(sound.URLPlayer, "stream"):
   sound.URLPlayer.stream.volume = self.session.settings["sound"]["volume"]
  self.session.sound.play("volume_changed.ogg")

 def start_stream(self):
  pass

 def put_items_on_list(self, items):
  pass

 def remove_buffer(self):
  pass

 def remove_item(self, item):
  self.buffer.list.remove_item(item)

 def bind_events(self):
  pass

 def get_object(self):
  return self.buffer

 def get_message(self):
  pass

 def set_list_position(self, reversed=False):
  if reversed == False:
   self.buffer.list.select_item(-1)
  else:
   self.buffer.list.select_item(0)

 def reply(self):
  pass

 def direct_message(self):
  pass

 def retweet(self):
  pass

 def destroy_status(self):
  pass

 def post_tweet(self, *args, **kwargs):
  title = _(u"Tweet")
  caption = _(u"Write the tweet here")
  tweet = messages.tweet(self.session, title, caption, "")
  if tweet.message.get_response() == widgetUtils.OK:
   text = tweet.message.get_text()
   if tweet.image == None:
    call_threaded(self.session.api_call, call_name="update_status", status=text)
   else:
    call_threaded(self.session.api_call, call_name="update_status_with_media", status=text, media=tweet.image)

class accountPanel(bufferController):
 def __init__(self, parent, name, account):
  super(accountPanel, self).__init__(parent, None, name)
  log.debug("Initializing buffer %s, account %s" % (name, account,))
  self.buffer = buffers.accountPanel(parent, name)
  self.type = self.buffer.type
  self.compose_function = None
  self.session = None
  self.needs_init = False
  self.id = self.buffer.GetId()
  self.account = account
  self.buffer.account = account
  self.name = name

class emptyPanel(bufferController):
 def __init__(self, parent, name, account):
  super(emptyPanel, self).__init__(parent, None, name)
  log.debug("Initializing buffer %s, account %s" % (name, account,))
  self.buffer = buffers.emptyPanel(parent, name)
  self.type = self.buffer.type
  self.compose_function = None
  self.id = self.buffer.GetId()
  self.account = account
  self.buffer.account = account
  self.name = name
  self.session = None
  self.needs_init = True

class baseBufferController(bufferController):
 def __init__(self, parent, function, name, sessionObject, account, sound=None, bufferType=None, *args, **kwargs):
  super(baseBufferController, self).__init__(parent, function, *args, **kwargs)
  log.debug("Initializing buffer %s, account %s" % (name, account,))
  if bufferType != None:
   self.buffer = getattr(buffers, bufferType)(parent, name)
  else:
   self.buffer = buffers.basePanel(parent, name)
  self.invisible = True
  self.name = name
  self.type = self.buffer.type
  self.id = self.buffer.GetId()
  self.session = sessionObject
  self.compose_function = compose.compose_tweet
  log.debug("Compose_function: %s" % (self.compose_function,))
  self.account = account
  self.buffer.account = account
  self.bind_events()
  self.sound = sound

 def get_formatted_message(self):
  if self.type == "dm" or self.name == "sent_tweets" or self.name == "sent_direct_messages":   return self.compose_function(self.get_right_tweet(), self.session.db, self.session.settings["general"]["relative_times"])[1]
  return self.get_message()

 def get_message(self):
  return " ".join(self.compose_function(self.get_right_tweet(), self.session.db, self.session.settings["general"]["relative_times"]))

 def start_stream(self):
  log.debug("Starting stream for buffer %s, account %s and type %s" % (self.name, self.account, self.type))
  log.debug("args: %s, kwargs: %s" % (self.args, self.kwargs))
  val = self.session.call_paged(self.function, *self.args, **self.kwargs)
  number_of_items = self.session.order_buffer(self.name, val)
  log.debug("Number of items retrieved: %d" % (number_of_items,))
  self.put_items_on_list(number_of_items)
  if self.sound == None: return
  if number_of_items > 0 and self.name != "sent_tweets" and self.name != "sent_direct_messages":
   self.session.sound.play(self.sound)

 def put_items_on_list(self, number_of_items):
  log.debug("The list contains %d items " % (self.buffer.list.get_count(),))
  log.debug("Putting %d items on the list" % (number_of_items,))
  if self.buffer.list.get_count() == 0:
   for i in self.session.db[self.name]:
    tweet = self.compose_function(i, self.session.db, self.session.settings["general"]["relative_times"])
    self.buffer.list.insert_item(False, *tweet)
   self.buffer.set_position(self.session.settings["general"]["reverse_timelines"])
#   self.buffer.set_list_position()
  elif self.buffer.list.get_count() > 0:
   if self.session.settings["general"]["reverse_timelines"] == False:
    for i in self.session.db[self.name][:number_of_items]:
     tweet = self.compose_function(i, self.session.db, self.session.settings["general"]["relative_times"])
     self.buffer.list.insert_item(False, *tweet)
   else:
    for i in self.session.db[self.name][0:number_of_items]:
     tweet = self.compose_function(i, self.session.db, self.session.settings["general"]["relative_times"])
     self.buffer.list.insert_item(True, *tweet)
  log.debug("Now the list contains %d items " % (self.buffer.list.get_count(),))

 def add_new_item(self, item):
  tweet = self.compose_function(item, self.session.db, self.session.settings["general"]["relative_times"])
  if self.session.settings["general"]["reverse_timelines"] == False:
   self.buffer.list.insert_item(False, *tweet)
  else:
   self.buffer.list.insert_item(True, *tweet)

 def bind_events(self):
  log.debug("Binding events...")
  self.buffer.list.list.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onFocus)
  self.buffer.list.list.Bind(wx.EVT_CHAR_HOOK, self.get_event)
  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.post_tweet, self.buffer.tweet)
#  if self.type == "baseBuffer":
  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.retweet, self.buffer.retweet)
  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.direct_message, self.buffer.dm)
  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.reply, self.buffer.reply)

 def get_tweet(self):
  if self.session.db[self.name][self.buffer.list.get_selected()].has_key("retweeted_status"):
   tweet = self.session.db[self.name][self.buffer.list.get_selected()]["retweeted_status"]
  else:
   tweet = self.session.db[self.name][self.buffer.list.get_selected()]
  return tweet

 def get_right_tweet(self):
  tweet = self.session.db[self.name][self.buffer.list.get_selected()]
  return tweet

 def reply(self, *args, **kwargs):
  tweet = self.get_right_tweet()
  screen_name = tweet["user"]["screen_name"]
  id = tweet["id"]
  users =  utils.get_all_mentioned(tweet, self.session.db)
  message = messages.reply(self.session, _(u"Reply"), _(u"Reply to %s") % (screen_name,), "@%s " % (screen_name,), users)
  if message.message.get_response() == widgetUtils.OK:
   if message.image == None:
    call_threaded(self.session.api_call, call_name="update_status", _sound="reply_send.ogg", in_reply_to_status_id=id, status=message.message.get_text())
   else:
    call_threaded(self.session.api_call, call_name="update_status_with_media", _sound="reply_send.ogg", in_reply_to_status_id=id, status=message.message.get_text(), media=message.file)

 def direct_message(self, *args, **kwargs):
  tweet = self.get_tweet()
  if self.type == "dm":
   screen_name = tweet["sender"]["screen_name"]
   users = utils.get_all_users(tweet, self.session.db)
  elif self.type == "people":
   screen_name = tweet["screen_name"]
   users = [screen_name]
  else:
   screen_name = tweet["user"]["screen_name"]
   users = utils.get_all_users(tweet, self.session.db)
  dm = messages.dm(self.session, _(u"Direct message to %s") % (screen_name,), _(u"New direct message"), users)
  if dm.message.get_response() == widgetUtils.OK:
   call_threaded(self.session.api_call, call_name="send_direct_message", text=dm.message.get_text(), screen_name=dm.message.get("cb"))

 def retweet(self, *args, **kwargs):
  tweet = self.get_right_tweet()
  id = tweet["id"]
  answer = commonMessageDialogs.retweet_question(self.buffer)
  if answer == widgetUtils.YES:
   retweet = messages.tweet(self.session, _(u"Retweet"), _(u"Add your comment to the tweet"), u"“@%s: %s ”" % (tweet["user"]["screen_name"], tweet["text"]))
   if retweet.message.get_response() == widgetUtils.OK:
    if retweet.image == None:
     call_threaded(self.session.api_call, call_name="update_status", _sound="retweet_send.ogg", status=retweet.message.get_text(), in_reply_to_status_id=id)
    else:
     call_threaded(self.session.api_call, call_name="update_status", _sound="retweet_send.ogg", status=retweet.message.get_text(), in_reply_to_status_id=id, media=retweet.image)
  elif answer == widgetUtils.NO:
   call_threaded(self.session.api_call, call_name="retweet", _sound="retweet_send.ogg", id=id)

 def onFocus(self, ev):
  tweet = self.get_tweet()
  if self.session.settings["general"]["relative_times"] == True:
   # fix this:
   original_date = arrow.get(self.session.db[self.name][self.buffer.list.get_selected()]["created_at"], "ddd MMM D H:m:s Z YYYY", locale="en")
   ts = original_date.humanize(locale=languageHandler.getLanguage())
   self.buffer.list.list.SetStringItem(self.buffer.list.get_selected(), 2, ts)
  if utils.is_audio(tweet):
   self.session.sound.play("audio.ogg")

 def audio(self):
  tweet = self.get_tweet()
  urls = utils.find_urls(tweet)
  if len(urls) == 1:
   sound.URLPlayer.play(urls[0])
  else:
   urls_list = dialogs.urlList.urlList()
   urls_list.populate_list(urls)
   if urls_list.get_response() == widgetUtils.OK:
    sound.URLPlayer.play(urls_list.get_string())

 def url(self):
  tweet = self.get_tweet()
  urls = utils.find_urls(tweet)
  if len(urls) == 1:
   output.speak(_(u"Opening URL..."))
   webbrowser.open_new_tab(urls[0])
  elif len(urls) > 1:
   urls_list = dialogs.urlList.urlList()
   urls_list.populate_list(urls)
   if urls_list.get_response() == widgetUtils.OK:
    output.speak(_(u"Opening URL..."))
    webbrowser.open_new_tab(urls_list.get_string())

 def clear_list(self):
  dlg = wx.MessageDialog(None, _(u"Do you really want to empty this buffer? It's tweets will be removed from the list but not from Twitter"), _(u"Empty buffer"), wx.ICON_QUESTION|wx.YES_NO)
  if dlg.ShowModal() == widgetUtils.YES:
   self.session.db[self.name] = []
   self.buffer.list.clear()
  dlg.Destroy()

 def destroy_status(self, *args, **kwargs):
  index = self.buffer.list.get_selected()
  if self.type == "events" or self.type == "people" or self.type == "empty" or self.type == "account": return
  answer = commonMessageDialogs.delete_tweet_dialog(None)
  if answer == widgetUtils.YES:
#   try:
   if self.name == "direct_messages":
    self.session.twitter.twitter.destroy_direct_message(id=self.get_right_tweet()["id"])
   else:
    self.session.twitter.twitter.destroy_status(id=self.get_right_tweet()["id"])
   self.session.db[self.name].pop(index)
   self.buffer.list.remove_item(index)
   if index > 0:
    self.buffer.list.select_item(index-1)
#   except TwythonError:
#    sound.player.play("error.ogg")

class eventsBufferController(bufferController):
 def __init__(self, parent, name, session, account, *args, **kwargs):
  super(eventsBufferController, self).__init__(parent, *args, **kwargs)
  log.debug("Initializing buffer %s, account %s" % (name, account,))
  self.invisible = True
  self.buffer = buffers.eventsPanel(parent, name)
  self.name = name
  self.account = account
  self.id = self.buffer.GetId()
  self.buffer.account = self.account
  self.compose_function = compose.compose_event
  self.session = session
  self.type = self.buffer.type
  self.get_formatted_message = self.get_message

 def get_message(self):
  if self.buffer.list.get_count() == 0: return _(u"Empty")
  # fix this:
  return "%s. %s" % (self.buffer.list.list.GetItemText(self.buffer.list.get_selected()), self.buffer.list.list.GetItemText(self.buffer.list.get_selected(), 1))

 def add_new_item(self, item):
  tweet = self.compose_function(item, self.session.db["user_name"])
  if self.session.settings["general"]["reverse_timelines"] == False:
   self.buffer.list.insert_item(False, *tweet)
  else:
   self.buffer.list.insert_item(True, *tweet)

class peopleBufferController(baseBufferController):
 def __init__(self, parent, function, name, sessionObject, account, bufferType=None, *args, **kwargs):
  super(peopleBufferController, self).__init__(parent, function, name, sessionObject, account, bufferType="peoplePanel")
  log.debug("Initializing buffer %s, account %s" % (name, account,))
  self.compose_function = compose.compose_followers_list
  log.debug("Compose_function: %s" % (self.compose_function,))
  self.get_tweet = self.get_right_tweet

 def onFocus(self, ev):
  pass

 def get_message(self):
  return " ".join(self.compose_function(self.get_tweet(), self.session.db, self.session.settings["general"]["relative_times"]))

 def delete_item(self): pass

 def start_stream(self):
  log.debug("Starting stream for %s buffer, %s account" % (self.name, self.account,))
  log.debug("args: %s, kwargs: %s" % (self.args, self.kwargs))
  val = self.session.get_cursored_stream(self.name, self.function, *self.args, **self.kwargs)
#  self.session.order_cursored_buffer(self.name, self.session.db[self.name])
#  log.debug("Number of items retrieved:  %d" % (val,))
  self.put_items_on_list(val)

 def put_items_on_list(self, number_of_items):
  log.debug("The list contains %d items" % (self.buffer.list.get_count(),))
#  log.debug("Putting %d items on the list..." % (number_of_items,))
  if self.buffer.list.get_count() == 0:
   for i in self.session.db[self.name]["items"]:
    tweet = self.compose_function(i, self.session.db, self.session.settings["general"]["relative_times"])
    self.buffer.list.insert_item(False, *tweet)
   self.buffer.set_position(self.session.settings["general"]["reverse_timelines"])
#   self.buffer.set_list_position()
  elif self.buffer.list.get_count() > 0:
   if self.session.settings["general"]["reverse_timelines"] == False:
    for i in self.session.db[self.name]["items"][:number_of_items]:
     tweet = self.compose_function(i, self.session.db)
     self.buffers.list.insert_item(False, *tweet)
   else:
    for i in self.session.db[self.name]["items"][0:number_of_items]:
     tweet = self.compose_function(i, self.session.db)
     self.buffer.list.insert_item(True, *tweet)
  log.debug("now the list contains %d items" % (self.buffer.list.get_count(),))

 def get_right_tweet(self):
  tweet = self.session.db[self.name]["items"][self.buffer.list.get_selected()]
  return tweet

 def add_new_item(self, item):
  self.session.db[self.name]["items"].append(item)
  tweet = self.compose_function(item, self.session.db, self.session.settings["general"]["relative_times"])
  if self.session.settings["general"]["reverse_timelines"] == False:
   self.buffer.list.insert_item(False, *tweet)
  else:
   self.buffer.list.insert_item(True, *tweet)

class searchBufferController(baseBufferController):
 def start_stream(self):
  log.debug("Starting stream for %s buffer, %s account and %s type" % (self.name, self.account, self.type))
  log.debug("args: %s, kwargs: %s" % (self.args, self.kwargs))
  log.debug("Function: %s" % (self.function,))
  val = getattr(self.session.twitter.twitter, self.function)(*self.args, **self.kwargs)
  number_of_items = self.session.order_buffer(self.name, val["statuses"])
  log.debug("Number of items retrieved: %d" % (number_of_items,))
  self.put_items_on_list(number_of_items)
  if number_of_items > 0:
   self.session.sound.play("search_updated.ogg")

class searchPeopleBufferController(searchBufferController):

 def __init__(self, parent, function, name, sessionObject, account, bufferType="peoplePanel", *args, **kwargs):
  super(searchPeopleBufferController, self).__init__(parent, function, name, sessionObject, account, bufferType="peoplePanel", *args, **kwargs)
  log.debug("Initializing buffer %s, account %s" % (name, account,))
  self.compose_function = compose.compose_followers_list
  log.debug("Compose_function: %s" % (self.compose_function,))

 def start_stream(self):
  log.debug("starting stream for %s buffer, %s account and %s type" % (self.name, self.account, self.type))
  log.debug("args: %s, kwargs: %s" % (self.args, self.kwargs))
  log.debug("Function: %s" % (self.function,))
  val = getattr(self.session.twitter.twitter, self.function)(*self.args, **self.kwargs)
  number_of_items = self.session.order_buffer(self.name, val)
  log.debug("Number of items retrieved: %d" % (number_of_items,))
  self.put_items_on_list(number_of_items)
  if number_of_items > 0:
   self.session.sound.play("search_updated.ogg")

class trendsBufferController(bufferController):
 def __init__(self, parent, name, session, account, trendsFor, *args, **kwargs):
  super(trendsBufferController, self).__init__(parent=parent, session=session)
  self.trendsFor = trendsFor
  self.session = session
  self.account = account
  self.invisible = True
  self.buffer = buffers.trendsPanel(parent, name)
  self.buffer.account = account
  self.type = self.buffer.type
  self.bind_events()
  self.sound = "trends_updated.ogg"
  self.trends = []
  self.name = name
  self.buffer.name = name
  self.compose_function = self.compose_function_
  self.get_formatted_message = self.get_message

 def start_stream(self):
  data = self.session.twitter.twitter.get_place_trends(id=self.trendsFor)
  if not hasattr(self, "name"):
   self.name = data[0]["locations"][0]["name"]
  self.trends = data[0]["trends"]
  self.put_items_on_the_list()
  self.session.sound.play(self.sound)

 def put_items_on_the_list(self):
  selected_item = self.buffer.list.get_selected()
  self.buffer.list.clear()
  for i in self.trends:
   tweet = self.compose_function(i)
   self.buffer.list.insert_item(False, *tweet)
  self.buffer.list.select_item(selected_item)

 def compose_function_(self, trend):
  return [trend["name"]]

 def bind_events(self):
  log.debug("Binding events...")
  self.buffer.list.list.Bind(wx.EVT_CHAR_HOOK, self.get_event)
#  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.post_tweet, self.buffer.tweet)
#  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.retweet, self.buffer.retweet)
#  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.direct_message, self.buffer.dm)
#  widgetUtils.connect_event(self.buffer, widgetUtils.BUTTON_PRESSED, self.reply, self.buffer.reply)

 def get_message(self):
  return self.compose_function(self.trends[self.buffer.list.get_selected()])[0]

