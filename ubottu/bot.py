import json
import os
import re
import requests
import traceback
from time import time
from typing import Type, Tuple
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command
import mautrix.util
from mautrix.types import (
    EventType,
    MemberStateEventContent,
    PowerLevelStateEventContent,
    RoomID,
    RoomAlias,
    StateEvent,
    UserID,
)
from mautrix.errors import MForbidden
from aiohttp.web import Request, Response, json_response
from pathlib import Path
from urllib.parse import urlparse, unquote
from .floodprotection import FloodProtection
from .packages import Apt
from launchpadlib.launchpad import Launchpad

ubottu_change_level = EventType.find("com.ubuntu.ubottu", t_class=EventType.Class.STATE)

class Config(BaseProxyConfig):
  def do_update(self, helper: ConfigUpdateHelper) -> None:
    helper.copy("whitelist")
    helper.copy("rooms")

class Ubottu(Plugin):
  power_level_cache: dict[RoomID, tuple[int, PowerLevelStateEventContent]]

  async def get_power_levels(self, room_id: RoomID) -> PowerLevelStateEventContent:
        try:
            expiry, levels = self.power_level_cache[room_id]
            if expiry < int(time()):
                return levels
        except KeyError:
            self.log.info(f"Cache miss for {room_id}")
            pass
        levels = await self.client.get_state_event(room_id, EventType.ROOM_POWER_LEVELS)
        #self.log.info(f"Levels: {levels}")
        if levels:
          now = int(time())
          self.power_level_cache[room_id] = (now + 5 * 60, levels)
          return levels
        return False

  async def can_manage(self, evt: MessageEvent) -> bool:
    if evt.sender in self.config["whitelist"]:
        return True
    levels = await self.get_power_levels(evt.room_id)
    user_level = levels.get_user_level(evt.sender)
    state_level = levels.get_event_level(ubottu_change_level)
    if not isinstance(state_level, int):
        state_level = 50
    if user_level < state_level:
        return False
    return True
  
  async def get_room_mods_and_admins(self, evt: MessageEvent) -> list:
    high_level_user_ids = []  # Initialize an empty list to store user IDs
    try:
        # Fetch the state of the room, focusing on power levels
        levels = await self.get_power_levels(evt.room_id)
        for user_id, level in levels.users.items():
          if level >= 50:
            high_level_user_ids.append(user_id)
          else:
            self.log.info("No power levels found in {evt.room_id}")
    except Exception as e:
        print(f"Failed to access room state: {e}")
        self.log.info(f"Failed to access room state: {e}")
        self.log.info(f"Failed to access room state: {traceback.print_exc()}")
        # Optionally, handle the error more gracefully here (e.g., by logging or by returning an error message)
    return high_level_user_ids

  def sanitize_string(self, input_string):
    # Pattern includes single quotes, double quotes, semicolons, and common SQL comment markers
    pattern = r"[\'\";]|(--)|(/\*)|(\*/)"
    # Replace the identified patterns with an empty string
    safe_string = re.sub(pattern, '', input_string)
    return safe_string

  async def pre_start(self) -> None:
    return True

  async def start(self) -> None:
    self.config.load_and_update()
    self.flood_protection = FloodProtection()
    self.power_level_cache = {}

  def check_access(self, sender, room_id):
      if sender in self.config["whitelist"] and room_id in self.config["rooms"]:
         return True
      return False
  def check_access_sender(self, sender):
      if sender in self.config["whitelist"]:
         return True
      return False

  #@command.new(name="email", aliases=["json"])
  @command.new(name="jsontest", aliases=["json"])
  async def email(self, evt: MessageEvent) -> None:
    if self.check_access(evt.sender, evt.room_id):
      url='https://xentonix.net/test.json'
      resp = await self.http.get(url)
      if resp.status == 200:
        data = await resp.json()
        #print(data)
        await evt.reply(data['employees'][0]['email'])

  async def lookup_launchpad_bug(self, bug_id):
    url = 'http://127.0.0.1:8000/bugtracker/api/bugtracker/launchpad/' + str(bug_id) + '/'
    resp = await self.http.get(url)
    if resp.status == 200:
      data = await resp.json()
      return data
    return False

  async def lookup_github_bug(self, owner, project, bug_id):
    url = 'http://127.0.0.1:8000/bugtracker/api/bugtracker/github/' + owner + '/' + project + '/' + str(bug_id) + '/'
    resp = await self.http.get(url)
    if resp.status == 200:
      data = await resp.json()
      return data
    return False

  async def lookup_factoid(self, command_name, to_user, evt):
      api_url = 'http://127.0.0.1:8000/factoids/api/facts/'
      url = api_url + command_name + '/?format=json'
      resp = await self.http.get(url)
      if resp and resp.status == 200:
        data = await resp.json()
        if data:
          id = data['id']
          name = data['name']
          value = data['value']
          ftype = data['ftype']
          user_ids = data['user_ids']
          if ftype == 'ALIAS':
            command_name = value
            url = api_url + command_name + '/?format=json'
            resp = await self.http.get(url)
            if resp and resp.status == 200:
              data = await resp.json()
              value = data['value']

          # if factoid is room specific check and only reply in this room
          room = data['room']
          if room is not None and room != evt.room_id:
            return False
        
          content = {}
          content['m.mentions'] = {}
          moderators = []
          mentions = 0
          m_str = ''
          m_str_html = ''
          user_ids = []
          value = data['value']
          formatted_value = value

          if '.mentions' in value:
            value = value.replace('.mentions', '')
            mentions = 1
            
          #find matrix user ids in message
          user_id_re = '@[\w.-]+:[a-zA-Z\d.-]+\.[a-zA-Z]{2,}'
          user_ids = re.findall(user_id_re, value)
          if len(user_ids) > 0:
            for user_id in user_ids:
              formatted_value = formatted_value.replace(user_id, '<a href="https://matrix.to/#/' + user_id + '">' + user_id + '</a>')

          #find room moderators and add to mentions if needed
          if '{moderators}' in value:
            moderators = await self.get_room_mods_and_admins(evt)
            if mentions == 1:
              value = value.replace('{moderators}', '')
              
            formatted_value = value

            if mentions == 0:
              for m in moderators:
                m_str_html = "<a href='https://matrix.to/#/'>" + m + '</a> ' + m_str_html
                m_str = m_str + ' ' + m
              value = value.replace('{moderators}', m_str)
              formatted_value = formatted_value.replace('{moderators}', m_str_html)

          value = re.sub(' +', ' ', value)

          content['m.mentions']['user_ids'] = list(set(list(moderators) + list(data['user_ids'])))
          self.log.info(content['m.mentions']['user_ids'])
          content['formatted_body'] = mautrix.util.markdown.render(formatted_value, allow_html=True)
          content['msgtype'] = "m.text"
          content['format'] = 'org.matrix.custom.html'
          content['body'] = value
          if to_user:
            content['body'] = to_user + ': ' + value
            content['formatted_body'] = to_user + ': ' + mautrix.util.markdown.render(formatted_value, allow_html=True)
          
          await evt.respond(content)
          return True
      return False
  
  @command.passive("LP.? #?(\d+)|bug #?(\d+)|https?:\/\/bugs\.launchpad\.net\/[^\d]*(\d+)")
  async def command_launchpad_bug(self, evt: MessageEvent, match: Tuple[str]) -> None:
    if match:
        if match[1]:
          bug_id = match[1]
        if match[2]:
          bug_id = match[2]
    if int(bug_id) < 1000:
      return False
    if self.flood_protection.flood_check_bug(bug_id) and self.flood_protection.flood_check(evt.sender):
        data = await self.lookup_launchpad_bug(bug_id)
        if data:
            package = ''
            if data['package'] != '':
              package = ' in ' + data['package']
            msg = f"Launchpad Bug [#{data['id']}]({data['link']}){package} \"{data['title']}\" [{data['importance']}, {data['status']}]"
            await evt.respond(msg)
            return True
    return False

  @command.passive("https:\/\/github\.com\/([^\/]+)\/([^\/]+)\/issues\/(\d+)")
  async def command_github_bug(self, evt: MessageEvent, match: Tuple[str]) -> None:
    owner = match[1]
    project  = match[2]
    issue_id = match[3]
  
    if self.flood_protection.flood_check_bug(issue_id) and self.flood_protection.flood_check(evt.sender):
        data = await self.lookup_github_bug(owner, project, issue_id)
        if data:
            issue_url = f"https://github.com/{data['project']}/issues/{data['id']}"
            project_url = f"https://github.com/{data['project']}"
            msg = f"GitHub Issue [#{data['id']}]({issue_url}) in [{data['project']}]({project_url}) \"{data['description']}\" [{data['state']}]"
            await evt.respond(msg)
            return True
    return False

  @command.passive("^!(.+)$")
  async def command_e(self, evt: MessageEvent, match: Tuple[str]) -> None:
    # allow all rooms and users, only enable flood protection
    #if self.check_access(evt.sender, evt.room_id):
    if self.flood_protection.flood_check(evt.sender):
      args = []
      to_user = ''
      command_name = self.sanitize_string(match[0][1:].split(' ')[0])
      full_command = re.sub(r'\s+', ' ', match[0][1:])
      if full_command.count('|') > 0:
        to_user = self.sanitize_string(full_command.split('|')[1].strip())
        args = full_command.split('|')[0].strip().split(' ')[1:]
      else:
        args = full_command.strip().split(' ')[1:]
      
      #block !tr factoid to allow translation
      if command_name == 'tr':
        return False
        
      #reload stuff
      if command_name == 'reload' and self.check_access_sender(evt.sender):
        if self.pre_start():
          await evt.respond('Reload completed')
        else:
          await evt.respond('Reload failed')
        return True

      if command_name == 'time' or command_name == 'utc':
        if command_name == 'utc':
          city = 'UTC'
        else:
          city = " ".join(args)
        api_url = 'http://127.0.0.1:8000/factoids/api/citytime/' + city + '/?format=json'
        resp = await self.http.get(api_url)
        if resp and resp.status == 200:
          data = await resp.json()
          if data:
            if city == 'UTC':
              await evt.respond('The current UTC time is ' + data['local_time'])
            else:
              await evt.respond('The current time in ' + data['location'] + ' is ' + data['local_time'] + ' ' + data['utc_offset'])

      if command_name == 'lpbug' or command_name == 'lp':
        if len(args) == 1:
          package = ''
          bug_id = int(args[0])
          data = await self.lookup_launchpad_bug(bug_id)
          if data:
            if data['package'] != '':
              package = ' in ' + '[' + data['package'] + '](' + data['target_link'] + ')'           
            msg = f"Launchpad Bug [#{data['id']}]({data['link']}){package} \"{data['title']}\" [{data['importance']}, {data['status']}]"
            await evt.respond(msg)
            
        return False

      #package lookup command
      if command_name == 'package' or command_name == 'depends':
        apt = Apt()
        if len(args) == 0:
          return False
        if len(args) == 1:
          if command_name == 'depends':
            await evt.respond(apt.depends(args[0], 'noble', False))
          else:
            await evt.respond(apt.info(args[0], 'noble', False))
          return True
        if len(args) == 2:
          if args[1] in ['jammy', 'noble', 'oracular', 'focal', 'plucky']:
            if command_name == 'depends':
              await evt.respond(apt.info(args[0], args[1], False))
            else:
              await evt.respond(apt.depends(args[0], args[1], False))
            return True
        return False

      if await self.lookup_factoid(command_name, to_user, evt):
        return True
  @classmethod
  def get_config_class(cls) -> Type[BaseProxyConfig]:
    return Config