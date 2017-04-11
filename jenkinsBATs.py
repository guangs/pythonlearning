import time
import urllib
import urllib2
import re
import subprocess
import sys
import logging
import logging.config
import socket
import abc
import tempfile
import zipfile
import atexit
from os.path import isdir, join, normpath, split
from multiprocessing import Process, Queue

from pyVim import connect
from pyVmomi import vim
from pyVmomi import vmodl
import requests
from PySTAF import *
from tools import pchelper

import errno

sys.setrecursionlimit(10000)

logger = logging.getLogger(__name__)
BUILD_TAG = os.environ.get('BUILD_TAG', 'BATs')

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,  # this fixes the problem

    'formatters': {
        'standard': {
            'format': '%(asctime)-15s (%(processName)-9s) %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'filename': 'c:/BATs/logs/%s.log' % BUILD_TAG,
            'formatter': 'standard',
            'maxBytes': 10485760,
            'encoding': "utf8"
        }
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        }
    }
})

try:
    import simplejson as json
except ImportError:
    import json


def get_pattern_product(product, system_arch):
    """
    :param product: client, agent, broker, viewtest, viewapioperator
    :param system_arch: x86, x64
    :rtype : String, product name pattern.
    """
    arch = ''
    if product == ProductEnum.VIEWAGENT or product == ProductEnum.VIEWBROKER:
        arch = '-x86_64-' if system_arch.endswith('64') else '-'
    if product == ProductEnum.VIEWCLIENT:
        arch = 'x86_64' if system_arch.endswith('64') else 'x86'

    return {
        'viewtest': r'VMware-viewtest-\w.\w.\w-\d+\.zip',
        'viewapioperator': r'VMware-viewapioperator-\w.\w.\w-\d+\.zip',
        'client': r'publish/VMware-Horizon-Client-%s-\d+\.\d+\.\d+\-\d+\.exe' % arch,
        'agent': r'VMware-viewagent%s\w.\w.\w-\d+\.exe' % arch,
        'broker': r'VMware-viewconnectionserver%s\w.\w.\w-\d+\.exe' % arch
    }.get(product, None)


class ProductEnum():
    VIEWCLIENT = 'client'
    VIEWAGENT = 'agent'
    VIEWBROKER = 'broker'
    VIEWTEST = 'viewtest'
    VIEWAPIOPERATOR = 'viewapioperator'


class BuildWebProduct:
    def __init__(self):
        pass

    #  previous is viewcrt
    VIEWCLIENT = 'viewclientwin'
    VIEWAGENT = 'view'
    VIEWBROKER = 'view'


class VC_cred():
    def __init__(self):
        pass

    user = 'administrator'
    user_for_web_cmd = user
    pwd = 'ca$hc0w'


''' For the vsphere 6.0U2, the policy of password change, so this is for the new version. '''


class VC_cred_60U2():
    def __init__(self):
        pass

    user = 'administrator@vsphere.local'
    user_for_web_cmd = 'administrator%40vsphere.local'
    pwd = 'Ca$hc0w1'


class Domain_cred():
    user = 'hovdi\\administrator'
    pwd = 'ca$hc0w'


class DownloadError(Exception):
    """
    Error for the build download.
    """

    def __init__(self, *args, **kwargs):  # real signature unknown
        pass

    @staticmethod  # known case of __new__
    def __new__(S, *more):  # real signature unknown; restored from __doc__
        """ T.__new__(S, ...) -> a new object with type S, a subtype of T """
        pass


class AgentInstallException(Exception):
    def __init__(self, *args, **kwargs):  # real signature unknown
        Exception.__init__(self, *args, **kwargs)


# os.environ.__setitem__('components', 'RDSH')
# os.environ.__setitem__('selectBATEnv', 'BAT5-W764')
# os.environ.__setitem__('brokerBranch', 'view-server-main')
# os.environ.__setitem__('agentBranch', 'view-server-main')
# os.environ.__setitem__('viewBuildType', 'ob')
# os.environ.__setitem__('brokerBuildNo', '')
# os.environ.__setitem__('agentBuildNo', '')
# os.environ.__setitem__('client', '5-10.112.118.252')
# os.environ.__setitem__('clientImage', '5-Win81U3x64P')
# os.environ.__setitem__('clientBranch', 'crt-main')
# os.environ.__setitem__('clientBuildNum', '')
# os.environ.__setitem__('clientBuildType', 'ob')
# os.environ.__setitem__('testSuite', '')
# os.environ.__setitem__('executeParams', '')

# Load all the BATs data.
with open('c:\\BATs\\bats.json') as bats_data_file:
    bats_data = json.load(bats_data_file)


class Parameters(object):
    """
        All of these parameters are input from the jenkins.
    """

    def __init__(self):
        self.components = os.environ.get('components', '')
        self.select_bat_env = os.environ.get('selectBATEnv', '')
        self.broker_branch = os.environ.get('brokerBranch', '')
        self.agent_branch = os.environ.get('agentBranch', '')
        self.view_build_type = os.environ.get('viewBuildType', 'ob')
        self.broker_build_no = os.environ.get('brokerBuildNo', '')
        self.agent_build_no = os.environ.get('agentBuildNo', '')

        enable_fips_str = os.environ.get('enableFIPS', '')
        if enable_fips_str == 'true':
            enable_fips = True
        else:
            enable_fips = False
        self.enable_fips = enable_fips

        enable_udp_str = os.environ.get('enableUDP', '')
        if enable_udp_str == 'true':
            enable_udp = True
        else:
            enable_udp = False
        self.enable_udp = enable_udp

        enable_non_default_str = os.environ.get('enableNonDefault', '')
        if enable_non_default_str == 'true':
            enable_non_default = True
        else:
            enable_non_default = False
        self.enable_non_default = enable_non_default

        self.client_branch = os.environ.get('clientBranch', '')
        self.client_build_num = os.environ.get('clientBuildNum', '')
        self.client_build_type = os.environ.get('clientBuildType', '')
        self.test_suite = os.environ.get('testSuite', '')
        self.execute_params = os.environ.get('executeParams', '')

        self.bat_env_no = os.environ.get('BATEnv', '')
        self.client_platform = os.environ.get('ClientPlatform', '')
        self.agent_platform = os.environ.get('AgentPlatform', '')

        self.client_build_path_64 = ''
        self.client_build_path_32 = ''
        self.agent_build_path = ''
        self.broker_build_path = ''
        self.rdsh_build_path = ''
        self.view_test_build_path = ''
        self.view_api_operator_build_path = ''


class BATsEnvParameters(object):
    def __init__(self, parameters):

        self.parameters = parameters

        self.vc_server = bats_data[parameters.bat_env_no]["vc"].get("vc_server", "")
        self.is_new_vc = bats_data[parameters.bat_env_no]["vc"].get("is_new_vc", False)

        self.esxi_ip = bats_data[parameters.bat_env_no]["esxi"].get("esxi_server", "")

        self.broker_ip = bats_data[parameters.bat_env_no]["broker"].get("broker_ip", "")
        self.broker_vm = bats_data[parameters.bat_env_no]["broker"].get("broker_vm", "")

        self.pool_name = parameters.agent_platform
        self.agent_vm = bats_data[parameters.bat_env_no]["agents"][self.pool_name].get("agent_vm", "")
        self.agent_arch = bats_data[parameters.bat_env_no]["agents"][self.pool_name].get("agent_arch", "")

        self.rds_vm = bats_data[parameters.bat_env_no]["rdsh"].get("rds_vm", "")
        self.rds_hostname = bats_data[parameters.bat_env_no]["rdsh"].get("rds_hostname", "")

        self.client_ip = bats_data[parameters.bat_env_no]["client"].get("client_ip", "")
        self.client_name = bats_data[parameters.bat_env_no]["client"].get("client_name", "")
        self.is_client_vm = bats_data[parameters.bat_env_no]["client"].get("is_client_vm", False)
        self.client_vm = bats_data[parameters.bat_env_no]["client"][parameters.client_platform].get("client_vm", "")
        self.client_image = bats_data[parameters.bat_env_no]["client"][parameters.client_platform].get("client_image", "")

        self.license = bats_data["license"].get(self.parameters.broker_branch, "")

        ''' Support both 55 and 60vc. '''
        self.vc_cred = None
        if self.is_new_vc:
            self.vc_cred = VC_cred_60U2()
        else:
            self.vc_cred = VC_cred()

        workflow_controller = WorkflowController(parameters.components)
        workflow_controller.do_parse_components()

        self.skip_broker = workflow_controller.skip_broker
        self.skip_client = workflow_controller.skip_client
        self.skip_agent = workflow_controller.skip_agent
        self.skip_rdsh = workflow_controller.skip_rdsh
        self.skip_rdsh_conf = workflow_controller.skip_rdsh_conf
        self.broker_ins_only = workflow_controller.broker_ins_only
        self.agent_config = workflow_controller.agent_config
        self.run_tc = workflow_controller.run_tc
        self.restore_machine = workflow_controller.restore_machine
        self.do_refactor = workflow_controller.do_refactor

        self.do_prepare_setting()
        self.log_input(parameters)
        # self.debug_func()

    def do_prepare_setting(self):
        """
            This function will get the build num and download build for later use.

            If choose the web commander to install build, just ignore the download part which only serves
            for the install that implemented by myself.

            As i use the multiple threads to install build, so download firstly with the signle thread mode.

            For the RDSH build, as it only to be installed on the 64 based platform, so if the agent is 32 bit, here
            have to force download a 64 bit version as the RDSH installer.

        """
        build_web = BuildWeb()

        if not self.skip_agent:
            self.download_agent_assets(build_web)

        if not self.skip_broker:
            self.download_broker_assets(build_web)

        if not self.skip_rdsh:
            self.download_rdsh_assets(build_web)

        if not self.skip_client:
            self.download_client_assets(build_web)

    def download_client_assets(self, build_web):
        ''' Here is just download both 64 and 32 for further use. '''
        if self.parameters.client_build_num == '' or not self.parameters.client_build_num.isdigit():
            self.parameters.client_build_num = BuildWeb.get_latest_build(BuildWebProduct.VIEWCLIENT,
                                                                         self.parameters.client_branch,
                                                                         self.parameters.client_build_type)
            assert (self.parameters.client_build_num != ''), "Client should not be null."
            logger.info("Client build number: " + str(self.parameters.client_build_num))

        ''' Get the latest client build... '''
        self.parameters.client_build_path_64 = build_web.download_by_build_num(self.parameters.client_build_num,
                                                                               self.parameters.client_build_type,
                                                                               ProductEnum.VIEWCLIENT, '64')
        self.parameters.client_build_path_32 = build_web.download_by_build_num(self.parameters.client_build_num,
                                                                               self.parameters.client_build_type,
                                                                               ProductEnum.VIEWCLIENT, '32')
        logger.info("Client build path 64: " + str(self.parameters.client_build_path_64))
        logger.info("Client build path 32:" + str(self.parameters.client_build_path_32))

    def download_rdsh_assets(self, build_web):
        if not self.skip_agent:
            ''' RDSH only supports 64 bit. '''
            if self.agent_arch != 'x64':
                self.parameters.rdsh_build_path = build_web.download_by_build_num(self.parameters.agent_build_no,
                                                                                  self.parameters.view_build_type,
                                                                                  ProductEnum.VIEWAGENT, 'x64')
            else:
                self.parameters.rdsh_build_path = self.parameters.agent_build_path
        else:
            ''' Fix bug, if specify the agent build number, use it as the RDSH build number.'''
            if self.parameters.agent_build_no == '' or not self.parameters.agent_build_no.isdigit():
                self.parameters.agent_build_no = BuildWeb.get_latest_recommend_build(BuildWebProduct.VIEWAGENT,
                                                                                     self.parameters.agent_branch,
                                                                                     self.parameters.view_build_type)
            self.parameters.rdsh_build_path = build_web.download_by_build_num(self.parameters.agent_build_no,
                                                                              self.parameters.view_build_type,
                                                                              ProductEnum.VIEWAGENT, 'x64')
        logger.info("RDSH build path: " + str(self.parameters.rdsh_build_path))

    def download_broker_assets(self, build_web):
        if self.parameters.broker_build_no == '' or not self.parameters.broker_build_no.isdigit():
            self.parameters.broker_build_no = BuildWeb.get_latest_recommend_build(BuildWebProduct.VIEWBROKER,
                                                                                  self.parameters.broker_branch,
                                                                                  self.parameters.view_build_type)
        assert (self.parameters.broker_build_no != ''), "Broker should not be null."
        logger.info("Broker build number: " + str(self.parameters.broker_build_no))
        ''' Broker only support 64 bit platform '''
        self.parameters.broker_build_path = build_web.download_by_build_num(self.parameters.broker_build_no,
                                                                            self.parameters.view_build_type,
                                                                            ProductEnum.VIEWBROKER, 'x64')
        logger.info("Broker build path: " + str(self.parameters.broker_build_path))
        self.parameters.view_test_build_path = build_web.download_by_build_num(self.parameters.broker_build_no,
                                                                               self.parameters.view_build_type,
                                                                               ProductEnum.VIEWTEST, '')
        logger.info("View Test build path: " + str(self.parameters.view_test_build_path))
        self.parameters.view_api_operator_build_path = build_web.download_by_build_num(
            self.parameters.broker_build_no,
            self.parameters.view_build_type,
            ProductEnum.VIEWAPIOPERATOR, '')
        logger.info("View API Operator build path: " + str(self.parameters.view_api_operator_build_path))

    def download_agent_assets(self, build_web):
        if self.parameters.agent_build_no == '' or not self.parameters.agent_build_no.isdigit():
            self.parameters.agent_build_no = BuildWeb.get_latest_recommend_build(BuildWebProduct.VIEWAGENT,
                                                                                 self.parameters.agent_branch,
                                                                                 self.parameters.view_build_type)
        assert (self.parameters.agent_build_no != ''), "Agent should not be null."
        logger.info("Agent build number: " + str(self.parameters.agent_build_no))
        self.parameters.agent_build_path = build_web.download_by_build_num(self.parameters.agent_build_no,
                                                                           self.parameters.view_build_type,
                                                                           ProductEnum.VIEWAGENT, self.agent_arch)
        logger.info("Agent build path: " + str(self.parameters.agent_build_path))

    def log_input(self, parameters):
        logger.info("-" * 70)
        logger.info("Skip Broker :                {0}".format(str(self.skip_broker)))
        logger.info("Skip Agent :                 {0}".format(str(self.skip_agent)))
        logger.info("Skip RDSH :                  {0}".format(str(self.skip_rdsh)))
        logger.info("Skip Client :                {0}".format(str(self.skip_client)))
        logger.info("Agent Configuration :        {0}".format(str(self.agent_config)))
        logger.info("Run Test Cases :             {0}".format(str(self.run_tc)))
        logger.info("Select Env :                 {0}".format(str(parameters.bat_env_no)))
        logger.info("VC :                         {0}".format(str(self.vc_server)))
        logger.info("Agent VM :                   {0}".format(str(self.agent_vm)))
        logger.info("Broker VM :                  {0}".format(str(self.broker_vm)))
        logger.info("Broker IP :                  {0}".format(str(self.broker_ip)))
        logger.info("-" * 70)


