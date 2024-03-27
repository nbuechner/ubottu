import json
import os
import re
import requests
from typing import Type, Tuple
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from aiohttp.web import Request, Response, json_response
from pathlib import Path
from urllib.parse import urlparse, unquote
from .floodprotection import FloodProtection
from .packages import Apt
from launchpadlib.launchpad import Launchpad

class Config(BaseProxyConfig):
  def do_update(self, helper: ConfigUpdateHelper) -> None:
    helper.copy("whitelist")
    helper.copy("rooms")

class Ubottu(Plugin):

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
          if ftype == 'ALIAS':
            command_name = value
            url = api_url + command_name + '/?format=json'
            resp = await self.http.get(url)
            if resp and resp.status == 200:
              data = await resp.json()
              value = data['value']
          if to_user:
            await evt.respond(to_user + ': ' + value)
          else:
            await evt.respond(value)
          return True
      return False
  
  @command.passive("bug #?(\d+)|https?:\/\/bugs\.launchpad\.net\/.+/(\d+)")
  async def command_bug(self, evt: MessageEvent, match: Tuple[str]) -> None:
    if match:
        if match[1]:
          bug_id = match[1]
        if match[2]:
          bug_id = match[2] 
    if self.flood_protection.flood_check_bug(bug_id) and self.flood_protection.flood_check(evt.sender):
        data = await self.lookup_launchpad_bug(bug_id)
        if data:
            if data['package'] != '':
              package = ' in ' + '[' + data['package'] + '](' + data['target_link'] + ')'           
            msg = f"Launchpad Bug [#{data['id']}]({data['link']}){package} \"{data['title']}\" [{data['importance']}, {data['status']}]"
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
          city = 'London'
        else:
          city = " ".join(args)
        api_url = 'http://127.0.0.1:8000/factoids/api/citytime/' + city + '/?format=json'
        resp = await self.http.get(api_url)
        if resp and resp.status == 200:
          data = await resp.json()
          if data:
            await evt.respond('The current time in ' + data['location'] + ' is ' + data['local_time'])

      if command_name == 'bug':
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

      #!package lookup command
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
          if args[1] in ['jammy', 'noble', 'mantic']:
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