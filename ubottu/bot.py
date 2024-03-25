import json
import sqlite3
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
    #if await self.get_ubottu_db('https://ubottu.com/ubuntu3.db'):
    #  self.db = sqlite3.connect("/home/maubot/.ubottu/ubuntu3.db")
    #else:
    #  return False
    return True

  async def start(self) -> None:
    self.config.load_and_update()
    self.flood_protection = FloodProtection()
    
  async def get_ubottu_db(self, url):
    """Load a file from a URL into an in-memory filesystem."""
    # Create a filename if required
    u = urlparse(url)
    fn = "/home/maubot/.ubottu/" + os.path.basename(u.path)
    #if os.path.isfile(fn):
    #  return fn
    requests.packages.urllib3.util.connection.HAS_IPV6 = False
    with requests.get(url, stream=True) as r:
        r.raise_for_status()  # Checks if the request was successful
        # Open the local file in binary write mode
        with open(fn, 'wb+') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                # If you have a chunk of data, write it to the file
                if chunk:
                    f.write(chunk)
        f.close()
    return fn

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
  
  async def lookup_factoid_irc(self, command_name, to_user, evt):
      sql = "SELECT value FROM facts where name = '" + command_name + "' LIMIT 1"
      db = self.db
      cur = db.cursor()
      cur.execute(sql)
      rows = cur.fetchall()
      row = None
      for row in rows:
        if row[0].startswith('<alias>'):
          command_name = str(row[0]).replace('<alias> ', '')
          sql = "SELECT value FROM facts where name = '" + command_name + "' LIMIT 1"
          cur.execute(sql)
          rows = cur.fetchall()
          for row in rows:
            break
          break
      if row is not None and row[0].startswith('<reply>'):
        output = str(row[0]).replace('<reply> ', '')
        if to_user:
          await evt.respond(to_user + ': ' + output)
        else:
          await evt.respond(output)
        return True
      return False

  async def lookup_factoid_matrix(self, command_name, to_user, evt):
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

  @command.passive("^!(.+)$")
  async def command(self, evt: MessageEvent, match: Tuple[str]) -> None:
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
      
      #reload stuff
      if command_name == 'reload' and self.check_access_sender(evt.sender):
        if self.pre_start():
          await evt.respond('Reload completed')
        else:
          await evt.respond('Reload failed')
        return True

      #block !tr factoid to allow translation
      if command_name == 'tr':
        return False

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

      # check for factoids IRC
      #if await self.lookup_factoid_irc(command_name, to_user, evt):
      #  return True
      # check for factoids matrix
      if await self.lookup_factoid_matrix(command_name, to_user, evt):
        return True
  @classmethod
  def get_config_class(cls) -> Type[BaseProxyConfig]:
    return Config