class WorkflowController:
    def __init__(self, components):
        self.components = components

    skip_broker = False
    skip_client = False
    skip_agent = False
    skip_rdsh = False
    skip_rdsh_conf = False
    broker_ins_only = False
    agent_config = False
    run_tc = True
    restore_machine = True
    ''' It's a case for dev refactor. '''
    do_refactor = False

    def do_parse_components(self):

        if 'brokerinsonly' in self.components.lower():
            self.skip_agent = True
            self.skip_rdsh = True
            self.skip_client = True
            self.agent_config = False
            self.skip_rdsh_conf = True
            self.run_tc = False
            self.restore_machine = False
            return

        if '4refactor' in self.components.lower():
            self.skip_broker = True
            self.skip_client = False
            self.skip_agent = True
            self.skip_rdsh = True
            self.agent_config = False
            self.skip_rdsh_conf = True
            self.restore_machine = False
            self.do_refactor = True
            self.run_tc = True
            return

        if 'broker' not in self.components.lower():
            self.skip_broker = True
        if 'agent' not in self.components.lower():
            self.skip_agent = True
        if 'rdsh' not in self.components.lower():
            self.skip_rdsh = True
        if 'client' not in self.components.lower():
            self.skip_client = True
        if 'agentconf' in self.components.lower() or not self.skip_broker:
            self.agent_config = True
        if 'norun' in self.components.lower():
            self.run_tc = False
        if 'norestore' in self.components.lower():
            self.restore_machine = False
        if 'rdshnoconf' in self.components.lower():
            self.skip_rdsh = False
            self.skip_rdsh_conf = True


class BuildWeb:
    """Interact with build web."""

    def __init__(self):
        self.delimiter = '#' * 80
        self.lineSep = '\r\n'

    @staticmethod
    def get_resource_list(url, times=1):
        """Get build info data"""
        try:
            build_web = 'http://buildapi.eng.vmware.com'
            url = '%s%s' % (build_web, url)
            """print 'Fetching %s ...\r\n' % url"""
            ret = urllib2.urlopen(url)
            status = int(ret.code)
            if status != 200:
                logging.error('HTTP status %d', status)
                raise Exception('Error: %s' % data['http_response_code']['message'])
            content = ret.read()
            if json:
                data = json.loads(content)
            else:
                data_dict = {}
                data_list = []
                for i in content.replace(' ', '').split('[{')[1].split('}]')[0].split('},{'):
                    for j in i.split(','):
                        data_dict[j.split(':')[0].strip().strip('"')] = j.split(':')[1].strip().strip('"')
                    data_list.append(data_dict)
                    data_dict = {}
                data_dict['_list'] = data_list
                data = data_dict
        except Exception, e:
            logger.info(e)
            logger.info(url)
            times += 1
            time.sleep(5)
            if times < 10:
                BuildWeb.get_resource_list(url, times)
        return data

    @staticmethod
    def get_latest_recommend_build(product, branch, build_type='ob'):
        ret = ''
        url = '/%s/build/?' \
              'product=%s&' \
              'branch=%s&' \
              '_limit=%d&' \
              '_order_by=-id&' \
              'buildstate__in=succeeded,storing&' \
              'buildtype__in=release,beta' \
              % (build_type, product, branch, 100)
        data = BuildWeb.get_resource_list(url)
        found_recommend = 0

        for item in data['_list']:
            build_id = item['id']
            """Save the latest build if there's no "recommended" build"""
            if ret == '': ret = str(build_id)
            qa_rrl = '/%s/qatestresult/?build=%s' % (build_type, build_id)
            qa_data = BuildWeb.get_resource_list(qa_rrl)
            for result in qa_data['_list']:
                if result['qaresult'] == "recommended":
                    ret = str(build_id)
                    found_recommend = 1
            if found_recommend == 1:
                break
        return ret

    @staticmethod
    def get_latest_build(product, branch, build_type='ob'):
        ''' only get the latest release build '''
        url = '/%s/build/?' \
              'product=%s&' \
              'branch=%s&' \
              '_limit=%d&' \
              '_order_by=-id&' \
              'buildstate__in=succeeded,storing&' \
              'buildtype__in=release' \
              % (build_type, product, branch, 1)
        """print 'url is %s' % url"""
        data = BuildWeb.get_resource_list(url)
        return data['_list'][0]['id']

    @staticmethod
    def get_deliverable_list_by_build_id(build_id, build_type='ob'):
        url = '/%s/deliverable/?build=%s' % (build_type, build_id)
        data = BuildWeb.get_resource_list(url)
        if data is not None:
            return data['_list']
        return None

    @staticmethod
    def get_version_by_build_num(build_id, build_type='ob'):
        url = '/%s/build/%s' % (build_type, build_id)
        data = BuildWeb.get_resource_list(url)
        if data is not None:
            return data['version']
        return None

    def download_by_build_num(self, build_id, build_type, product, system_arch, retry=True):
        """
        :param build_id:
        :param product:
        :param system_arch: x86 or x64 -- this is a predefined agent vm arch, as this script will not communicate with
                                          the vm machine. Thus, just hard code before run.

                                          Actually, the script already enhanced to communicate with VM machine with
                                          vsphere API. As no bug so far, will not update the code here.
        :param retry:

       :rtype : str, build local path. Should be in the temp folder.
       """
        builds = BuildWeb.get_deliverable_list_by_build_id(build_id, build_type)

        target_path = None
        target_pattern = get_pattern_product(product, system_arch)

        assert (builds != '')
        assert (target_pattern != '')

        for build in builds:
            matched = re.search(target_pattern, build['path'])
            if matched:
                target_path = build['_download_url']
                break

        """download build to temp folder."""
        try:
            local_file_path = os.path.join(tempfile.gettempdir(), os.path.basename(target_path))
            # logger.info('Downloading... : ' + str(build_id))
            if not os.path.exists(local_file_path):
                urllib.urlretrieve(target_path, local_file_path)
            logger.info('the build was downloaded successfully on the local : ' + local_file_path)
        except Exception, e:
            logger.info(e)
            if not retry:
                raise DownloadError("Build ID " + str(build_id) + " download error.")
            """will retry one more to handle any exception"""
            logger.info('Get download exception, will try one more time and stop the workflow if meet it twice.')
            self.download_by_build_num(build_id, product, system_arch, False)

        return local_file_path


