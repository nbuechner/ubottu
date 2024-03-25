# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2006-2007 Dennis Kaarsemaker
# Copyright (c) 2008-2010 Terence Simpson
# Copyright (c) 2017-     Krytarik Raido
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
###

import warnings
warnings.filterwarnings("ignore", "apt API not stable yet", FutureWarning)
import subprocess, os, apt, re
#import supybot.utils as utils
from email.parser import FeedParser

def component(arg):
    if '/' in arg:
        return arg[:arg.find('/')]
    return 'main'

def description(pkg):
    if 'Description-en' in pkg:
        return pkg['Description-en'].split('\n')[0]
    elif 'Description' in pkg:
        return pkg['Description'].split('\n')[0]
    return "Description not available"

class Apt:
    def __init__(self):
        self.aptdir = os.path.expanduser('~') + '/apt-data'
        self.distros = []
        #self.plugin = "plugin"
        #self.log = "apt.log"
        os.environ["LANG"] = "C.UTF-8"
        if self.aptdir:
            self.distros = sorted([x[:-5] for x in os.listdir(self.aptdir) if x.endswith('.list')])

    def apt_cache(self, distro, cmd, pkg):
        return subprocess.check_output(['apt-cache',
            '-oAPT::Architecture=amd64',
            '-oAPT::Architectures::=i386',
            '-oAPT::Architectures::=amd64',
            '-oDir::State::Lists=%s/%s' % (self.aptdir, distro),
            '-oDir::State::Status=%s/%s.status' % (self.aptdir, distro),
            '-oDir::Etc::SourceList=%s/%s.list' % (self.aptdir, distro),
            '-oDir::Etc::SourceParts=""',
            '-oDir::Cache=%s/cache' % self.aptdir] +
            cmd + [pkg.lower()]).decode('utf-8')

    def apt_file(self, distro, pkg):
        return subprocess.check_output(['apt-file',
            '-oAPT::Architecture=amd64',
            '-oAPT::Architectures::=i386',
            '-oAPT::Architectures::=amd64',
            '-oDir::State::Lists=%s/%s' % (self.aptdir, distro),
            '-oDir::State::Status=%s/%s.status' % (self.aptdir, distro),
            '-oDir::Etc::SourceList=%s/%s.list' % (self.aptdir, distro),
            '-oDir::Etc::SourceParts=""',
            '-oDir::Cache=%s/cache' % self.aptdir,
            '-l', '-i', 'search', pkg]).decode('utf-8')

    def _parse(self, pkg):
        parser = FeedParser()
        parser.feed(pkg)
        return parser.close()

    def find(self, pkg, distro, filelookup=True):
        if distro.split('-')[0] in ('oldstable', 'stable', 'unstable', 'testing', 'experimental'):
            pkgTracURL = "https://packages.debian.org"
        else:
            pkgTracURL = "https://packages.ubuntu.com"

        try:
            data = self.apt_cache(distro, ['search', '-n'], pkg)
        except subprocess.CalledProcessError as e:
            data = e.output
        if not data:
            if filelookup:
                try:
                    data = self.apt_file(distro, pkg).split()
                except subprocess.CalledProcessError as e:
                    if e.returncode == 1:
                        return 'Package/file %s does not exist in %s' % (pkg, distro)
                    #self.log.error("PackageInfo/packages: Please update the cache for %s" % distro)
                    return "Cache out of date, please contact the administrator"
                except OSError:
                    #self.log.error("PackageInfo/packages: apt-file is not installed")
                    return "Please use %s/ to search for files" % pkgTracURL
                if data:
                    if len(data) > 10:
                        return "File %s found in %s and %d others <%s/search?searchon=contents&keywords=%s&mode=exactfilename&suite=%s&arch=any>" % (pkg, ', '.join(data[:10]), len(data)-10, pkgTracURL, utils.web.urlquote(pkg), distro)
                    return "File %s found in %s" % (pkg, ', '.join(data))
                return 'Package/file %s does not exist in %s' % (pkg, distro)
            return "No packages matching '%s' could be found" % pkg
        pkgs = [x.split()[0] for x in data.split('\n') if x]
        if len(pkgs) > 10:
            return "Found: %s and %d others <%s/search?keywords=%s&searchon=names&suite=%s&section=all>" % (', '.join(pkgs[:10]), len(pkgs)-10, pkgTracURL, utils.web.urlquote(pkg), distro)
        else:
            return "Found: %s" % ', '.join(pkgs)

    def raw_info(self, pkg, distro, isSource, archlookup=True):
        try:
            data = self.apt_cache(distro, ['show'] if not isSource else ['showsrc', '--only-source'], pkg)
        except subprocess.CalledProcessError:
            data = ''
        if not data:
            return 'Package %s does not exist in %s' % (pkg, distro)

        maxp = {'Version': '0~'}
        packages = list(map(self._parse, [x for x in data.split('\n\n') if x]))
        for p in packages:
            if apt.apt_pkg.version_compare(maxp['Version'], p['Version']) <= 0:
                maxp = p

        if isSource:
            bdeps = maxp.get('Build-Depends')
            vcs = maxp.get('Vcs-Browser')
            for (key, value) in list(maxp.items()):
                if key.startswith('Build-Depends-'):
                    bdeps = "%s, %s" % (bdeps, value) if bdeps else value
                elif key.startswith('Vcs-') and not vcs:
                    vcs = "%s (%s)" % (value, key[4:])
            maxp['Builddeps'] = bdeps
            maxp['Vcs'] = vcs
            return maxp

        if not maxp.get('Source'):
            maxp['Sourcepkg'] = maxp['Package']
        else:
            maxp['Sourcepkg'] = maxp['Source'].split()[0]

        if not archlookup:
            return maxp

        try:
            data2 = self.apt_cache(distro, ['showsrc', '--only-source'], maxp['Sourcepkg'])
        except subprocess.CalledProcessError:
            data2 = ''
        if not data2:
            return maxp

        maxp2 = {'Version': '0~'}
        packages2 = list(map(self._parse, [x for x in data2.split('\n\n') if x]))
        for p in packages2:
            if apt.apt_pkg.version_compare(maxp2['Version'], p['Version']) <= 0:
                maxp2 = p

        archs = re.match(r'.*^ %s \S+ \S+ \S+ arch=(?P<arch>\S+)$' % re.escape(pkg), maxp2['Package-List'],
                         re.I | re.M | re.DOTALL)
        if archs:
            archs = archs.group('arch').split(',')
            if not ('any' in archs or 'all' in archs):
                maxp['Architectures'] = ', '.join(archs)

        return maxp

    def info(self, pkg, distro, isSource):
        maxp = self.raw_info(pkg, distro, isSource)
        if isinstance(maxp, str):
            return maxp
        if isSource:
            return "%s (%s, %s): Packages %s. Maintained by %s%s" % (
                maxp['Package'], maxp['Version'], distro, maxp['Binary'].replace('\n',''),
                re.sub(r' <\S+>$', '', maxp.get('Original-Maintainer', maxp['Maintainer'])),
                " @ %s" % maxp['Vcs'] if maxp['Vcs'] else "")
        return "{} ({}, {}): {}. In component {}, is {}. Built by {}. Size {:,} kB / {:,} kB{}".format(
            maxp['Package'], maxp['Version'], distro, description(maxp), component(maxp['Section']),
            maxp['Priority'], maxp['Sourcepkg'], int((int(maxp['Size'])/1024)+1), int(maxp['Installed-Size']),
            ". (Only available for %s.)" % maxp['Architectures'] if maxp.get('Architectures') else "")

    def depends(self, pkg, distro, isSource):
        maxp = self.raw_info(pkg, distro, isSource, archlookup=False)
        if isinstance(maxp, str):
            return maxp
        if isSource:
            return "%s (%s, %s): Build depends on %s" % (
                maxp['Package'], maxp['Version'], distro, maxp.get('Builddeps', "nothing").replace('\n',''))
        return "%s (%s, %s): Depends on %s%s" % (
            maxp['Package'], maxp['Version'], distro, maxp.get('Depends', "nothing").replace('\n',''),
            ". Recommends %s" % maxp['Recommends'].replace('\n','') if maxp.get('Recommends') else "")

# Simple test
if __name__ == "__main__":
    import sys
    argv = sys.argv
    argc = len(argv)
    if argc == 1:
        print("Need at least one arg")
        sys.exit(1)
    if argc > 3:
        print("Only takes 2 args")
        sys.exit(1)
    class FakePlugin:
        class FakeLog:
            def error(*args, **kwargs):
                pass
        def __init__(self):
            self.log = self.FakeLog()
        def registryValue(self, *args, **kwargs):
            return os.path.expanduser('~') + '/apt-data'

    try:
        (command, lookup) = argv[1].split(None, 1)
    except:
        print("Need something to look up")
        sys.exit(1)
    dist = "noble"
    if argc == 3:
        dist = argv[2]
    plugin = FakePlugin()
    aptlookup = Apt(plugin)
    print(getattr(aptlookup, command)(lookup, dist))
