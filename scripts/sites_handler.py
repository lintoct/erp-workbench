#!bin/python
# -*- encoding: utf-8 -*-
import warnings
import sys
import os
import logging
import re
from pprint import pformat
import subprocess
from subprocess import PIPE
from copy import deepcopy
#from config.config_data.base_info import base_info as BASE_INFO
from config import BASE_INFO
from config import ACT_USER
from config.config_data.servers_info import REMOTE_SERVERS
from scripts.messages import *
from scripts.bcolors import bcolors
from importlib import reload
from config import BASE_INFO, PROJECT_DEFAULTS, DOCKER_DEFAULTS

class UpdateError(subprocess.CalledProcessError):
    """Specific class for errors occurring during updates of existing repos.
    """

# --------------------------------------
# sites_handler.py maintains two set of data
# 1. local_data.py
#   this file contains info about the local user,
#   like with what credentials she/he will be accessing local and remote data
#   if it does not exist, it will be copied from templates
#   and must be editted afterwards
#
# 2. sites_global/*.py and sites_local/*.py.py
#   ssites_global contains descriptions of of sites. they are ment to be
#   maintained in a remote repo
#   sites_local1 contain the same list of site descriptions.
#   However they will be only handeled on the local computer.

# -------------------------------------------------------------
# the marker is used to place a new site when the file is updated
# -------------------------------------------------------------
# defined in messages.py
#MARKER = '# ---------------- marker ----------------'
SITES_LIST_INI ="""from .sites_local import SITES_L
from .sites_global import SITES_G
"""
SITES_LIST_OUTER_HEAD = """
SITES_G = {}
SITES_L = {}
def set_orig(dic, orig):
    for k,v in list(dic.items()):
        v['site_list_name'] = orig
"""
SITES_LIST_OUTER_LINE = """
from .%(file_name)s import SITES_G as SG_%(file_name)s
set_orig(SG_%(file_name)s, '%(file_name)s')
SITES_G.update(SG_%(file_name)s)
from .%(file_name)s import SITES_L as SL_%(file_name)s
set_orig(SL_%(file_name)s, '%(file_name)s')
SITES_L.update(SL_%(file_name)s)
"""