class WebCommander:
    def __init__(self):
        self.web_commander_url = 'http://10.136.240.188/webcmd.php'
        self.web_commander_success = '4488'
        self.self_defined_error = '9999'

    def request_web_commander_once(self, url, action):
        http_response_ok = 200

        try:
            logger.info('action %s : %s ' % (action, url))
            ret = urllib2.urlopen(url)
            if ret.getcode() != http_response_ok:
                logger.info('http return code: %s != 200' % ret.getcode())
                return self.self_defined_error

            response_from_web_commander = ret.read()
            if self.no_return_code_from_web_commander(response_from_web_commander):
                logger.info(response_from_web_commander)
                return self.self_defined_error

            return_code = self.get_return_code_from_web_commander_response(response_from_web_commander)
            if return_code == self.web_commander_success:
                logger.info('***** webCommander action: ' + action + ' return code: '
                            + return_code + '. Succeeded. *****\n')
                return self.web_commander_success

            logger.info(response_from_web_commander)
            return self.get_error_code_from_web_commander_response(response_from_web_commander)
        except Exception, e:
            logger.info(e)

    def request_web_commander(self, url, action):
        if self.request_web_commander_once(url, action) != self.web_commander_success:
            return self.request_web_commander_once(url, action)
        return self.web_commander_success

    @staticmethod
    def no_return_code_from_web_commander(response):
        return response.find('<returnCode>') <= 0

    @staticmethod
    def get_return_code_from_web_commander_response(response):
        return response.split(r'</returnCode>')[0].split('<returnCode>')[1]

    def get_error_code_from_web_commander_response(self, response_from_web_commander):
        if response_from_web_commander.find('Exit code:') > 0:
            return response_from_web_commander.split(r'</fullyQualifiedErrorId>')[0].split('Exit code:')[1]
        elif response_from_web_commander.find('VMware Tools is not running') > 0:
            return '4007'
        return self.self_defined_error

    """The return code of this function will also be used to check VC's connectivity"""

    def revert_snapshot(self, vc_server, vc_user, vc_pwd, vm_name, snapshot_name='NRready'):
        assert (vm_name != '')
        url_revert = 'http://10.136.240.188/webcmd.php?command=snapshotAction&serverAddress=%s&' \
                     'serverUser=%s&serverPassword=%s&vmName=%s&ssName=%s&ssDescription=&action=restore' \
                     % (vc_server, vc_user, vc_pwd, vm_name, snapshot_name)
        url_power_on = 'http://10.136.240.188/webcmd.php?command=vmPowerOn&serverAddress=%s&' \
                       'serverUser=%s&serverPassword=%s&vmName=%s' % (vc_server, vc_user, vc_pwd, vm_name)
        return_code = self.request_web_commander(url_revert, 'revert snapshot')
        if return_code == '4488':
            self.request_web_commander(url_power_on, 'Power On')
        return return_code

    def vm_trust(self, vc_server, vc_user, vc_pwd, vm_name):
        url_trust_cert = 'http://10.136.240.188/webcmd.php?command=vmTrustVMwareSignature' + \
                         '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&guestUser=HOVDI%sAdministrator' \
                         % (vc_server, vc_user, vc_pwd, vm_name, r'%5C')
        return self.request_web_commander(url_trust_cert, 'vmTrustVMwareSignature')

    def update_vm_tools(self, vc_server, vc_user, vc_pwd, vm_name):
        update_vm_tools = 'http://10.136.240.188/webcmd.php?command=vmUpdateTools&serverAddress=%s&' \
                          'serverUser=%s&serverPassword=%s&vmName=%s' % (vc_server, vc_user, vc_pwd, vm_name)
        self.request_web_commander(update_vm_tools, 'vmUpdateTools')

    def restart_vm(self, vc_server, vc_user, vc_pwd, vm_name):
        url_restart = 'http://10.136.240.188/webcmd.php?command=vmRestart&serverAddress=%s&' \
                      'serverUser=%s&serverPassword=%s&vmName=%s' % (vc_server, vc_user, vc_pwd, vm_name)
        return_code = self.request_web_commander(url_restart, 'vmRestart')
        if return_code != '4488':
            if return_code == '4007':
                self.update_vm_tools(vm_name)
                time.sleep(180)
            self.request_web_commander(url_restart, 'vmRestart')

    def power_off_on_vm(self, vc_server, vc_user, vc_pwd, vm_name):
        """

       :param vc_server:
       :param vm_name:

        it's a workaround for restart vm machine.

       """
        url_shutdown = 'http://10.136.240.188/webcmd.php?command=vmShutdown&serverAddress=%s&' \
                       'serverUser=%s&serverPassword=%s&vmName=%s' % (vc_server, vc_user, vc_pwd, vm_name)
        url_power_on = 'http://10.136.240.188/webcmd.php?command=vmPowerOn&serverAddress=%s&' \
                       'serverUser=%s&serverPassword=%s&vmName=%s' % (vc_server, vc_user, vc_pwd, vm_name)
        self.request_web_commander(url_shutdown, 'vmShutdown')
        time.sleep(600)  # Wait 10 minutes for View to reconfigure the VM, mostly for increasing the video vRAM.
        self.request_web_commander(url_power_on, 'vmPowerOn')

    def install_prepare(self, vc_server, vc_user, vc_pwd, vm_name):
        assert (vm_name != '')

        """
           The first step is to revert the VM.
           if this step returns "vc is not reachable" error, then exit and fail the Jenkins build.

        """
        if self.revert_snapshot(vc_server, vc_user, vc_pwd, vm_name) == '4001':
            logger.info("Connecting to the VC is failed, the build is cancelled" % vc_server)
            sys.exit(-1)

        """
           wait for enough long time since some VMs are a bit slow,
           win10 sometimes cannot be launched success in 5 minutes, increase it to 500 seconds.

        """
        time.sleep(600)

        assert self.vm_trust(vc_server, vc_user, vc_pwd, vm_name) == '4488', 'Set trust error, stop the workflow.'

    ''' Retry once if failed '''

    def install_view(self, vc_server, vc_user, vc_pwd, vm_name, product, build_no, broker_ip, redo=1):

        if product == 'broker':
            install_url_no_revert = 'http://10.136.240.188/webcmd.php?command=installViewSync' \
                                    + '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&type=%s&build=%d&' \
                                      'downloadOnly=false&guestUser=HOVDI%sAdministrator' \
                                      % (vc_server, vc_user, vc_pwd, vm_name, product, build_no, r'%5C')

        if product == 'agent':
            agent_install_parameter = '%2Fs+%2Fv%22%2Fqn+RebootYesNo%3DNo+REBOOT' \
                                      '%3DReallySuppress+SUPPRESS_RUNONCE_CHECK%3D1+ADDLOCAL%3DALL%22'
            install_url_no_revert = 'http://10.136.240.188/webcmd.php?command=installViewSync' + \
                                    '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&type=%s&build=%d&' \
                                    'downloadOnly=false&guestUser=HOVDI%sAdministrator&silentInstallParam=%s' \
                                    % (vc_server, vc_user, vc_pwd, vm_name, product, build_no, r'%5C',
                                       agent_install_parameter)

        if product == 'agent-ts':
            install_url_no_revert = 'http://10.136.240.188/webcmd.php?command=installViewSync' \
                                    + '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&type=%s&build=%d&' \
                                      'downloadOnly=false&guestUser=HOVDI%sAdministrator&stdBrokerIp=%s' \
                                      % (vc_server, vc_user, vc_pwd, vm_name, product, build_no, r'%5C', broker_ip)

        return self.request_web_commander(install_url_no_revert, 'install build')

    """
        We have only few BATs cases for app test, so do not check the return code
        and make the build continue whether the setup is successful or failed.
    """

    def add_rds_app_pool(self, vc_server, vc_user, vc_pwd, broker_vm, rds_hostname):
        app_path = 'C:\Users\Default\AppData\Roaming\Microsoft\Windows\Start+Menu\Programs\Accessories\Notepad.lnk'
        url_add_farm_with_host = 'http://10.136.240.188/webcmd.php?command=brokerAddFarmWithRdsServer' \
                                 + '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s' \
                                   '&guestUser=HOVDI\\Administrator&farmName=rdsh&rdsServerDnsName=%s' \
                                   % (vc_server, vc_user, vc_pwd, broker_vm, rds_hostname)
        # web command brokerAddFarm seems not working
        url_add_app_pool = 'http://10.136.240.188/webcmd.php?command=brokerAddRdsAppPool' + \
                           "&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&" \
                           "guestUser=HOVDI\\Administrator&farmId=rdsh&poolId=Notepad&execPath=%s" \
                           % (vc_server, vc_user, vc_pwd, broker_vm, app_path)
        url_entitle = 'http://10.136.240.188/webcmd.php?command=brokerEntitleApplication' + \
                      "&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&" \
                      "guestUser=HOVDI\\Administrator&applicationId=Notepad&userName=HOVDI\\Domain+Users" \
                      % (vc_server, vc_user, vc_pwd, broker_vm)
        self.request_web_commander(url_add_farm_with_host, 'url_add_farm_with_host')
        self.request_web_commander(url_add_app_pool, 'url_add_app_pool')
        self.request_web_commander(url_entitle, 'url_entitle')

    def add_app_pool(self, vc_server, vc_user, vc_pwd, broker_vm):
        app_path = 'C:\Users\Default\AppData\Roaming\Microsoft\Windows\Start+Menu\Programs\Accessories\Notepad.lnk'
        url_add_app_pool = 'http://10.136.240.188/webcmd.php?command=brokerAddRdsAppPool' + \
                           "&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&" \
                           "guestUser=HOVDI\\Administrator&farmId=rdsh&poolId=Notepad&execPath=%s" \
                           % (vc_server, vc_user, vc_pwd, broker_vm, app_path)
        url_entitle = 'http://10.136.240.188/webcmd.php?command=brokerEntitleApplication' + \
                      "&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&" \
                      "guestUser=HOVDI\\Administrator&applicationId=Notepad&userName=HOVDI\\Domain+Users" \
                      % (vc_server, vc_user, vc_pwd, broker_vm)
        self.request_web_commander(url_add_app_pool, 'url_add_app_pool')
        self.request_web_commander(url_entitle, 'url_entitle')

    def rm_rdsh_server_from_farm(self, vc_server, vc_user, vc_pwd, rds_vm, rds_hostname):
        url_rm_rdsh_server_from_farm = 'http://10.136.240.188/webcmd.php?command=brokerRemoveRdsServerFromFarm' + \
                                       "&serverAddress=%s" \
                                       "&serverUser=%s&serverPassword=%s" \
                                       "&vmName=%s&" \
                                       "guestUser=HOVDI\\Administrator" \
                                       "&farmName=rdsh" \
                                       "&rdsServerDnsName=%s" \
                                       % (vc_server, vc_user, vc_pwd, rds_vm, rds_hostname)
        self.request_web_commander(url_rm_rdsh_server_from_farm, 'url_rm_rdsh_server_from_farm')

    def rm_app(self, vc_server, vc_user, vc_pwd, rds_vm):
        url_rm_app = 'http://10.136.240.188/webcmd.php?command=brokerDeleteApplication' + \
                     "&serverAddress=%s" \
                     "&serverUser=%s&serverPassword=%s" \
                     "&vmName=%s&" \
                     "guestUser=HOVDI\\Administrator" \
                     "&applicationId=Notepad" \
                     % (vc_server, vc_user, vc_pwd, rds_vm)
        self.request_web_commander(url_rm_app, 'url_rm_app')

    def add_farm(self, vc_server, vc_user, vc_pwd, rds_vm):
        url_add_farm = 'http://10.136.240.188/webcmd.php?command=brokerAddFarm' + \
                       "&serverAddress=%s" \
                       "&serverUser=%s&serverPassword=%s" \
                       "&vmName=%s&" \
                       "guestUser=HOVDI\\Administrator" \
                       "&farmName=rdsh" \
                       % (vc_server, vc_user, vc_pwd, rds_vm)
        return_code = self.request_web_commander(url_add_farm, 'url_add_farm')
        if return_code != '4488':
            return False
        return True

    def add_rds_to_farm(self, vc_server, vc_user, vc_pwd, rds_vm, rds_hostname):
        url_add_rds_to_farm = 'http://10.136.240.188/webcmd.php?command=brokerAddRdsServerToFarm' + \
                              "&serverAddress=%s" \
                              "&serverUser=%s&serverPassword=%s" \
                              "&vmName=%s&" \
                              "guestUser=HOVDI\\Administrator" \
                              "&farmName=rdsh" \
                              "&rdsServerDnsName=%s" \
                              % (vc_server, vc_user, vc_pwd, rds_vm, rds_hostname)
        self.request_web_commander(url_add_rds_to_farm, 'url_add_farm')

    def enable_html_access(self, vc_server, vc_user, vc_pwd, broker_vm, pool_name):
        url = 'http://10.136.240.188/webcmd.php?command=brokerSetHtmlAccess' \
              + '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&' \
                'guestUser=HOVDI%sAdministrator&poolId=%s&switch=true' \
                % (vc_server, vc_user, vc_pwd, broker_vm, r'%5c', pool_name)
        self.request_web_commander(url, 'brokerSetHtmlAccess')

    def add_desktop_pool(self, vc_server, vc_user, vc_pwd, broker_vm, pool_name, agent_vm):
        url_remove = 'http://10.136.240.188/webcmd.php?command=brokerRemovePool' + \
                     '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&' \
                     'guestUser=HOVDI%sAdministrator&poolId=%s&rmFromDisk=false' \
                     % (vc_server, vc_user, vc_pwd, broker_vm, r'%5C', pool_name)
        url_add = 'http://10.136.240.188/webcmd.php?command=brokerAddManualPool' + \
                  '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&' \
                  'guestUser=HOVDI%sAdministrator&poolId=%s&vcAddress=%s&vcUser=%s&vcPassword=%s' \
                  '&agentVmName=%s&poolType=NonPersistent' \
                  % (vc_server, vc_user, vc_pwd, broker_vm, r'%5C', pool_name, vc_server, vc_user, vc_pwd, agent_vm)
        url_entitle = 'http://10.136.240.188/webcmd.php?command=brokerEntitlePool' + \
                      '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&' \
                      'guestUser=HOVDI%sAdministrator&poolId=%s&userName=HOVDI\\Domain+Users' \
                      % (vc_server, vc_user, vc_pwd, broker_vm, r'%5C', pool_name)
        self.request_web_commander(url_remove, 'brokerRemovePool')
        self.request_web_commander(url_add, 'brokerAddManualPool')
        self.request_web_commander(url_entitle, 'brokerEntitlePool')
        self.enable_html_access(vc_server, vc_user, vc_pwd, broker_vm, pool_name)

    def add_license(self, vc_server, vc_user, vc_pwd, broker_vm, license_broker):
        # license_broker = 'H501V-N010J-M8R83-00CRP-C444C'
        url_add_license = 'http://10.136.240.188/webcmd.php?command=brokerAddLicense' + \
                          '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&license=%s' \
                          % (vc_server, vc_user, vc_pwd, broker_vm, license_broker)
        self.request_web_commander(url_add_license, 'brokerAddLicense')

    def add_vc(self, vc_server, vc_user, vc_pwd, broker_vm):
        add_vc_url = 'http://10.136.240.188/webcmd.php?command=brokerAddVc' + \
                     '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s' \
                     '&vcAddress=%s&vcUser=%s&vcPassword=%s&useComposer=false' \
                     % (vc_server, vc_user, vc_pwd, broker_vm, vc_server, vc_user, vc_pwd)
        self.request_web_commander(add_vc_url, 'brokerAddVc')

    def entitle(self, vc_server, vc_user, vc_pwd, broker_vm, pool_name):
        url_entitle = 'http://10.136.240.188/webcmd.php?command=brokerEntitlePool' + \
                      '&serverAddress=%s&serverUser=%s&serverPassword=%s&vmName=%s&' \
                      'guestUser=HOVDI%sAdministrator&poolId=%s&userName=HOVDI\\Domain+Users' \
                      % (vc_server, vc_user, vc_pwd, broker_vm, r'%5C', pool_name)
        self.request_web_commander(url_entitle, 'brokerEntitlePool')


"""
 It' used pyVMomi module to get vm information from VC center.

 For more details, please refer to the https://wiki.eng.vmware.com/PyVmomi

"""


class VMUtil(object):
    def __init__(self, host, user, pwd):

        self.host = host
        self.user = user
        self.pwd = pwd

    def __init__(self, host):
        self.host = host
        self.user = 'administrator'
        self.pwd = 'ca$hc0w'

    @property
    def vm_summary(self):
        return self.vm_summary

    @vm_summary.setter
    def vm_summary(self, vm_summary):
        self.vm_summary = vm_summary

    @staticmethod
    def get_vm_summary_by_name_internal(virtual_machine, vm_name, depth=1):
        """
        Print information for a particular virtual machine or recurse into a
        folder with depth protection
        """
        max_depth = 10
        # if this is a group it will have children. if it does, recurse into them
        # and then return
        if hasattr(virtual_machine, 'childEntity'):
            if depth > max_depth:
                return
            vm_list = virtual_machine.childEntity
            for c in vm_list:
                VMUtil.get_vm_summary_by_name_internal(c, vm_name, depth + 1)
            return
        summary = virtual_machine.summary
        if summary.config.name == vm_name:
            VMUtil.vm_summary = summary

    @staticmethod
    def get_vm_summary_by_name(host, user, pwd, vm_name, do_connect=True, service_instance=None):

        try:
            if do_connect:
                service_instance = connect.SmartConnect(host=host,
                                                        user=user,
                                                        pwd=pwd)

                atexit.register(connect.Disconnect, service_instance)
            content = service_instance.RetrieveContent()
            children = content.rootFolder.childEntity
            for child in children:
                if hasattr(child, 'vmFolder'):
                    data_center = child
                else:
                    # some other non-datacenter type object
                    continue
                vm_folder = data_center.vmFolder
                vm_list = vm_folder.childEntity
                for virtual_machine in vm_list:
                    VMUtil.get_vm_summary_by_name_internal(virtual_machine, vm_name, 1)
        except Exception, e:
            logger.info(e)

    @staticmethod
    def get_vm_summary_by_name_quick(host, user, pwd, vm_name, do_connect=True, service_instance=None):

        vm_properties = ["name", "config.uuid", "config.hardware.numCPU",
                         "config.hardware.memoryMB", "guest.guestState", "guest.ipAddress", "guest.toolsStatus",
                         "config.guestFullName", "config.guestId",
                         "config.version", "summary"]

        try:
            if do_connect:
                service_instance = connect.SmartConnect(host=host,
                                                        user=user,
                                                        pwd=pwd)

                atexit.register(connect.Disconnect, service_instance)
        except IOError as e:
            logger.info(e)
            pass

        if not service_instance:
            raise SystemExit("Unable to connect to host with supplied info.")

        logger.info("Success connect to " + host)

        try:

            view = pchelper.get_container_view(service_instance,
                                               obj_type=[vim.VirtualMachine])
            vm_data = pchelper.collect_properties(service_instance, view_ref=view,
                                                  obj_type=vim.VirtualMachine,
                                                  path_set=vm_properties,
                                                  include_mors=True)
        except Exception as e:
            logger.info(e)
            pass

        for vm in vm_data:
            if vm["name"] == vm_name:
                return vm["summary"]
        return None

    @staticmethod
    def upload_file_to_vm(host, user, pwd, upload_file, vm_name, vm_path, vm_user, vm_pwd, retry_times=0):
        """
        Simple command-line program for Uploading a file from host to guest

        host, user, pwd : VC
        upload_file :
        vm_name :
        vm_path :
        vm_user :
        vm_pwd :

        """

        ret = False
        try:
            service_instance = connect.SmartConnect(host=host, user=user, pwd=pwd)
            atexit.register(connect.Disconnect, service_instance)
            content = service_instance.RetrieveContent()

            vm_summary = VMUtil.get_vm_summary_by_name_quick(host, user, pwd, vm_name, False, service_instance)
            vm_uuid = str(vm_summary.config.uuid)

            vm = content.searchIndex.FindByUuid(None, vm_uuid, True)

            tools_status = vm.guest.toolsStatus
            if tools_status == 'toolsNotInstalled' or tools_status == 'toolsNotRunning':
                raise SystemExit(
                    "VMwareTools is either not running or not installed. "
                    "Rerun the script after verifying that VMWareTools "
                    "is running")

            creds = vim.vm.guest.NamePasswordAuthentication(
                username=vm_user, password=vm_pwd
            )

            with open(upload_file, 'rb') as myfile:
                args = myfile.read()

            try:
                file_attribute = vim.vm.guest.FileManager.FileAttributes()
                url = content.guestOperationsManager.fileManager.InitiateFileTransferToGuest(vm, creds,
                                                                                             vm_path, file_attribute,
                                                                                             len(args), True)

                resp = requests.put(url, data=args, verify=False)
                if not resp.status_code == 200:
                    logger.info("Error while uploading file")
                else:
                    logger.info("Successfully uploaded file")
                    ret = True
            except IOError, e:
                logger.info(e)
        except vmodl.MethodFault as error:
            logger.info("Caught vmodl fault : " + error.msg)
            if retry_times < 5:
                retry_times += 1
                VMUtil.upload_file_to_vm(host, user, pwd, upload_file, vm_name, vm_path, vm_user, vm_pwd, retry_times)
        finally:
            return ret

    @staticmethod
    def execute_program_in_vm(host, user, pwd, vm_name, program, para, vm_user, vm_pwd, wait_result=True, timeout=3600):
        """

         Return : the exit code of the program. Timeout is one hour.

        """
        try:
            service_instance = connect.SmartConnect(host=host, user=user, pwd=pwd)

            atexit.register(connect.Disconnect, service_instance)
            content = service_instance.RetrieveContent()

            vm_summary = VMUtil.get_vm_summary_by_name_quick(host, user, pwd, vm_name, False, service_instance)
            vm_uuid = str(vm_summary.config.uuid)

            vm = content.searchIndex.FindByUuid(None, vm_uuid, True)

            tools_status = vm.guest.toolsStatus
            if tools_status == 'toolsNotInstalled' or tools_status == 'toolsNotRunning':
                raise SystemExit(
                    "VMwareTools is either not running or not installed. "
                    "Rerun the script after verifying that VMwareTools "
                    "is running")

            creds = vim.vm.guest.NamePasswordAuthentication(
                username=vm_user, password=vm_pwd
            )

            try:
                pm = content.guestOperationsManager.processManager
                ps = vim.vm.guest.ProcessManager.ProgramSpec(
                    programPath=program,
                    arguments=para
                )

                res = pm.StartProgramInGuest(vm, creds, ps)

                if res > 0:
                    logger.info("Program executed, PID is %d" % res)

                if wait_result:
                    interval = 100
                    while True:
                        try:
                            if timeout <= 0:
                                logger.info(' execute program in vm reaching timeout, error.')
                                return -1

                            process_info = pm.ListProcessesInGuest(vm=vm, auth=creds, pids=[res])
                            if process_info[0].endTime != None:
                                logger.info(' execute program exit with code : ' + str(process_info[0].exitCode))
                                return process_info[0].exitCode

                        except Exception, e:
                            continue
                        timeout -= interval
                        time.sleep(interval)

                    return -1
                else:
                    ''' if no need to wait result, just return 0. '''
                    return 0
            except IOError, e:
                logger.info(e)
                return -1
        except vmodl.MethodFault as error:
            logger.info(error)
            logger.info("Caught vmodl fault : " + error.msg)
            return -1


