'''
supported yaml with absl.flags.argparse_flags.ArgumentParser and argparse.ArgumentParser

# from absl.flags import argparse_flags
# parser = argparse_flags.ArgumentParser()

'''
import argparse
import builtins
import inspect
import os
import pathlib
from collections import OrderedDict
from pprint import pformat

from loguru import logger
from omegaconf import OmegaConf


class BibiFlags:
    names = [
        'dest',
        'type',
        'const',
        'default',
        'option_strings',
        'help',
        'required',
        'nargs',
        'choices',
        'metavar',
    ]

    def __init__(self,
                 flags_path: str = None,
                 argparser: argparse.ArgumentParser = None,
                 app_name: str = None,
                 root: str = None,
                 key: str = 'flags',
                 encoding: str = 'UTF8'):
        argparser_ = argparser if argparser is not None else argparse.ArgumentParser()
        app_name_ = app_name if app_name is not None else pathlib.Path(inspect.stack()[1][0].f_code.co_filename).stem
        self.app_name = app_name_
        if root is None:
            root = pathlib.Path('.')
        if flags_path is None:
            app_flags_path = pathlib.Path(root).joinpath(f'{self.app_name}.yaml')
        else:
            app_flags_path = pathlib.Path(root).joinpath(flags_path)
        if app_flags_path.exists():
            argparser_ = self.from_yaml(str(app_flags_path), argparser_, encoding=encoding, key=key)
        else:
            self.to_yaml(argparser_, app_flags_path, encoding=encoding, key=key)
        self.argparser_ = argparser_
        self.argparser_.parse_args()
        logger.info(f'app_name:{app_name_}, key:{key}, parameters: {self.parameters}')

    @property
    def parameters(self):
        return vars(self.argparser_.parse_args())

    @property
    def argparser(self):
        return self.argparser_

    @staticmethod
    def to_yaml(argparser: argparse.ArgumentParser,
                yaml_file,
                encoding: str = 'utf-8',
                key='ArgumentParser'):
        flags = []
        for action in argparser._actions:
            flag = OrderedDict()
            suppressed = False
            for name in BibiFlags.names:
                val = getattr(action, name)
                if val == '==SUPPRESS==':
                    suppressed = True
                if name == 'type':
                    if val is None:
                        flag[name] = 'bool'  # default bool
                    else:
                        flag[name] = val.__name__
                elif val is not None:
                    flag[name] = val
            if len(flag) > 0 and not suppressed:
                flags.append(flag)
        config = dict()
        config[key] = flags
        with open(yaml_file, 'w', encoding=encoding) as fp:
            OmegaConf.save(config=config, f=fp)

    @staticmethod
    def contains_yaml(yaml_file: str, encoding='utf-8', key='ArgumentParser'):
        with open(yaml_file, 'r', encoding=encoding) as fp:
            config = OmegaConf.load(fp)
            return key in config

    @staticmethod
    def from_yaml(yaml_file: str, parser=None, encoding='utf-8', key='ArgumentParser') -> argparse.ArgumentParser:
        with open(yaml_file, 'r', encoding=encoding) as fp:
            config = OmegaConf.load(fp)
            config = OmegaConf.to_object(config)
            logger.info(pformat(config))
            items = config.get(key, [])
            if len(items) == 0:
                logger.warning(f"Flags {key} NOT in {os.path.abspath(yaml_file)}")
            parser = argparse.ArgumentParser() if parser is None else parser
            for item in items:
                if item.get('type', 'str') == 'bool':
                    item['type'] = None
                else:
                    item['type'] = getattr(builtins, item.get('type', 'str'))
                action = argparse.Action(**item)
                if action.dest not in [_action.dest for _action in parser._actions]:
                    parser._add_action(action)
                else:
                    logger.warning(f"CONFLICT ARGS '{action.dest}', NOT USED {os.path.abspath(yaml_file)}")
            return parser

# if __name__ == '__main__':
#     flags = BibiFlags('flags_template.yaml')
#     print(flags.parameters)