class SitesHandler(object):
    def __init__(self, base_path, template_name='', preset_values=''):
        self.base_path = base_path
        #self.check_and_copy_local_data()
        self.template_name = template_name
        self.preset_values = preset_values

    def _create_sites_rep(self, running_path):
        """
        create sites_list structure
        @p1 : base path 
        return:
        must_exit  : flag whether calling process should exit
        """
        bp = '/' + '/'.join([p for p in running_path.split('/') if p][:-1])
        if not os.path.exists(bp):
            print(LOCALSITESLIST_BASEPATH_MISSING % bp)
        p1 = running_path
        is_localhost = running_path.endswith('localhost')
        # there could be a siteslist folder existing but without
        # the its inner structure (how??, but it happens!)
        must_create = False
        did_change = False
        for n in ['__init__.py', 'sites_global', 'sites_local']:
            if not os.path.exists(os.path.normpath('%s/%s' % (p1, n))):
                must_create = True
                break
        if not os.path.exists(p1) or must_create:
            os.makedirs(p1, exist_ok=True)
            # add __init__.py
            ini_p = '%s/__init__.py' % p1
            if not os.path.exists(ini_p):
                open(ini_p, 'w').write(SITES_LIST_INI)
            template = open('%s/templates/newsite.py' % self.base_path, 'r').read()
            template = template.replace('xx.xx.xx.xx', 'localhost')
            # default values for the demo sites
            defaults = {
                'site_name' : 'demo_global', 
                'marker' : self.marker,
                'base_sites_home' : '/home/%s/erp_workbench' % ACT_USER,
                'erp_provider' : PROJECT_DEFAULTS.get('erp_provider', 'odoo'),
                'erp_version': PROJECT_DEFAULTS.get('erp_version', PROJECT_DEFAULTS.get('odoo_version', '12')),
                'erp_minor' : PROJECT_DEFAULTS.get('erp_minor', '12'),
                'erp_nightly' : PROJECT_DEFAULTS.get('erp_nightly', '12'),
                'base_url' : 'demo_global',
                'local_user_mail' : 'mail@localhost.com',
                'remote_server' : 'localhost',
                'docker_port' : 8800,
                'docker_long_poll_port' : 18800,
                'docker_hub_name' : DOCKER_DEFAULTS.get('docker_hub_name', ''),
                'erp_image_version' : DOCKER_DEFAULTS.get('erp_image_version', ''),
            }                
            # create global sites
            global_dir = '%s/sites_global' % p1
            __ini__data = open('%s/templates/sites_list__init__.py' % self.base_path).read()
            print_message = True
            if not os.path.exists(global_dir):
                did_change = True
                os.mkdir(global_dir)
                open('%s/sites_global/__init__.py' % p1, 'w').write(__ini__data)
                if is_localhost:
                    open('%s/sites_global/demo_global.py' % p1, 'w').write(SITES_GLOBAL_TEMPLATE % (
                        'demo_global', template % defaults))
            else:
                print_message = False
                # maybe we cloned sites_list without ini files
                ini_p = '%s/sites_global/__init__.py' % p1
                if not os.path.exists(ini_p):
                    did_change = True
                    open('%s/sites_global/__init__.py' % p1, 'w').write(__ini__data)
            # create local sites
            local_dir = '%s/sites_local' % p1
            __ini__data = __ini__data.replace('SITES_G', 'SITES_L')
            if not os.path.exists(local_dir):
                did_change = True
                os.mkdir(local_dir)
                open('%s/sites_local/__init__.py' % p1, 'w').write(__ini__data)
                if is_localhost:
                    defaults['site_name'] = 'demo_local'
                    open('%s/sites_local/demo_local.py' % p1, 'w').write(SITES_GLOBAL_TEMPLATE % (
                        'demo_local', template % defaults))
            else:
                print_message = False
                # maybe we cloned sites_list without ini files
                ini_p = '%s/sites_local/__init__.py' % p1
                if not os.path.exists(ini_p):
                    did_change = True
                    open('%s/sites_local/__init__.py' % p1, 'w').write(__ini__data)
            if print_message:
                if is_localhost:
                    print(LOCALSITESLIST_CREATED % (
                        os.path.normpath('%s/sites_global/demo_global.py' % p1), 
                        os.path.normpath('%s/sites_local/demo_local.py' % p1)))
        return did_change
    

    def check_and_create_sites_repo(self, force = False):
        # check whether sites repo defined in BASEINFO exists
        # if not download and install it
        must_exit = False
        must_update_ini = False
        sitelist_names = []
        sites_list_path = BASE_INFO.get('sitesinfo_path')
        if not sites_list_path:
            return '' # not yet configured
        # create sitelisth path
        os.makedirs(sites_list_path, exist_ok=True)
        siteinfos = BASE_INFO.get('siteinfos', [])
        if siteinfos:
            for sitelist_name, sites_list_url in list(siteinfos.items()):
                #sites_list_url = BASE_INFO.get('sitesinfo_url')
                sitelist_names.append(sitelist_name)
                running_path = os.path.normpath('%s/%s' % (sites_list_path, sitelist_name))
                if sites_list_url == 'localhost':
                    must_exit = self._create_sites_rep(running_path)
                    # when we create the site-list, we must also create the ini file
                    if not os.path.exists('%s/__init__.py' % sites_list_path):
                        must_update_ini = True
                elif not os.path.exists(running_path):
                    # try to git clone sites_list_url
                    must_update_ini = True
                    act = os.getcwd()
                    #dp = '/' + '/'.join([p for p in running_path.split('/') if p][:-1])
                    os.chdir(sites_list_path)
                    cmd_line = ['git clone %s %s' % (sites_list_url, sitelist_name)]
                    p = subprocess.Popen(
                        cmd_line,
                        stdout=PIPE,
                        stderr=PIPE,
                        env=dict(os.environ,  PATH='/usr/bin'),
                        shell=True)
                    result = p.communicate()
                    if p.returncode:
                        print(bcolors.FAIL)
                        print('Error:')
                        print('The commandline %s produced an error' % cmd_line)
                        print('please check if the sites_list in config/config.yaml is properly formated')
                        for part in result[1].split(b'\n'):
                            print(part.decode("utf-8"))
                        print(bcolors.ENDC)
                        # clean up 
                        if os.path.exists(running_path):
                            os.unlink(running_path)
                    else:
                        print(bcolors.WARNING)
                        print(LOCALSITESLIST_CLONED % (sites_list_url, os.getcwd()))
                    os.chdir(act)
                    # now create missing elements
                    if not p.returncode:
                        must_exit = self._create_sites_rep(running_path)
            # create outer inifile if needed
            if must_update_ini:
                ini = SITES_LIST_OUTER_HEAD
                for sn in sitelist_names:
                    ini += (SITES_LIST_OUTER_LINE % {'file_name' : sn})
                with open('%s/__init__.py' % sites_list_path, 'w') as f:
                    f.write(ini)
                sys.exit()
            if must_exit:
                sys.exit()
        return sites_list_path

    @property
    def marker(self):
        #if self.parsername == 'docker':
            #return self.docker_rpc_host
        return MARKER

    def get_sites(self):
        sites_list_path = self.check_and_create_sites_repo()
        if not sites_list_path:
            return (None, None)
        self.sites_list_path = sites_list_path
        SITES_L = {}
        # if sites_list_path is != self.self.base_path + '/sites_list' we have to add it to the path
        sites_list_path = os.path.normpath(sites_list_path)
        if sites_list_path != os.path.normpath(self.base_path + '/sites_list'):
            parts = sites_list_path.split('/')
            if parts[-1] == 'sites_list':
                parts = [p for p in parts if p]
                sites_list_path = '/' + '/'.join(parts[:-1])
            sys.path.insert(0, os.path.normpath(sites_list_path))
        try:
            from sites_list import SITES_G, SITES_L
            #from sites_list.sites_local import SITES_L
        except ImportError:
            print(bcolors.FAIL)
            print('*' * 80)
            print('could not import sites list')
            print(bcolors.ENDC)
            return {}, {}
            
        # -------------------------------------------------------------
        # test code from prakash to set the local sites value to true
        #------------------------------------------------------------
        for key in list(SITES_L.keys()):
            SITES_L[key]['is_local'] = True

        SITES = {}
        SITES.update(SITES_G)
        SITES.update(SITES_L)

        # -------------------------------------------------------------
        # merge passwords
        # -------------------------------------------------------------
        DEFAULT_PWS = {
            'erp_admin_pw' : '',
            #'email_pw_incomming' : '',
            #'email_pw_outgoing' : '',
        }
        # read passwords
        SITES_PW = {}
        try:
            from sites_pw import SITES_PW
        except ImportError:
            pass
        # merge them
        for key in list(SITES.keys()):
            kDic = SITES_PW.get(key, DEFAULT_PWS)
            for k in list(DEFAULT_PWS.keys()):
                SITES[key][k] = kDic.get(k, '')
            # get dockerhub password if available
            docker_info = SITES[key].get('docker', {})
            docker_hub_info = SITES[key].get('docker_hub', {})
            hub_name  = docker_info.get('hub_name', '')
            if hub_name:
                # docker hub passwords are a separte block
                kDic_hub = SITES_PW.get('docker_hub', {})
                if kDic_hub:
                    # get docker_hub block from pw struct
                    kdic_hub_info = kDic_hub.get(
                        hub_name, {} # get image repository for this site
                    )
                    hub_user = docker_hub_info.get(hub_name, {}).get('user')
                    if hub_user:
                        docker_hub_pw = kdic_hub_info.get(hub_user, {}).get('docker_hub_pw', '')
                        if docker_hub_pw:
                            SITES[key]['docker_hub'][hub_name]['docker_hub_pw'] = docker_hub_pw

        return SITES, SITES_L
    
    def drop_site(self, template_name):
        # when dropping sites, it could be that we are in a testing environment
        # that did not restart since creating the site
        SITES_G, SITES_L = self.get_sites()
        sites_list_path = self.sites_list_path
        
        if template_name in list(SITES_L.keys()):
            site = SITES_L[template_name]
            origin = site['site_list_name']
            try:
                os.unlink(os.path.normpath('%s/%s/sites_local/%s.py' % (sites_list_path, origin, template_name)))
                os.unlink(os.path.normpath('%s/%s/sites_local/%s.pyc' %
                                           (sites_list_path, origin, template_name)))
            except:
                pass
            return True
        elif template_name in list(SITES_G.keys()):
            site = SITES_G[template_name]
            origin = site['site_list_name']
            try:
                os.unlink(os.path.normpath('%s/%s/sites_global/%s.py' %
                                           (sites_list_path, origin, template_name)))
                os.unlink(os.path.normpath('%s/%s/sites_global/%s.pyc' %
                                           (sites_list_path, origin, template_name)))
            except:
                pass
            return True
        print((bcolors.FAIL))
        print(('*' * 80))
        print(('%s is not an existing site description' % template_name))
        print((bcolors.ENDC))
        
    
    def find_template(self, template_name):
        sites_list_path = self.check_and_create_sites_repo()
        SITES, SITES_L = self.get_sites()
        if template_name in list(SITES.keys()):
            return open('%ssites_global/%s.py' % (sites_list_path, template_name)).read()
        elif template_name in list(SITES_L.keys()):
            return open('%ssites_local/%s.py' % (sites_list_path, template_name)).read()
        print((bcolors.FAIL))
        print(('*' * 80))
        print(('%s is not an existing site description' % template_name))
        print((bcolors.ENDC))
               
    def add_site_global(self, handler, template_name = '', preset_values = {}, sublist='localhost'):
        """add a global site to the list of site
        
        Arguments:
            handler {instance} -- the handler is the calling instance. trough it, all the callers 

        
        Keyword Arguments:
            template_name {str} -- the name of the template to use to construct the site description (default: {''})
            preset_values {dict} -- aset of values to use as default when constructing the site (default: {{}})
        
        Returns:
            [type] -- [description]
        """

        self.handler = handler
        remote_url = handler.opts.use_ip or '127.0.0.1'
        # look up what remote url we need to use
        remote_server_info = REMOTE_SERVERS.get(remote_url)
        if not remote_server_info:
            print(bcolors.FAIL)
            print('*' * 80)
            print('no remote server description found for %s' % remote_url)
            print('please create it with bin/s --add-server %s' % remote_url)
            print(bcolors.ENDC)
            sys.exit()
        handler.default_values['base_sites_home'] = remote_server_info.get('remote_data_path', '/root/erp_workbench')
        handler.default_values['base_url'] = ('%s.ch' % handler.site_name)
        template = ''
        # no_outer will be set, if we use an existing site-description as base
        no_outer = False
        if template_name:
            template = self.find_template(template_name)
            # now we replace all instances of the old name with the new one
            template = template.replace(template_name, handler.opts.name)
            no_outer = True # do not wrap the template in an outer dict
        if not template:
            # make sure we really have a site_name, this is sometimes not the case while testing
            if not handler.default_values['site_name']:
                handler.default_values['site_name'] = handler.site_name
            with open('%s/templates/newsite.py' % handler.sites_home, 'r') as f:
                template = f.read() % handler.default_values
            template = template.replace('127.0.0.1', remote_url)
        # make sure do have a site name
        if not handler.site_name:
            print(bcolors.FAIL)
            print('*' * 80)
            print('attempt to create a site without a name')
            print(bcolors.ENDC)
            sys.exit()

        return self._add_site('G', template, no_outer, sublist)

    def add_site_local(self, handler, template_name = '', sublist='localhost'):
        self.handler = handler
        handler.default_values['base_sites_home'] = '/home/%s/erp_workbench' % ACT_USER
        handler.default_values['base_url'] = ('%s.ch' % handler.site_name)
        template = ''
        if template_name:
            template = self.find_template(template_name)
            # 'remote_url' : '176.9.142.21',  # alice2
            template['remote_server']['remote_url'] = 'localhost'
            template = '"%s" : %s' % (handler.opts.name, pformat(template))
        if not template:
            # make sure we really have a site_name, this is sometimes not the cae while testing
            if not handler.default_values['site_name']:
                handler.default_values['site_name'] = handler.site_name
            with open('%s/templates/newsite.py' % handler.sites_home, 'r') as f:
                template = f.read() % handler.default_values
            template = template.replace('xx.xx.xx.xx', 'localhost')
        return self._add_site('L', template, False, sublist)

    def _add_site(self, where, template, no_outer, sublist):
        site_name = self.handler.site_name
        if self.handler.sites.get(site_name):
            print("site %s allready defined" % site_name)
            return
        if site_name.find('.') > -1 :
            print(SITE_ADDED_NO_DOT % site_name)
            return
        if where not in ['L', 'G']:
            return {'error' : 'not a valid sites type %s' % where}
        if not no_outer:
            outer_template = SITES_GLOBAL_TEMPLATE % (site_name, template)
        else:
            outer_template = template
        if where == 'G':
            # add a new file with the sites info
            f_path = '%s/%s/sites_global/%s.py' % (BASE_INFO['sitesinfo_path'], sublist, site_name)
        elif where == 'L':
            site_name = self.handler.site_name
            f_path = '%s/%s/sites_local/%s.py' % (BASE_INFO['sitesinfo_path'], sublist, site_name)
        f_path = os.path.normpath(f_path)
        with open(f_path, 'w') as f:
            f.write(outer_template)
        return {
            'type' : where,
            'site_info' : outer_template,
        }
        
    def check_pull(self, auto='check'):
        """automatically update sites-list according to seettings
        config file.
        
        Keyword Arguments:
            auto {str} -- should we first check config? (default: {'check'})
        """

        actual = os.getcwd()
        if not hasattr(self, 'sites_list_path'):
            return
        if auto =='check':
            if not BASE_INFO.get('sites_autopull', ''):
                return
        os.chdir(self.sites_list_path)
        p = subprocess.Popen(
            'git pull',
            stdout=PIPE,
            env=dict(os.environ,  PATH='/usr/bin'),
            shell=True)
        p.communicate()
        os.chdir(actual)

    def fix_sites_list(self, fix=False):
        """check if url to repository of sites list
        has changed. Try to update settings.
        """
        pass