class BrokerUtil(object):
    def __init__(self, host, user, pwd, domain):
        import PowershellServiceClient
        self.host = host
        self.user = user
        self.pwd = pwd
        self.domain = domain
        self.broker_instance = PowershellServiceClient.PowershellServiceClient()

    def connect(self):
        self.broker_instance.connect(self.host, self.user, self.pwd, self.domain)


class Utilities(object):
    def __init__(self):
        pass

    @staticmethod
    def unzip(infile, path):

        zip = zipfile.ZipFile(infile, 'r')

        # If the output location does not yet exist, create it
        #
        if not isdir(path):
            os.makedirs(path)

        for each in zip.namelist():

            # Check to see if the item was written to the zip file with an
            # archive name that includes a parent directory. If it does, create
            # the parent folder in the output workspace and then write the file,
            # otherwise, just write the file to the workspace.
            #
            if not each.endswith('/'):
                root, name = split(each)
                directory = normpath(join(path, root))
                if not isdir(directory):
                    os.makedirs(directory)
                file(join(directory, name), 'wb').write(zip.read(each))

        zip.close()

    @staticmethod
    def silent_remove(file_name):
        try:
            os.remove(file_name)
        except OSError as e:  # this would be "except OSError, e:" before Python 2.6
            if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
                raise  # re-raise exception if a different error occured

    @staticmethod
    def add_manual_pool(brokerAddress, brokerUser, brokerPassword, brokerUserDomain, vcAddress, agentVmName, poolId):
        try:
            logger.info('TRY TO ADD POOL WITH NEW METHOD..')
            STAFHelper.run_command_sync3('local', 'java -jar C:\\BATs\\addpool.jar ' + brokerAddress + ' '
                                         + brokerUser + ' ' + brokerPassword + ' ' + brokerUserDomain + ' '
                                         + vcAddress + ' ' + agentVmName + ' ' + poolId)
            time.sleep(150)
        except IOError, e:
            logger.info(e)

    @staticmethod
    def add_rds_pool(env):
        try:
            logger.info('TRY TO SET LICENSE WITH NEW METHOD..')
            STAFHelper.run_command_sync3('local', 'java -jar C:\\BATs\\view-api-wincdk.jar --batsEnv=%s '
                                                  '--service=rds --action=addPool --identifier=Win2012RDS '
                                                  '--farmName=rdsh --displayName=Win2012RDS '
                                                  '--description=BATSWin2012RDS'
                                         % env)
            time.sleep(150)
        except IOError, e:
            logger.info(e)

    @staticmethod
    def add_license(env, license):
        try:
            logger.info('TRY TO SET LICENSE WITH NEW METHOD..')
            STAFHelper.run_command_sync3('local', 'java -jar C:\\BATs\\view-api-wincdk.jar --batsEnv=%s '
                                                  '--service=license --action=setLicense --licenseValue=%s'
                                         % (env, license))
            time.sleep(150)
        except IOError, e:
            logger.info(e)

    @staticmethod
    def get_installed_product_version(ip):
        ''' So far only support 64 bit '''
        product_version = ''
        try:
            result = STAFHelper.run_command_sync4(ip, 'reg query \"HKEY_LOCAL_MACHINE\\SOFTWARE\\VMware, Inc.'
                                                      '\\VMware VDM\"')
            mc = unmarshall(result.result)
            entry_map = mc.getRootObject()
            product_version = entry_map['fileList'][0]['data'].split('\r\n')[2].split(' ')[-1]
        except IOError, e:
            logger.info(e)
            product_version = None
        finally:
            return product_version

    @staticmethod
    def enable_fips(vc_server=None, vc_user=None, vc_pwd=None, vm=None, is_vm_machine=True, ip=None):
        if is_vm_machine:
            logger.info(' Enable FIPS in the virtual machine. ')
            VMUtil.execute_program_in_vm(vc_server, vc_user, vc_pwd, vm, "c:\\Windows\\System32\\reg.exe",
                                         "add \"HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\"
                                         "FipsAlgorithmPolicy\" /v Enabled /t REG_DWORD /d 1 /f", Domain_cred.user,
                                         Domain_cred.pwd)
        else:
            logger.info(' Will use STAF to do enalbe FIPS as client is a physical machine. ')
            STAFHelper.run_command_sync3(ip, 'reg add \"HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Lsa'
                                             '\\FipsAlgorithmPolicy\" /v Enabled /t REG_DWORD /d 1 /f')

    @staticmethod
    def enable_udp(vc_server=None, vm=None, type=True, ip=None):
        if type == 'agent':
            logger.info(' Enable FIPS in the virtual machine. ')
            VMUtil.execute_program_in_vm(vc_server, VC_cred.user, VC_cred.pwd, vm, "c:\\Windows\\System32\\reg.exe",
                                         "add \"HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\"
                                         "FipsAlgorithmPolicy\" /v Enabled /t REG_DWORD /d 1 /f", Domain_cred.user,
                                         Domain_cred.pwd)
            ''' restart service '''
            VMUtil.execute_program_in_vm(vc_server, VC_cred.user, VC_cred.pwd, vm, "", Domain_cred.user,
                                         Domain_cred.pwd)
        elif type == 'broker':
            logger.info(' Will use STAF to do enalbe FIPS as client is a physical machine. ')
            STAFHelper.run_command_sync3(ip, 'reg add \"HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Lsa'
                                             '\\FipsAlgorithmPolicy\" /v Enabled /t REG_DWORD /d 1 /f')
        else:
            raise Exception('no support type to enable UDP.')

    @staticmethod
    def enable_none_default(type=None, vc_server=None, vm=None, ip=None, vm_name=None):
        if type == 'agent':
            logger.info(' Enable Non default port in the agent. ')

            STAFHelper.run_command_sync3(ip,
                                         'reg add \"HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Teradici\\PCoIP\\pcoip_admin_defaults\" '
                                         '/v pcoip.tcpport /t REG_DWORD /d 4182 /f')
            STAFHelper.run_command_sync3(ip,
                                         'reg add \"HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Teradici\\PCoIP\\pcoip_admin_defaults\" '
                                         '/v pcoip.tcpport_range /t REG_DWORD /d 1 /f')

            STAFHelper.run_command_sync3(ip,
                                         'reg add \"HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Teradici\\PCoIP\\pcoip_admin_defaults\" '
                                         '/v pcoip.udpport /t REG_DWORD /d 4182 /f')
            STAFHelper.run_command_sync3(ip,
                                         'reg add \"HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Teradici\\PCoIP\\pcoip_admin_defaults\" '
                                         '/v pcoip.udpport_range /t REG_DWORD /d 10 /f')
        elif type == 'broker':
            logger.info(' Enable Non default port in the broker side. ')
            locked_properties_path = 'C:/Program Files/VMware/VMware View/Server/sslgateway/conf/'
            STAFHelper.fs_request(ip, 'CREATE DIRECTORY %s' % locked_properties_path)

            logger.info(' Copy the locked file to the remote. ')
            none_default_port_locked_local = 'c:/BATs/non_default/locked.properties'
            none_default_port_locked_remote = locked_properties_path + 'locked.properties'
            STAFHelper.copy_from_local_to_remote(none_default_port_locked_local,
                                                 none_default_port_locked_remote,
                                                 ip)

            logger.info(' Copy the absg.properties to the remote. ')
            absg_file_local = 'c:/BATs/non_default/absg.properties'
            absg_file_remote = 'C:/Program Files/VMware/VMware View/Server/appblastgateway/absg.properties'
            STAFHelper.copy_from_local_to_remote(absg_file_local,
                                                 absg_file_remote,
                                                 ip)

            logger.info(' Change the UDP and TCP port in the broker side. ')
            VMUtil.execute_program_in_vm(vc_server, VC_cred.user, VC_cred.pwd, vm, "c:\\Windows\\System32\\reg.exe",
                                         "add \"HKEY_LOCAL_MACHINE\\SOFTWARE\\Teradici\\SecurityGateway\" "
                                         "/v ExternalTCPPort /t REG_SZ /d 4182 /f", Domain_cred.user,
                                         Domain_cred.pwd)
            VMUtil.execute_program_in_vm(vc_server, VC_cred.user, VC_cred.pwd, vm, "c:\\Windows\\System32\\reg.exe",
                                         "add \"HKEY_LOCAL_MACHINE\\SOFTWARE\\Teradici\\SecurityGateway\" "
                                         "/v ExternalUDPPort /t REG_SZ /d 4182 /f", Domain_cred.user,
                                         Domain_cred.pwd)

            logger.info(' edit the port for broker. ')
            STAFHelper.run_command_async(ip,
                                         '//10.117.45.89/view/tools/scripts/non_default.bat %s %s' %
                                         (vm_name, ip))
            time.sleep(150)
        else:
            raise Exception('no support type to enable None default port.')


class AbstractBATsEnvBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def config(self, bats_env_parameters):
        return

    @abc.abstractmethod
    def install(self, bats_env_parameters, queue):
        return

    @abc.abstractmethod
    def install2(self, bats_env_parameters, queue):
        return

    @abc.abstractmethod
    def valid_installation(self, bats_env_parameters, handle):
        return


class AgentRunner(AbstractBATsEnvBase):
    def __init__(self, bats_env_parameters):
        self.webCommander = WebCommander()
        self.bats_env_parameters = bats_env_parameters
        vm_summary = VMUtil.get_vm_summary_by_name_quick(bats_env_parameters.vc_server,
                                                         bats_env_parameters.vc_cred.user,
                                                         bats_env_parameters.vc_cred.pwd,
                                                         bats_env_parameters.agent_vm)
        ip = vm_summary.guest.ipAddress
        assert ip is not None
        self.agent_ip = ip

    def config(self, bats_env_parameters, queue):
        ret = False
        try:

            Utilities.add_manual_pool(bats_env_parameters.broker_ip,
                                      'administrator',
                                      'ca$hc0w',
                                      'hovdi',
                                      bats_env_parameters.vc_server,
                                      bats_env_parameters.agent_vm,
                                      bats_env_parameters.pool_name)

            self.webCommander.entitle(bats_env_parameters.vc_server,
                                      bats_env_parameters.vc_cred.user_for_web_cmd,
                                      bats_env_parameters.vc_cred.pwd,
                                      bats_env_parameters.broker_vm,
                                      bats_env_parameters.pool_name)

            if bats_env_parameters.parameters.enable_non_default:
                logger.info('do the non default config for agent, then to restart.')
                Utilities.enable_none_default(type='agent', ip=self.agent_ip)

            rc = STAFHelper.run_command_sync(self.agent_ip,
                                             'reg /s //10.117.45.89/view/tools/scripts/BAT/turn-off-auto-logon.reg')
            time.sleep(10)
            logger.info('Agent rc %s for turning off auto logon' % rc)

            rc = STAFHelper.run_command_sync(self.agent_ip,
                                             '//10.117.45.89/view/tools/scripts/BAT/pingbroker.bat %s' %
                                             STAFHelper.get_machine_nickname(bats_env_parameters.broker_ip))
            time.sleep(30)
            logger.info('Agent rc %s for ping broker' % rc)

            self.webCommander.power_off_on_vm(bats_env_parameters.vc_server,
                                              bats_env_parameters.vc_cred.user_for_web_cmd,
                                              bats_env_parameters.vc_cred.pwd,
                                              bats_env_parameters.agent_vm)
            time.sleep(120)
            logger.info('Agent all done with success.')
            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            queue.put(ret)

    '''
        Before install, it will revert screen shot and copy the installer to the remote machine.

        And restart the machine to avoid the 1618 error. -- Drop it as change to API call to execute program in the VM.

    '''

    def before_install(self):
        ret = False
        try:
            self.webCommander.install_prepare(self.bats_env_parameters.vc_server,
                                              self.bats_env_parameters.vc_cred.user_for_web_cmd,
                                              self.bats_env_parameters.vc_cred.pwd,
                                              self.bats_env_parameters.agent_vm)

            if self.bats_env_parameters.parameters.enable_fips:
                Utilities.enable_fips(vc_server=self.bats_env_parameters.vc_server,
                                      vc_user=self.bats_env_parameters.vc_cred.user,
                                      vc_pwd=self.bats_env_parameters.vc_cred.pwd,
                                      vm=self.bats_env_parameters.agent_vm)

            ''' As the restoration may change the IP address, so here just refresh the IP. '''
            logger.info(' get the agent ip address ')
            vm_summary = VMUtil.get_vm_summary_by_name_quick(self.bats_env_parameters.vc_server,
                                                             self.bats_env_parameters.vc_cred.user,
                                                             self.bats_env_parameters.vc_cred.pwd,
                                                             self.bats_env_parameters.agent_vm)
            vm_agent_ip = vm_summary.guest.ipAddress
            assert vm_agent_ip is not None
            self.agent_ip = vm_agent_ip
            logger.info(' copy the agent installer file to the remote agent. ')
            STAFHelper.copy_from_local_to_remote_temp(self.bats_env_parameters.parameters.agent_build_path,
                                                      self.agent_ip)
            logger.info(' copy %s finish.. ' % self.bats_env_parameters.parameters.agent_build_path)
            ''' Add time buffer here is because catch the 1618 error if start the installation right now. '''
            time.sleep(100)
            ret = True
        except Exception, e:
            ret = False
            logger.info(e)
        finally:
            return ret

    def install_internal(self):
        ret = False
        try:
            """ Install the MSI. """
            installer_path = os.path.join('C:\\temp', os.path.basename(self.bats_env_parameters.parameters.agent_build_path))
            logger.info(">>> Starting view agent installer")
            ADDLOCAL_ALL = 'ALL'

            if self.bats_env_parameters.parameters.enable_fips:
                msi_v_args = '"/qn ' \
                             'RebootYesNo=No ' \
                             'REBOOT=ReallySuppress ' \
                             'SUPPRESS_RUNONCE_CHECK=1 ' \
                             'VDM_FIPS_ENABLED=1 ' \
                             'ADDLOCAL=\"%s\""' % ADDLOCAL_ALL
            else:
                msi_v_args = '"/qn ' \
                             'RebootYesNo=No ' \
                             'REBOOT=ReallySuppress ' \
                             'SUPPRESS_RUNONCE_CHECK=1 ' \
                             'ADDLOCAL=\"%s\""' % ADDLOCAL_ALL

            cmd_and_args = [
                # installer_path,
                '/s',  # MSI slient install
                '/v',  # MSI /v option
                msi_v_args]
            logger.info('Starting subprocess:\n    %s' % (' '.join(cmd_and_args)))

            staf_command = ' '.join(cmd_and_args)
            result_install_agent = VMUtil.execute_program_in_vm(self.bats_env_parameters.vc_server,
                                                                self.bats_env_parameters.vc_cred.user,
                                                                self.bats_env_parameters.vc_cred.pwd,
                                                                self.bats_env_parameters.agent_vm,
                                                                installer_path, staf_command, Domain_cred.user,
                                                                Domain_cred.pwd)
            if result_install_agent == 0 or result_install_agent == 3010:
                logger.info("Agent installation is done with success.")
                ret = True
            else:
                logger.info("Agent installation is done with fail, error code is : " + str(result_install_agent))

        except Exception, e:
            ret = False
            logger.info(e)
        finally:
            return ret

    def install(self, bats_env_parameters, queue, times=1):
        ret = False
        try:
            if self.needs_install():
                ''' Try one more time for the installation failure. '''
                if not self.before_install():
                    if not self.before_install():
                        logger.info('Agent installation before error, break the installation.')
                        return
                if not self.install_internal():
                    if times != 2:
                        if not self.install(bats_env_parameters, queue, times=2):
                            logger.info('Agent installation error, break the installation.')
                            return
                    else:
                        return
                ret = True
            else:
                ret = True
        except Exception, e:
            logger.info(e)
        finally:
            queue.put(ret)

    ''' No need to do the validation here, just use it as a marker. '''

    def valid_installation(self, handle):
        return True

    """
        To compare the installed build version with the latest recommend build version,
        if same, not need to do the installation.

        TODO: To handle the power off state of vm machine.

    """

    def install2(self, bats_env_parameters, queue):
        pass

    def needs_install(self):
        installed_build_version = Utilities.get_installed_product_version(self.agent_ip)
        logger.info('Agent installed build : ' + installed_build_version)
        if installed_build_version != None:
            if installed_build_version.find(str(self.bats_env_parameters.parameters.agent_build_no)) != -1:
                return False
        return True


