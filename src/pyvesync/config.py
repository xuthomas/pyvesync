"""Configure devices based on API response."""
import logging
import json
import enum
from typing import Dict, List, Optional, Union
from pyvesync.helpers import Helpers as help


_LOGGER = logging.getLogger(__name__)


class ACTIONS(enum.Enum):
    """Define action ID's defined by linkage properties."""
    TOGGLE_POWER = 60000
    PRIMARY_LEVEL_TEXT = 70002
    PRIMARY_LEVEL_NUM = 70004
    MODES = 70001
    SECONDARY_TOGGLE = 70003
    SECONDARY_LEVELS = 70005
    LEVELS_TEXT = 70008


class VeSyncConfig:
    def __init__(self, manager) -> None:
        self.manager = manager
        self.config_modules = []
        for dev_list in manager._dev_list.values():
            for dev in dev_list:
                self.config_modules.append(dev.config_module)
        self.config = {}
        self.specs = {}

    def get_linkage(self):
        """Get VeSync Device properties."""
        headers = help.req_header_bypass()
        url = '/cloud/v1/app/linkage/getSupportedLinkageProperties'
        body = help.bypass_body_v2()
        body['method'] = 'getSupportedLinkageProperties'
        response, _ = help.call_api(url, 'post', headers=headers, json=body)
        if not isinstance(response, dict) or response.get('code') != 0:
            _LOGGER.debug('Failed to get supported linkage properties')
        return self.process_linkage(response)

    def process_linkage(self, response: dict):
        """Process supported linkage properties."""
        dev_list = response.get('result', {}).get('devicePropertiesList')
        if not isinstance(dev_list, list) or len(dev_list) == 0:
            _LOGGER.debug('No supported linkage properties found')
            return None
        for dev in dev_list:
            if dev.get('configModule', '').lower() not in map(str.lower, self.config_modules):
                continue
            self.config[dev.get('configModule')] = {}
            for prop in dev.get('actionPropertyList', []):
                self.config[dev.get('configModule')][prop.get('actionId')] = prop.get('actionProps')
        return True

    def get_specs(self) -> bool:
        """Get device specifications."""
        headers = help.req_header_bypass()
        url = '/cloud/v1/app/getAppConfigurationV2'
        body = help.bypass_body_v2(self.manager)
        body['method'] = 'getAppConfigurationV2'
        body['token'] = ''
        body['accountID'] = ''
        body['userCountryCode'] = ''
        body['categories'] = [{
            "category": "SupportedModelsV3",
            "testMode": False,
            "version": ""
        }]
        response, _ = help.call_api(url, 'post', headers=headers, json_object=body)
        if not isinstance(response, dict) or response.get('code') != 0:
            _LOGGER.debug('Failed to get device config')
            return False
        return self.process_specs(response)

    def process_specs(self, response: dict) -> bool:
        """Process device specifications from the API."""
        specs = response.get('result', {}).get('configList', [{}])[0].get('items', [])
        if len(specs) == 0 or not isinstance(specs[0], dict):
            _LOGGER.debug('No device specifications found')
            return False
        item_value = specs[0].get('itemValue', '')
        try:
            item_json = json.loads(item_value)
        except json.JSONDecodeError:
            _LOGGER.debug('Failed to parse device specifications')
            return False
        prod_line_list = item_json.get('productLineList')
        if not isinstance(prod_line_list, list):
            _LOGGER.debug('No device specifications found')
            return False
        for prod_line in prod_line_list:
            type_list = prod_line.get('typeInfoList')
            if not isinstance(type_list, list):
                continue
            for prod_type in type_list:
                current_type = prod_type['typeName'].lower()
                for model in prod_type['modelInfoList']:
                    current_model = model['model'].lower()
                    config_mod_list = model.get('configModuleInfoList')
                    if not isinstance(config_mod_list, list):
                        continue
                    for config_mod in config_mod_list:
                        if config_mod.get('configModule', '').lower() in map(str.lower, self.config_modules):
                            self.specs[config_mod['configModule']] = {
                                'type': current_type,
                                'model': current_model,
                                'model_name': model['modelName'],
                                'model_display': model['modelDisplay'],
                            }
        return True