class BrokerRunner(AbstractBATsEnvBase):
    def __init__(self):
        self.webCommander = WebCommander()
        self.handle = ''

    @property
    def broker_name(self):
        return self.broker_name

    @broker_name.setter
    def broker_name(self, name):
        self.broker_name = name

    def config(self, bats_env_parameters):
        """ Still leverage features of web commander here. """

        Utilities.add_license(bats_env_parameters.parameters.bat_env_no, bats_env_parameters.license)

        self.webCommander.add_vc(bats_env_parameters.vc_server,
                                 bats_env_parameters.vc_cred.user_for_web_cmd,
                                 bats_env_parameters.vc_cred.pwd,
                                 bats_env_parameters.broker_vm)

        """
        Enable NativeBlast, ServerInDesktop, Lagecy Agent
        """
        logger.info("Enable NativeBlast, ServerInDesktop, Lagecy Agent")
        STAFHelper.run_command_async(bats_env_parameters.broker_ip,
                                     '//10.117.45.89/view/tools/scripts/BAT/AllowAllThree.bat')
        time.sleep(180)

        if bats_env_parameters.parameters.enable_non_default:
            logger.info('do the non default config for broker, then to restart.')
            Utilities.enable_none_default(type='broker',
                                          vc_server=bats_env_parameters.vc_server,
                                          vm=bats_env_parameters.broker_vm,
                                          ip=bats_env_parameters.broker_ip,
                                          vm_name=self.broker_name)
            time.sleep(50)
            self.webCommander.power_off_on_vm(bats_env_parameters.vc_server,
                                              bats_env_parameters.vc_cred.user_for_web_cmd,
                                              bats_env_parameters.vc_cred.pwd,
                                              bats_env_parameters.broker_vm)
            time.sleep(300)

        logger.info("Broker all done with success.")

        return True

    @staticmethod
    def after_install(bats_env_parameters):
        """
            All of these workflow are followed the web commander to config broker.
            Any question, please refer to the source code of web commander
            at installview.ps(The part of install broker).

        :param bats_env_parameters:
        :param queue:
        """
        ret = False
        try:
            '''unzip the viewtest to temp folder'''
            Utilities.unzip(bats_env_parameters.parameters.view_test_build_path, 'c:/temp')

            '''back up the dll file and replace with test dll'''
            logger.info('back up the dll file and replace with test dll')
            cmd_let_dll = 'C:/Program Files/VMware/VMware View/Server/bin/PowershellServiceCmdlets.dll'
            cmd_let_dll_bk = 'C:/Program Files/VMware/VMware View/Server/bin/PowershellServiceCmdlets.dll.orig'
            STAFHelper.copy_from_remote_to_remote(cmd_let_dll, cmd_let_dll_bk, bats_env_parameters.broker_ip)
            STAFHelper.fs_request(bats_env_parameters.broker_ip, 'DELETE ENTRY %s CONFIRM' % cmd_let_dll)
            cmd_let_dll_view_test = 'C:/temp/powershell.dir/PowershellServiceCmdlets-Ext64.dll'
            STAFHelper.copy_from_local_to_remote(cmd_let_dll_view_test, cmd_let_dll, bats_env_parameters.broker_ip)

            ''' install the test dll '''
            logger.info('install the test dll')
            result = STAFHelper.fs_request(bats_env_parameters.broker_ip,
                                           'list directory c:/windows/Microsoft.Net/Framework64/ recurse name InstallUtil')
            install_util_path = 'c:/windows/Microsoft.Net/Framework64/' + result.resultObj[0].replace("\\", "/")
            cmd_let_dll = "\\\"" + cmd_let_dll + "\\\""
            STAFHelper.run_command_sync(bats_env_parameters.broker_ip,
                                        "\"" + install_util_path + " " + cmd_let_dll + "\"")
            '''
                set the exection policy, here only can run with async mode with STAF, cannot track the real rc.
                only wait 20 seconds here.
            '''
            logger.info('set the exection policy')
            rc_set_power_shell = STAFHelper.run_command_async(bats_env_parameters.broker_ip,
                                                              'powershell.exe -ExecutionPolicy UNRESTRICTED')
            time.sleep(20)

            ''' unzip and config api operator '''
            logger.info('unzip and config api operator')
            api_opt_path = os.path.join('C:/temp/',
                                        os.path.basename(bats_env_parameters.parameters.view_api_operator_build_path))
            STAFHelper.copy_from_local_to_remote_temp(bats_env_parameters.parameters.view_api_operator_build_path,
                                                      bats_env_parameters.broker_ip)

            rc_zip = STAFHelper.run_command_sync(bats_env_parameters.broker_ip,
                                                 '//10.117.45.89/view/tools/WinBATool/7-Zip/7z.exe x %s -o%s -y' %
                                                 (api_opt_path, 'C:/temp/'))
            assert int(rc_zip) == 0, 'unzip operator api error.'

            logger.info('copy the default api xml file.')
            view_api_cli_defaults_local = 'c:/BATs/viewapicli-defaults_' + bats_env_parameters.broker_ip + '.xml'
            view_api_cli_defaults_remote = 'c:/temp/view-api-operator/viewapicli-defaults.xml'
            STAFHelper.copy_from_local_to_remote(view_api_cli_defaults_local,
                                                 view_api_cli_defaults_remote,
                                                 bats_env_parameters.broker_ip)

            STAFHelper.run_command_sync(bats_env_parameters.broker_ip,
                                        '//10.117.45.89/view/tools/scripts/BAT/addClientSSLSecureProtocols.bat')
            time.sleep(150)

            broker_name = STAFHelper.get_computer_name(bats_env_parameters.broker_ip)
            BrokerRunner.broker_name = broker_name
            logger.info('Broker Name is : ' + broker_name)

            STAFHelper.run_command_async(bats_env_parameters.broker_ip,
                                         '//10.117.45.89/view/tools/scripts/Wincdk_BATs_config_broker.bat %s %s' %
                                         (broker_name, bats_env_parameters.broker_ip))

            time.sleep(150)
            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            return ret

    def install(self, bats_env_parameters, queue):
        ret = False
        queue.put(ret)

    ''' here is just do some prepare work for the installation. '''

    def before_install(self, bats_env_parameters):
        ret = False
        try:
            self.webCommander.install_prepare(bats_env_parameters.vc_server,
                                              bats_env_parameters.vc_cred.user_for_web_cmd,
                                              bats_env_parameters.vc_cred.pwd,
                                              bats_env_parameters.broker_vm)

            if bats_env_parameters.parameters.enable_fips:
                Utilities.enable_fips(vc_server=bats_env_parameters.vc_server,
                                      vc_user=bats_env_parameters.vc_cred.user,
                                      vc_pwd=bats_env_parameters.vc_cred.pwd,
                                      vm=bats_env_parameters.broker_vm)

            STAFHelper.copy_from_local_to_remote_temp(bats_env_parameters.parameters.broker_build_path,
                                                      bats_env_parameters.broker_ip)
            time.sleep(60)

            logger.info('before install, delete all the install logs if exists.')
            result = STAFHelper.fs_request(bats_env_parameters.broker_ip,
                                           'list directory %temp% name vmmsi.log*')
            vmmsi_log_path_list = result.resultObj
            ' if exists, then delete it.'
            if not vmmsi_log_path_list:
                for log in vmmsi_log_path_list:
                    STAFHelper.fs_request(bats_env_parameters.broker_ip,
                                          'delete entry %temp%/' + log + ' confirm')

            time.sleep(30)
            ret = True
        except Exception, e:
            ret = False
            logger.info(e)
        finally:
            return ret

    def install2(self, bats_env_parameters, queue, times=1):
        ret = False
        try:
            if not BrokerRunner.needs_install(bats_env_parameters):
                ret = True
                return

            ''' Try one more time for the installation failure. '''
            if not self.before_install(bats_env_parameters):
                if not self.before_install(bats_env_parameters):
                    logger.info('Broker installation before error, break the installation.')
                    return

            if not BrokerRunner.install_internal(bats_env_parameters):
                if times == 2:
                    return
                if not self.install2(bats_env_parameters, queue, times=2):
                    logger.info('Broker installation error, break the installation.')
                    return

            if not self.after_install(bats_env_parameters):
                if not self.after_install(bats_env_parameters):
                    logger.info('Broker installation after error, break the installation.')
                    return

            if not self.config(bats_env_parameters):
                if not self.config(bats_env_parameters):
                    logger.info('Broker installation config error, break the installation.')
                    return

            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            queue.put(ret)

    @staticmethod
    def install_internal(bats_env_parameters):
        ret = False
        try:
            installer_path = os.path.join('C:\\temp',
                                          os.path.basename(bats_env_parameters.parameters.broker_build_path))
            logger.info(">>> Starting view broker installer ...")

            if bats_env_parameters.parameters.enable_fips:
                msi_v_args = '/qn ' \
                             'ADDLOCAL=ALL ' \
                             'VDM_SERVER_INSTANCE_TYPE=1 ' \
                             'VDM_FIPS_ENABLED=1 ' \
                             'VDM_SERVER_RECOVERY_PWD=111111'
            else:
                msi_v_args = '/qn ' \
                             'ADDLOCAL=ALL ' \
                             'VDM_SERVER_INSTANCE_TYPE=1 ' \
                             'VDM_SERVER_RECOVERY_PWD=111111'

            cmd_and_args = [
                # installer_path,
                '/s',  # MSI slient install
                '/v',  # MSI /v option
                msi_v_args]
            logger.info('Starting subprocess:\n    %s' % (' '.join(cmd_and_args)))

            staf_command = ' '.join(cmd_and_args)
            result_install_broker = VMUtil.execute_program_in_vm(bats_env_parameters.vc_server,
                                                                 bats_env_parameters.vc_cred.user,
                                                                 bats_env_parameters.vc_cred.pwd,
                                                                 bats_env_parameters.broker_vm,
                                                                 installer_path, staf_command, Domain_cred.user,
                                                                 Domain_cred.pwd)

            if result_install_broker == 0 or result_install_broker == 3010:
                logger.info("Broker installation is done with success.")
                ret = True
            else:
                logger.info("Broker installation is done with fail, error code is : " + str(result_install_broker))
        except Exception, e:
            logger.info(e)
        finally:
            return ret

    @staticmethod
    def valid_installation(bats_env_parameters, handle):
        return True

    @staticmethod
    def needs_install(bats_env_parameters):
        return True


class RDSHRunner(AbstractBATsEnvBase):
    def __init__(self, bats_env_parameters):
        self.webCommander = WebCommander()
        self.bats_env_parameters = bats_env_parameters
        vm_summary = VMUtil.get_vm_summary_by_name_quick(bats_env_parameters.vc_server,
                                                         bats_env_parameters.vc_cred.user,
                                                         bats_env_parameters.vc_cred.pwd,
                                                         bats_env_parameters.rds_vm)
        vm_agent_ip = vm_summary.guest.ipAddress
        self.rdsh_ip = vm_agent_ip

    def config(self):
        ret = False
        try:
            self.webCommander.add_rds_app_pool(self.bats_env_parameters.vc_server,
                                               self.bats_env_parameters.vc_cred.user_for_web_cmd,
                                               self.bats_env_parameters.vc_cred.pwd,
                                               self.bats_env_parameters.broker_vm,
                                               self.bats_env_parameters.rds_hostname)
            self.webCommander.restart_vm(self.bats_env_parameters.vc_server,
                                         self.bats_env_parameters.vc_cred.user_for_web_cmd,
                                         self.bats_env_parameters.vc_cred.pwd,
                                         self.bats_env_parameters.rds_vm)
            # After entitle app pool with the same user, the entitlement of desktop pool will be lost. So re-add
            if not self.bats_env_parameters.skip_agent:
                self.webCommander.entitle(self.bats_env_parameters.vc_server,
                                          self.bats_env_parameters.vc_cred.user_for_web_cmd,
                                          self.bats_env_parameters.vc_cred.pwd,
                                          self.bats_env_parameters.broker_vm,
                                          self.bats_env_parameters.pool_name)

            Utilities.add_rds_pool(self.bats_env_parameters.parameters.bat_env_no)

            self.webCommander.entitle(self.bats_env_parameters.vc_server,
                                      self.bats_env_parameters.vc_cred.user_for_web_cmd,
                                      self.bats_env_parameters.vc_cred.pwd,
                                      self.bats_env_parameters.broker_vm,
                                      "Win2012RDS")

            time.sleep(300)
            STAFHelper.run_command_async(self.rdsh_ip,
                                         '//10.117.45.89/view/tools/scripts/BAT/logoff.bat')
            time.sleep(20)
            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            return ret

    ''' ON DEVELOPMENT '''

    def config2(self, bats_env_parameters):
        ret = False
        try:
            if not self.webCommander.add_farm(bats_env_parameters.vc_server, bats_env_parameters.rds_vm):
                ''' As the broker will not be installed every time, so fail means that the farm has already created '''
                self.webCommander.rm_app()
                self.webCommander.rm_rdsh_server_from_farm()

            self.webCommander.add_rds_to_farm(bats_env_parameters.vc_server, bats_env_parameters.rds_vm,
                                              bats_env_parameters.rds_hostname)
            self.webCommander.add_app_pool(bats_env_parameters.vc_server, bats_env_parameters.broker_vm)

            self.webCommander.restart_vm(bats_env_parameters.vc_server, bats_env_parameters.rds_vm)
            # After entitle app pool with the same user, the entitlement of desktop pool will be lost. So re-add
            if not bats_env_parameters.skip_agent:
                self.webCommander.entitle(bats_env_parameters.vc_server, bats_env_parameters.broker_vm,
                                          bats_env_parameters.pool_name)
            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            return ret

    '''
        Before install, it will revert screen shot and copy the installer to the remote machine.

        And restart the machine to avoid the 1618 error.

    '''

    def before_install(self):
        ret = False
        try:
            self.webCommander.install_prepare(self.bats_env_parameters.vc_server,
                                              self.bats_env_parameters.vc_cred.user_for_web_cmd,
                                              self.bats_env_parameters.vc_cred.pwd,
                                              self.bats_env_parameters.rds_vm)

            if self.bats_env_parameters.parameters.enable_fips:
                Utilities.enable_fips(vc_server=self.bats_env_parameters.vc_server,
                                      vc_user=self.bats_env_parameters.vc_cred.user,
                                      vc_pwd=self.bats_env_parameters.vc_cred.pwd,
                                      vm=self.bats_env_parameters.rds_vm)

            ''' As the restoration may change the IP address, so here just refresh the IP. '''
            vm_summary = VMUtil.get_vm_summary_by_name_quick(self.bats_env_parameters.vc_server,
                                                             self.bats_env_parameters.vc_cred.user,
                                                             self.bats_env_parameters.vc_cred.pwd,
                                                             self.bats_env_parameters.rds_vm)

            vm_agent_ip = vm_summary.guest.ipAddress
            logger.info(vm_agent_ip)
            self.rdsh_ip = vm_agent_ip
            if self.rdsh_ip is None:
                return
            logger.info(' copy the rdsh installer file to the remote agent. ')
            # here need to try the upload file util by vm.
            STAFHelper.copy_from_local_to_remote_temp(self.bats_env_parameters.parameters.rdsh_build_path,
                                                      self.rdsh_ip)
            time.sleep(100)
            ret = True
        except Exception, e:
            ret = False
            logger.info(e)
        finally:
            return ret

    def install_internal(self):
        ret = False
        try:
            """ Install the MSI. """
            installer_path = os.path.join('C:\\temp', os.path.basename(self.bats_env_parameters
                                                                       .parameters.rdsh_build_path))
            logger.info(">>> Starting view agent installer")

            msi_v_args = '"/qn ' \
                         'RebootYesNo=No ' \
                         'REBOOT=ReallySuppress ' \
                         'SUPPRESS_RUNONCE_CHECK=1 ' \
                         'ADDLOCAL=\"Core\" ' \
                         'VDM_SERVER_USERNAME=hovdi\\administrator ' \
                         'VDM_SERVER_PASSWORD=ca$hc0w ' \
                         'VDM_SERVER_NAME=' + self.bats_env_parameters.broker_ip + '"'

            cmd_and_args = [
                # installer_path,
                '/s',  # MSI slient install
                '/v',  # MSI /v option
                msi_v_args]
            logger.info('Starting subprocess:\n    %s' % (' '.join(cmd_and_args)))

            staf_command = ' '.join(cmd_and_args)
            result_install_agent = VMUtil.execute_program_in_vm(self.bats_env_parameters.vc_server,
                                                                self.bats_env_parameters.vc_cred.user,
                                                                self.bats_env_parameters.vc_cred.pwd,
                                                                self.bats_env_parameters.rds_vm,
                                                                installer_path, staf_command, Domain_cred.user,
                                                                Domain_cred.pwd)
            if result_install_agent == 0 or result_install_agent == 3010:
                logger.info("Agent installation is done with success.")
                ret = True
            else:
                logger.info("Agent installation is done with fail, error code is : " + str(result_install_agent))

        except Exception, e:
            ret = False
            logger.info(e)
        finally:
            return ret

    def install(self, queue):
        ret = False
        queue.put(ret)

    def install2(self, queue, times=1):
        ret = False
        try:
            if RDSHRunner.needs_install():
                ''' Try one more time for the installation failure. '''
                if not self.before_install():
                    if not self.before_install():
                        logger.info('RDSH installation before error, break the installation.')
                        return
                if not RDSHRunner.install_internal():
                    if times != 2:
                        if not self.install2(queue, times=2):
                            logger.info('RDSH installation error, break the installation.')
                            return
                    else:
                        return
                if not self.bats_env_parameters.skip_rdsh_conf:
                    self.config()
                ret = True
            else:
                ret = True
        except Exception, e:
            logger.info(e)
        finally:
            queue.put(ret)

    @staticmethod
    def valid_installation(vm_agent_ip, handle):
        pass

    @staticmethod
    def needs_install():
        return True


class ClientRunner(AbstractBATsEnvBase):
    def __init__(self, bats_env_parameters):
        self.bats_env_parameters = bats_env_parameters
        self.clientIP = self.get_valid_client_ip()
        self.client_build_path = self.get_client_build_path(bats_env_parameters)
        assert (self.client_build_path != ""), "Client is not up now, please to check the physical machine."
        assert (self.clientIP != 'NA'), "Client is not up now, please to check the physical machine."
        logger.info("client ip %s" % self.clientIP)
        logger.info("client build path %s" % self.client_build_path)
        self.test_root = "C:\\tests\\wincdk_BATs\\depot\\non-framework\\BFG\\view-monaco\\Linux\\"

    def config(self, bats_env_parameters):
        """
            Just refactor code to run test cases in client side.
            Do not familiar with the details.

        """
        self.prepare_source_files()
        self.sync_test_cases()
        self.generate_automation_ini()
        self.setup_before_run_tc()
        time.sleep(20)

    def generate_racetrack_id(self):
        os_name = STAFHelper.get_os_name(self.clientIP)
        logger.info(os_name)
        racetrack_id = RacetrackHelper.generate_testset_id(str(self.bats_env_parameters.parameters.client_build_num),
                                                           os_name,
                                                           str(self.bats_env_parameters.parameters.agent_build_no),
                                                           str(self.bats_env_parameters.parameters.client_branch))

        logger.info("The racetrack id is : %s" % racetrack_id)
        return racetrack_id

    def prepare_source_files(self):
        ''' It's should be the required step for the client exection, will enhance later. '''
        STAFHelper.run_command_sync(self.clientIP, 'echo %s > c:/buildnum.txt' % self.bats_env_parameters.
                                    parameters.client_build_num)
        STAFHelper.run_command_sync(self.clientIP, 'echo %s > c:/obsb.txt' % self.bats_env_parameters.
                                    parameters.client_build_type)

        ''' As don't know the UTIL user and password, just use myself here. '''
        STAFHelper.run_command_sync3(self.clientIP, 'net use \\\\10.117.45.89 vmware /user:wangyan')

        assert STAFHelper.run_command_sync3(self.clientIP,
                                            'copy /D /Y \\\\10.117.45.89\\view\\tools\\scripts\\BAT C:\\').rc == 0, \
            'copy BAT files error.'

        assert STAFHelper.run_command_sync3(self.clientIP,
                                            'copy /Y \\\\10.117.45.89\\view\\tools\\hosts '
                                            'C:\\Windows\\System32\\drivers\\etc').rc == 0, 'copy hosts error.'

    def setup_before_run_tc(self):
        STAFHelper.run_command_sync(self.clientIP, "c:\\BATs\\client_prepare.bat")

    def generate_automation_ini(self):
        automation_ini = "c:\\BATs\\automation.ini"
        automation_template_ini = "c:\\BATs\\automation_template.ini"

        Utilities.silent_remove(automation_ini)
        broker_machine_name = STAFHelper.get_machine_nickname(self.bats_env_parameters.broker_ip)
        racetrack_id = self.generate_racetrack_id()
        with open(automation_ini, "wt") as fout:
            with open(automation_template_ini, "rt") as fin:
                for line in fin:
                    line = line.replace('${pool_name}', self.bats_env_parameters.pool_name). \
                        replace('${broker_machine_name}', broker_machine_name). \
                        replace('${broker_ip}', self.bats_env_parameters.broker_ip). \
                        replace('${vc_server}', self.bats_env_parameters.vc_server). \
                        replace('${client_branch}', self.bats_env_parameters.parameters.client_branch). \
                        replace('${client_build_type}', self.bats_env_parameters.parameters.client_build_type). \
                        replace('${testset_id}', racetrack_id). \
                        replace('${agent_platform_ini}', self.bats_env_parameters.pool_name). \
                        replace('${broker_name}', STAFHelper.get_computer_name(self.bats_env_parameters.broker_ip)). \
                        replace('${esxi_ip}', self.bats_env_parameters.esxi_ip)
                    fout.write(line)

        STAFHelper.copy_from_local_to_remote(automation_ini, self.test_root + "\\conf\\automation.ini", self.clientIP)

    def sync_test_cases(self):
        STAFHelper.run_command_sync(self.clientIP, 'xcopy /I /Y /E \\\\10.117.45.89\\view\\tools\\scripts\\source'
                                                   '\\Linux %s c:\\bat_p4Sync.log' % self.test_root)
        STAFHelper.run_command_sync(self.clientIP, 'del %s\\conf\\result.txt /f /q' % self.test_root)
        STAFHelper.run_command_sync(self.clientIP, 'del %s\\conf\\logs\\*.* /f /q' % self.test_root)

    def __wait_client_up(self, timeout=4800, interval=300):
        ret = False
        elapsed_time = 0
        logger.info("Ping with new method " + self.clientIP + "...")
        while elapsed_time < timeout:
            try:
                output = subprocess.check_output("ping -n 1 " + self.clientIP)
                if 'TTL=' in output:
                    logger.info(self.clientIP + " is online!")
                    ret = True
                    break
            except Exception, e:
                continue
            elapsed_time += interval
            time.sleep(interval)
        return ret

    def verify_client_via_ip(self):
        return self.__wait_client_up()

    def verify_client_via_staf(self):
        return STAFHelper.staf_ping_timeout(self.bats_env_parameters.client_ip)

    def get_ip_2(self):
        try:
            return socket.gethostbyname(self.bats_env_parameters.client_name)
        except Exception, e:
            return "NA"

    def get_valid_client_ip(self):
        if not self.verify_client_via_staf():
            return self.get_ip_2()
        return self.bats_env_parameters.client_ip

    def restore(self):
        try:
            logger.info(' start the restoring... ')
            if not self.verify_client_via_staf():
                logger.info("STAF is not running on the client, quit.")
                return False

            self.go_into_winpe()
            ''' Ping success, means that the machine doesn't go into the WinPE success. So, do it again. '''
            if STAFHelper.staf_ping(self.clientIP):
                self.go_into_winpe()

            time.sleep(300)
            # Wait up to 1 hr for the system to be restored and start up.
            if not self.verify_client_via_ip():
                logger.info("The client cannot be reached by Ping IP after 1 hr.")
                return False

            logger.info(' success ping with ip after restoring, then to ping with STAF...')
            if not self.verify_client_via_staf():
                logger.info("The client cannot be reached by STAF after restoring, " \
                            "canceling the job. Known issue is: Cannot login with hovdi/admin")
                return False

            logger.info(' restoring success... ')
            return True
        except Exception, e:
            logger.info(e)
            return False

    def go_into_winpe(self):
        restore_image_command = 'cmd /k C:/tests/SCRestore.bat ' + \
                                self.bats_env_parameters.client_image + ' NEWCONSOLE'
        logger.info(restore_image_command)
        STAFHelper.run_command_async(self.clientIP, restore_image_command)
        time.sleep(5)
        STAFHelper.run_command_async(self.clientIP, 'shutdown /r /f')
        # wait 2 minutes before pinging it, to make sure the previous shutdown command has taken place.
        time.sleep(120)

    def __before_install(self, bats_env_parameters):
        if bats_env_parameters.is_client_vm:
            self.webCommander.install_prepare(bats_env_parameters.vc_server,
                                              bats_env_parameters.vc_cred.user_for_web_cmd,
                                              bats_env_parameters.vc_cred.pwd,
                                              bats_env_parameters.client_vm)

        if bats_env_parameters.restore_machine:
            assert bool(self.restore()), "restoring fail, break the workflow in __before_install. "

        if bats_env_parameters.parameters.enable_fips:
            Utilities.enable_fips(is_vm_machine=False, ip=self.clientIP)

        if not STAFHelper.copy_from_local_to_remote_temp(self.client_build_path, self.clientIP):
            logger.info("copy client install error with STAF.")
            return False

        logger.info('all things done before install build in client... ')
        return True

    def get_client_build_path(self, bats_env_parameters):
        client_arch = STAFHelper.get_os_arch(self.clientIP)
        if client_arch == '64':
            return bats_env_parameters.parameters.client_build_path_64
        if client_arch == '32':
            return bats_env_parameters.parameters.client_build_path_32
        return ""

    def install(self, bats_env_parameters, queue):
        ret = False
        try:
            if not self.__before_install(bats_env_parameters):
                ret = False

            msi_v_args = self.__get_install_cmd(bats_env_parameters, 'install')
            if msi_v_args == '':
                logger.info("the install command is null.")
                ret = False

            if not self.install2(bats_env_parameters, msi_v_args, 'install'):
                ret = False

            self.config(bats_env_parameters)
            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            queue.put(ret)

    def reinstall(self, bats_env_parameters):
        try:
            if not self.__before_install(bats_env_parameters):
                return False

            msi_v_args_uninstall = self.__get_install_cmd(bats_env_parameters, 'uninstall')
            if msi_v_args_uninstall == '':
                logger.info("the uninstall command is null.")
                return False

            if not self.install2(bats_env_parameters, msi_v_args_uninstall, 'uninstall'):
                return False

            msi_v_args_install = self.__get_install_cmd(bats_env_parameters, 'install')
            if msi_v_args_install == '':
                logger.info("the install command is null.")
                return False

            if not self.install2(bats_env_parameters, msi_v_args_install, 'install'):
                return False

            self.config(bats_env_parameters)
            return True
        except Exception, e:
            logger.info(e)
            return False

    @staticmethod
    def __get_install_cmd(bats_env_parameters, action):
        if action == 'install':
            if bats_env_parameters.parameters.enable_fips:
                return '"/qn ' \
                       'RebootYesNo=No ' \
                       'REBOOT=ReallySuppress ' \
                       'VDM_FIPS_ENABLED=1 ' \
                       'ADDLOCAL=ALL "'
            else:
                return '"/qn ' \
                       'RebootYesNo=No ' \
                       'REBOOT=ReallySuppress ' \
                       'ADDLOCAL=ALL "'
        if action == 'uninstall':
            return '"/qn ' \
                   'RebootYesNo=No ' \
                   'REBOOT=ReallySuppress ' \
                   'REMOVE=ALL "'
        return ""

    def __compose_full_install_cmd(self, msi_v_args):
        installer_path = os.path.join('C:/temp/', os.path.basename(self.client_build_path))
        cmd_and_args = [
            installer_path,
            '/s',  # MSI slient install
            '/v',  # MSI /v option
            msi_v_args]
        logger.info('Starting subprocess:\n    %s' % (' '.join(cmd_and_args)))
        return ' '.join(cmd_and_args)

    def install2(self, bats_env_parameters, msi_v_args, action):

        logger.info(">>> Starting view client installer")
        try:
            staf_command = self.__compose_full_install_cmd(msi_v_args)
            logger.info("command %s" % staf_command)
            result_install_client = STAFHelper.run_command_async(self.clientIP, staf_command)
            if result_install_client.rc != 0:
                logger.info("Installation failed with error code %d" % result_install_client.rc)
                return False

            'No need to check the installation result immediately, just wait 5 minutes here.'
            time.sleep(3)
            if not self.valid_installation(str(result_install_client.resultObj), action):
                return False

            logger.info("Client %s success, then to restart." % action)
            STAFHelper.run_command_async(self.clientIP, 'shutdown -r -t 0')
            ''' Here just set the timeout to 15 minutes. '''
            time.sleep(60)

            if not STAFHelper.staf_ping_timeout(self.clientIP, timeout=900):
                logger.info("Client restart fail after the installation.")
                return False

            logger.info("Client all done with success")
            return True
        except Exception as ex1:
            logger.info(ex1)
            return False

    def valid_installation(self, handle, action):
        """ 40 minutes """
        timeout = 40 * 60
        elapsed_time = 0
        logger.info(' Start the validation of client %s. Timeout is 40 minutes. ' % action)
        while elapsed_time < timeout:
            try:
                result_query_handle = STAFHelper.submit(self.clientIP,
                                                        'process', 'query handle %s' % handle)
                assert result_query_handle.rc == 0, 'client installation process was fail to query, please check.'
                mc = unmarshall(result_query_handle.result)
                entry_map = mc.getRootObject()
                if None != entry_map['endTimestamp']:
                    if action == 'install':
                        return self.validate_install(entry_map['rc'])
                    if action == 'uninstall':
                        return self.validate_uninstall(entry_map['rc'])
            except Exception as e:
                logger.info(e)
                pass
            elapsed_time += 60
            time.sleep(60)

    @staticmethod
    def validate_uninstall(return_code):
        """
        :param return_code: 1605 means, no product has been installed.
                            3010 means, success but needs restart.
        :return:
        """
        if return_code == '1605' or return_code == '3010':
            logger.info('The client uninstallation is done with success. ')
            return True
        else:
            logger.info('The client uninstallation is done with fail, will check the installation logs, '
                        'Result : ' + return_code)
            return False

    @staticmethod
    def validate_install(return_code):
        """
        :param return_code: 0 means, success
                            3010 means, success but needs restart.
        :return:
        """
        if return_code == '0' or return_code == '3010':
            logger.info('The client installation is done with success. ')
            return True
        else:
            logger.info('The client installation is done with fail, will check the installation logs, '
                        'Result : ' + return_code)
            return False

    def run_tc(self):
        """
            trigger the test cases run in the client side.

        """
        run_cmd = 'c:/BATs/wincdk-run-tc.bat /N %s /O %s /S WinCDKBATs' % \
                  (self.bats_env_parameters.parameters.client_build_num,
                   self.bats_env_parameters.parameters.client_build_type)
        logger.info(run_cmd)
        STAFHelper.run_command_async(self.clientIP, run_cmd)


class ClientVMRunner(AbstractBATsEnvBase):
    def __init__(self, bats_env_parameters):
        self.bats_env_parameters = bats_env_parameters
        self.webCommander = WebCommander()
        self.log_pre = '[ Client ] '
        vm_summary = VMUtil.get_vm_summary_by_name_quick(bats_env_parameters.vc_server,
                                                         bats_env_parameters.vc_cred.user,
                                                         bats_env_parameters.vc_cred.pwd,
                                                         bats_env_parameters.client_vm)
        vm_client_ip = vm_summary.guest.ipAddress
        assert vm_client_ip is not None
        self._client_ip = vm_client_ip
        self._client_build_path = None

    @property
    def client_ip(self):
        return self._client_ip

    @client_ip.setter
    def client_ip(self, ip):
        self._client_ip = ip

    @property
    def client_build_path(self):
        return self._client_build_path

    @client_build_path.setter
    def client_build_path(self, build_path):
        self._client_build_path = build_path

    def get_client_arch(self):
        arch = ''
        result = STAFHelper.submit(self._client_ip, 'var', 'resolve string {STAF/Env/PROCESSOR_IDENTIFIER}')
        assert result.rc == 0, 'get client arch error.'
        if result.resultObj.lower().find('64') != -1:
            arch = '64'
        if result.resultObj.lower().find('86') != -1:
            arch = '32'
        return arch

    def get_client_build_path(self, bats_env_parameters):
        client_arch = self.get_client_arch()
        if client_arch == '64':
            return bats_env_parameters.parameters.client_build_path_64
        if client_arch == '32':
            return bats_env_parameters.parameters.client_build_path_32
        return ""

    def config(self, bats_env_parameters):
        STAFHelper.run_command_sync(self._client_ip, 'echo %s > c:/buildnum.txt' % self.bats_env_parameters.
                                    parameters.client_build_num)
        STAFHelper.run_command_sync(self._client_ip, 'echo %s > c:/obsb.txt' % self.bats_env_parameters.
                                    parameters.client_build_type)
        pass

    def install2(self, bats_env_parameters, queue):
        """
            remove the logic with web commander.
        """
        pass

    def before_install(self, bats_env_parameters):
        ret = False
        try:
            self.webCommander.install_prepare(bats_env_parameters.vc_server,
                                              bats_env_parameters.vc_cred.user_for_web_cmd,
                                              bats_env_parameters.vc_cred.pwd,
                                              bats_env_parameters.client_vm)

            ''' As the restoration may change the IP address, so here just refresh the IP. '''
            vm_summary = VMUtil.get_vm_summary_by_name_quick(bats_env_parameters.vc_server,
                                                             bats_env_parameters.vc_cred.user,
                                                             bats_env_parameters.vc_cred.pwd,
                                                             bats_env_parameters.client_vm)
            vm_client_ip = vm_summary.guest.ipAddress
            assert vm_client_ip is not None
            self._client_ip = vm_client_ip

            logger.info(' copy the client installer file to the remote agent. ')
            self._client_build_path = self.get_client_build_path(bats_env_parameters)
            STAFHelper.copy_from_local_to_remote_temp(self._client_build_path,
                                                      self._client_ip)
            logger.info(' copy finish.. ')
            ''' Add time buffer here is because catch the 1618 error if start the installation right now. '''
            time.sleep(100)
            ret = True
        except Exception, e:
            ret = False
            logger.info(e)
        finally:
            return ret

    @staticmethod
    def __get_install_cmd(bats_env_parameters, action):
        if action == 'install':
            if bats_env_parameters.parameters.enable_fips:
                return '"/qn ' \
                       'RebootYesNo=No ' \
                       'REBOOT=ReallySuppress ' \
                       'VDM_FIPS_ENABLED=1 ' \
                       'ADDLOCAL=ALL "'
            else:
                return '"/qn ' \
                       'RebootYesNo=No ' \
                       'REBOOT=ReallySuppress ' \
                       'ADDLOCAL=ALL "'
        if action == 'uninstall':
            return '"/qn ' \
                   'RebootYesNo=No ' \
                   'REBOOT=ReallySuppress ' \
                   'REMOVE=ALL "'
        return ""

    def __compose_full_install_cmd(self, msi_v_args):
        installer_path = os.path.join('C:/temp/', os.path.basename(self._client_build_path))
        cmd_and_args = [
            installer_path,
            '/s',  # MSI slient install
            '/v',  # MSI /v option
            msi_v_args]
        logger.info('Starting subprocess:\n    %s' % (' '.join(cmd_and_args)))
        return ' '.join(cmd_and_args)

    def install_internal(self, msi_v_args, action):

        logger.info(">>> Starting view client installer")
        try:
            staf_command = self.__compose_full_install_cmd(msi_v_args)
            logger.info("command %s" % staf_command)
            result_install_client = STAFHelper.run_command_async(self._client_ip, staf_command)
            if result_install_client.rc != 0:
                logger.info("Installation failed with error code %d" % result_install_client.rc)
                return False

            'No need to check the installation result immediately, just wait 5 minutes here.'
            time.sleep(3)
            if not self.valid_installation(str(result_install_client.resultObj), action):
                return False

            logger.info("Client %s success, then to restart." % action)
            STAFHelper.run_command_async(self._client_ip, 'shutdown -r -t 0')
            ''' Here just set the timeout to 15 minutes. '''
            time.sleep(60)

            if not STAFHelper.staf_ping_timeout(self._client_ip, timeout=900):
                logger.info("Client restart fail after the installation.")
                return False

            logger.info("Client all done with success")
            return True
        except Exception as ex1:
            logger.info(ex1)
            return False

    def install(self, bats_env_parameters, queue, times=1):
        ret = False
        try:
            if not ClientVMRunner.needs_install(bats_env_parameters):
                ret = True
                return

            ''' Try one more time for the installation failure. '''
            if not self.before_install(bats_env_parameters):
                if not self.before_install(bats_env_parameters):
                    logger.info('Client installation before error, break the installation.')
                    return

            msi_v_args = self.__get_install_cmd(bats_env_parameters, 'install')
            if msi_v_args == '':
                logger.info("the install command is null.")
                ret = False

            if not self.install_internal(msi_v_args, 'install'):
                if times == 2:
                    return
                if not self.install(bats_env_parameters, queue, times=2):
                    logger.info('Client installation error, break the installation.')
                    return

            self.config(bats_env_parameters)
            ret = True
        except Exception, e:
            logger.info(e)
        finally:
            queue.put(ret)

    def valid_installation(self, handle, action):
        """ 40 minutes """
        timeout = 40 * 60
        elapsed_time = 0
        logger.info(' Start the validation of client %s. Timeout is 40 minutes. ' % action)
        while elapsed_time < timeout:
            try:
                result_query_handle = STAFHelper.submit(self._client_ip,
                                                        'process', 'query handle %s' % handle)
                assert result_query_handle.rc == 0, 'client installation process was fail to query, please check.'
                mc = unmarshall(result_query_handle.result)
                entry_map = mc.getRootObject()
                if None != entry_map['endTimestamp']:
                    if action == 'install':
                        return self.validate_install(entry_map['rc'])
                    if action == 'uninstall':
                        return self.validate_uninstall(entry_map['rc'])
            except Exception as e:
                logger.info(e)
                pass
            elapsed_time += 60
            time.sleep(60)

    @staticmethod
    def validate_uninstall(return_code):
        """
        :param return_code: 1605 means, no product has been installed.
                            3010 means, success but needs restart.
        :return:
        """
        if return_code == '1605' or return_code == '3010':
            logger.info('The client uninstallation is done with success. ')
            return True
        else:
            logger.info('The client uninstallation is done with fail, will check the installation logs, '
                        'Result : ' + return_code)
            return False

    @staticmethod
    def validate_install(return_code):
        """
        :param return_code: 0 means, success
                            3010 means, success but needs restart.
        :return:
        """
        if return_code == '0' or return_code == '3010':
            logger.info('The client installation is done with success. ')
            return True
        else:
            logger.info('The client installation is done with fail, will check the installation logs, '
                        'Result : ' + return_code)
            return False

    @staticmethod
    def needs_install(bats_env_parameters):
        return True

    def run_tc(self):
        """
            trigger the test cases run in the client side.

            So far, the vm machine is only for DaaS env.

        """
        run_cmd = 'c:/wincdk-run-daas.bat /N %s' % self.bats_env_parameters.parameters.client_build_num
        logger.info(run_cmd)
        STAFHelper.run_command_async(self._client_ip, run_cmd)


class RacetrackHelper(object):
    def __init__(self):
        pass

    @staticmethod
    def generate_testset_id_once(client_build_id, client_os, agent_build_id, client_build_branch):
        http_response_ok = 200
        racetrack_id = None

        try:
            if agent_build_id != '':
                url = 'https://racetrack.eng.vmware.com/TestSetBegin.php?' + \
                      "BuildID=%s&" \
                      "User=wincdk&" \
                      "Product=viewcrt-windows&" \
                      "Description=View CRT Automation&" \
                      "HostOS=%s&" \
                      "ServerBuildID=%s&" \
                      "Branch=%s&" \
                      "BuildType=release&" \
                      "TestType=BATS" \
                      % (client_build_id, client_os, agent_build_id, client_build_branch)
            else:
                url = 'https://racetrack.eng.vmware.com/TestSetBegin.php?' + \
                      "BuildID=%s&" \
                      "User=wincdk&" \
                      "Product=viewcrt-windows&" \
                      "Description=View CRT Automation&" \
                      "HostOS=%s&" \
                      "Branch=%s&" \
                      "BuildType=release&" \
                      "TestType=BATS" \
                      % (client_build_id, client_os, client_build_branch)

            url = url.replace(" ", "%20")

            logger.info('create racetrack id url is : %s ' % url)
            ret = urllib2.urlopen(url)
            if ret.getcode() != http_response_ok:
                logger.info('racetrack return code: %s != 200' % ret.getcode())
                return

            racetrack_id = ret.read()
        except Exception, e:
            logger.info(e)

        finally:
            return racetrack_id

    @staticmethod
    def generate_testset_id(client_build_id, client_os, agent_build_id, client_build_branch):
        ret = RacetrackHelper.generate_testset_id_once(client_build_id,
                                                       client_os,
                                                       agent_build_id,
                                                       client_build_branch)
        if ret is None:
            ret = RacetrackHelper.generate_testset_id_once(client_build_id,
                                                           client_os,
                                                           agent_build_id,
                                                           client_build_branch)
        return ret


class STAFHelper(object):
    try:
        handle = STAFHandle("BATsHandler")
    except STAFException, e:
        logger.info("Error registering with STAF, RC: %d" % e.rc)
        sys.exit(e.rc)

    def __init__(self):
        pass

    @staticmethod
    def run_command_async(ip, cmd):
        request_async = 'START SHELL COMMAND %s' % wrapData(cmd)
        try:
            result = STAFHelper.handle.submit(ip, "PROCESS", request_async)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s" % (cmd, result.rc, result.result))
            return result
        except Exception, e:
            logger.info('Err on staf run command async : %s' % e)
            return -1

    @staticmethod
    def run_command_sync(ip, cmd):
        request = 'START SHELL COMMAND %s WAIT RETURNSTDOUT RETURNSTDERR' % cmd
        try:
            logger.info(ip + " " + request)
            result = STAFHelper.handle.submit(ip, "PROCESS", request)
            # logger.info(result.resultObj)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s" % (cmd, result.rc, result.result))
            return result.rc
        except Exception, e:
            logger.info('Err on staf ping: %s' % e)
            return -1

    @staticmethod
    def run_command_sync2(ip, cmd, dir):
        request = 'START COMMAND %s WORKDIR "%s" WAIT RETURNSTDOUT RETURNSTDERR' % (cmd, dir)
        try:
            logger.info(ip + " " + request)
            result = STAFHelper.handle.submit(ip, "PROCESS", request)
            logger.info(result.resultObj)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s" % (cmd, result.rc, result.result))
            return result.rc
        except Exception, e:
            logger.info('Err on staf ping: %s' % e)
            return -1

    @staticmethod
    def run_command_sync3(ip, cmd):
        request = 'START SHELL COMMAND %s WAIT RETURNSTDOUT RETURNSTDERR' % wrapData(cmd)
        try:
            logger.info(ip + " " + request)
            result = STAFHelper.handle.submit(ip, "PROCESS", request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s" % (cmd, result.rc, result.result))
            return result
        except Exception, e:
            logger.info('Err on staf ping: %s' % e)
            return None

    ''' Tricky method, just for reg query, force it run as 32bit. '''

    @staticmethod
    def run_command_sync4(ip, cmd):
        request = 'START SHELL COMMAND %s ENV \"PATH=C:\\Windows\\sysnative;{STAF/Env/PATH}\"  ' \
                  'RETURNSTDOUT STDERRTOSTDOUT WAIT' % wrapData(cmd)
        try:
            logger.info(ip + " " + request)
            result = STAFHelper.handle.submit(ip, "PROCESS", request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s" % (cmd, result.rc, result.result))
            return result
        except Exception, e:
            logger.info('Err on staf ping: %s' % e)
            return None

    @staticmethod
    def submit(ip, service, request):
        try:
            # logger.info(service + " " + request)
            result = STAFHelper.handle.submit(ip, service, request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s" % (request, result.rc, result.result))
            return result
        except Exception, e:
            logger.info('Err on staf request: %s' % e)
            return -1

    @staticmethod
    def copy_from_local_to_remote_temp(from_file, to_machine, retry=1):
        """
            It will copy the file to c:\\temp of the remote machine

            Will retry one more times if encounter any error.

        :param from_file:
        :param to_file:
        :param to_machine:
        :return: true or false
        """
        ret = False
        '''will upload the installer file to the temp folder. Only support windows here.'''
        to_file = os.path.join('C:/temp', os.path.basename(from_file))
        copy_request = 'COPY FILE ' + from_file + ' TOFILE ' + to_file + ' TOMACHINE ' + to_machine
        logger.info(copy_request)
        try:
            ''' force create the temp folder  '''
            STAFHelper.handle.submit(to_machine, "FS", 'create directory c:\\temp')
            time.sleep(5)
            result = STAFHelper.handle.submit('local', "FS", copy_request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s"
                            % (copy_request, result.rc, result.result))
                time.sleep(5)
                if retry != 2:
                    STAFHelper.copy_from_local_to_remote_temp(from_file, to_machine, 2)
                return
            time.sleep(10)
            ret = True
        except Exception, e:
            logger.info('Err on staf ping: %s' % e)
            time.sleep(5)
            if retry != 2:
                STAFHelper.copy_from_local_to_remote_temp(from_file, to_machine, 2)
        finally:
            return ret

    @staticmethod
    def copy_from_local_to_remote(from_file, to_file, to_machine, retry=1):
        """
            It will copy the file to the remote machine

        :param from_file:
        :param to_file:
        :param to_machine:
        :return: true or false
        """
        ret = False
        copy_request = 'COPY FILE ' + from_file + ' TOFILE ' + to_file + ' TOMACHINE ' + to_machine
        try:
            result = STAFHelper.handle.submit('local', "FS", copy_request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s"
                            % (copy_request, result.rc, result.result))
                ''' Will retry one more to ensure the file be copied successfully. '''
                time.sleep(5)
                if retry != 2:
                    STAFHelper.copy_from_local_to_remote(from_file, to_file, to_machine, 2)
                return
            time.sleep(5)
            ret = True
        except Exception, e:
            logger.info('Err on staf copy from local to remote : %s' % e)
            time.sleep(5)
            if retry != 2:
                ''' Will retry one more to ensure the file be copied successfully. '''
                STAFHelper.copy_from_local_to_remote(from_file, to_file, to_machine, 2)
        finally:
            return ret

    @staticmethod
    def copy_from_remote_to_remote(from_file, to_file, remote_machine):
        """
            It's just a function of copy on the remote machine.

        :param from_file:
        :param to_file:
        :param remote_machine:
        :return: true or false
        """
        ret = False
        copy_request = 'COPY FILE ' + from_file + ' TOFILE ' + to_file + ' TOMACHINE ' + remote_machine
        try:
            result = STAFHelper.handle.submit(remote_machine, "FS", copy_request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s"
                            % (copy_request, result.rc, result.result))
                return
            time.sleep(5)
            ret = True
        except Exception, e:
            logger.info('Err on staf copy to remote : %s' % e)
        finally:
            return ret

    @staticmethod
    def delete_file(machine, file_entry):
        ret = False
        delete_request = 'DELETE ENTRY ' + file_entry + ' file_entry'
        try:
            result = STAFHelper.handle.submit(machine, "FS", delete_request)
            if result.rc != 0:
                logger.info("Staf request fail, Request:%s RC: %d, Result: %s"
                            % (delete_request, result.rc, result.result))
                return
            ret = True
        except Exception, e:
            logger.info('Err on staf delete file: %s' % e)
        finally:
            return ret

    @staticmethod
    def fs_request(machine, fs_request):
        try:
            return STAFHelper.handle.submit(machine, "FS", fs_request)
        except Exception, e:
            logger.info('Err on staf FS: %s' % e)

    @staticmethod
    def staf_ping(ip):
        ret = False
        try:
            result = STAFHelper.handle.submit(ip, "ping", "ping")
            if result.rc != 0:
                # logger.info("Staf ping fail, RC: %d, Result: %s" % (result.rc, result.result))
                return
            if result.result != 'PONG':
                # logger.info("Staf ping fail, RC: %d, Result: %s" % (result.rc, result.result))
                return
            ret = True
        except Exception, e:
            logger.info('Err on staf ping: %s' % e)
        finally:
            return ret

    @staticmethod
    def staf_ping_timeout(ip, timeout=600, interval=20):
        ret = False
        elapsed_time = 0
        logger.info("STAF " + ip + " ping ping...")
        while elapsed_time < timeout:
            try:
                if STAFHelper.staf_ping(ip):
                    ret = True
                    break
            except:
                continue
            elapsed_time += interval
            time.sleep(interval)
        return ret

    @staticmethod
    def get_computer_name(ip):
        result = STAFHelper.submit(ip, 'var', 'resolve string {STAF/Env/COMPUTERNAME}')
        assert result.rc == 0, 'get computer name error.'
        return result.resultObj

    @staticmethod
    def get_machine_nickname(ip):
        result = STAFHelper.submit(ip, 'var', 'resolve string {STAF/Config/MachineNickname}')
        assert result.rc == 0, 'get machine nickname error.'
        return result.resultObj

    @staticmethod
    def get_os_name(ip):
        os_name = ''
        try:
            result = STAFHelper.run_command_sync3(ip, 'systeminfo | find \"OS Name\"')
            mc = unmarshall(result.result)
            entry_map = mc.getRootObject()
            os_name = entry_map['fileList'][0]['data'].split(':')[1].strip()
        except Exception, e:
            logger.info(e)
            os_name = None
        finally:
            return os_name

    @staticmethod
    def get_os_arch(ip):
        os_arch_return = ''
        try:
            result = STAFHelper.run_command_sync3(ip, 'systeminfo | find \"System Type\"')
            mc = unmarshall(result.result)
            entry_map = mc.getRootObject()
            os_arch = entry_map['fileList'][0]['data'].split(':')[1].strip()
            if os_arch.lower().find('x64') != -1:
                os_arch_return = '64'
            if os_arch.lower().find('x86') != -1:
                os_arch_return = '32'
        except Exception, e:
            logger.info(e)
            os_arch_return = ''
        finally:
            return os_arch_return


def install(bats_env_parameters):
    """
            To install client.agent.broker at the same time.

            Each thread will handle one installation request, any failure will stop the thread. But the main thread
            will continue to run until get all the results from all the threads.

            Do not handle the RDSH installation since it depends on the broker. For the RDSH installation, refer the
            config function.

    """
    agent_queue = Queue()
    broker_queue = Queue()
    client_queue = Queue()

    if not bats_env_parameters.skip_agent:
        agent_runner = AgentRunner(bats_env_parameters)
        # t1 = threading.Thread(target=agent_runner.install2, name="install agent",
        #                       args=[bats_env_parameters, agent_queue])
        t1 = Process(target=agent_runner.install, name="[Process] install agent",
                     args=[bats_env_parameters, agent_queue])

    if not bats_env_parameters.skip_client:
        if bats_env_parameters.is_client_vm:
            client_runner = ClientVMRunner(bats_env_parameters)
        else:
            client_runner = ClientRunner(bats_env_parameters)
        t2 = Process(target=client_runner.install, name="[Process] install client",
                     args=[bats_env_parameters, client_queue])

    if not bats_env_parameters.skip_broker:
        broker_runner = BrokerRunner()
        t3 = Process(target=broker_runner.install2, name="[Process] install broker",
                     args=[bats_env_parameters, broker_queue])

    if not bats_env_parameters.skip_agent:
        t1.start()
    if not bats_env_parameters.skip_client:
        t2.start()
    if not bats_env_parameters.skip_broker:
        t3.start()

    if not bats_env_parameters.skip_agent:
        t1.join()
        if not agent_queue.get():
            logger.info("agent install fail, then to terminate")
            sys.exit(-1)
    if not bats_env_parameters.skip_client:
        t2.join()
        if not client_queue.get():
            logger.info("client install fail, then to terminate")
            sys.exit(-1)
    if not bats_env_parameters.skip_broker:
        t3.join()
        if not broker_queue.get():
            logger.info("broker install fail, then to terminate")
            sys.exit(-1)


def config(bats_env_parameters):
    rdsh_queue = Queue()
    agent_config_queue = Queue()

    rdsh_runner = RDSHRunner(bats_env_parameters)
    agent_runner = AgentRunner(bats_env_parameters)

    if not bats_env_parameters.skip_rdsh:
        t4 = Process(target=rdsh_runner.install2, name="[Process] install and config RDSH",
                     args=[rdsh_queue])
    if not bats_env_parameters.skip_agent or bats_env_parameters.agent_config:
        t5 = Process(target=agent_runner.config, name="[Process] agent config",
                     args=[bats_env_parameters, agent_config_queue])

    if not bats_env_parameters.skip_rdsh:
        t4.start()
    if not bats_env_parameters.skip_agent or bats_env_parameters.agent_config:
        t5.start()

    if not bats_env_parameters.skip_rdsh:
        t4.join()
        if not rdsh_queue.get():
            logger.info("RDSH install fail, ignore")
    if not bats_env_parameters.skip_agent or bats_env_parameters.agent_config:
        t5.join()
        if not agent_config_queue.get():
            logger.info("agent config fail, then to terminate")
            sys.exit(-1)


def trigger_test_run(bats_env_parameters):
    if bats_env_parameters.is_client_vm:
        client_runner = ClientVMRunner(bats_env_parameters)
    else:
        client_runner = ClientRunner(bats_env_parameters)
    client_runner.run_tc()


def init_data():
    parameters = Parameters()
    bats_env_parameters = BATsEnvParameters(parameters)
    return bats_env_parameters


''' This function is just for dev refactor environment, no background will be upgraded. Only for client. '''


def for_refactor(bats_env_parameters):
    client_runner = ClientRunner(bats_env_parameters)
    client_runner.reinstall(bats_env_parameters)
    client_runner.run_tc()
    time.sleep(60)


def tear_down():
    """
        will do some tear down work. (Enhance later.)
        1, delete all the downloaded files.
        2, will send out a summary mail to tell the execution result.
        3, Release the STAF handler

    """
    STAFHelper.handle.unregister()
    pass


def main():
    try:
        bats_env_parameters = init_data()
        if bats_env_parameters.do_refactor:
            for_refactor(bats_env_parameters)
        else:
            install(bats_env_parameters)
            config(bats_env_parameters)
            if bats_env_parameters.run_tc:
                trigger_test_run(bats_env_parameters)
    finally:
        tear_down()


if __name__ == '__main__':
    main()
    pass
