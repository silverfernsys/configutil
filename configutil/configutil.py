from argparse import ArgumentParser, ArgumentError
from os import getenv

try:
    from ConfigParser import SafeConfigParser, NoOptionError, NoSectionError
except:
    from configparser import SafeConfigParser, NoOptionError, NoSectionError


class ConfigError(Exception):
    def __init__(self, arg):
        self.message = 'Missing configuration argument "{0}".'.format(arg)
        self.arg = arg


class MissingSection(ConfigError):
    def __init__(self, arg):
        self.message = 'Missing section "{0}" in configuration.'.format(arg)
        self.arg = arg


class SectionError(ConfigError):
    def __init__(self, arg):
        self.arg = arg
        self.message = 'Section "{0}" does not exist in configuration.'.format(arg)


class ConfigArgumentError(ConfigError):
    def __init__(self, arg):
        self.arg
        self.message = ''


class ConfigArgument(object):
    def __init__(self, name, help, type, choices):
        self.name = name
        self.help = help
        self.type = type
        self.choices = choices

    def __repr__(self):
        return '<ConfigArgument(name={self.name}, help={self.help}, ' \
            'type={self.type}, choices={self.choices})>'.format(self=self)


class ConfigSection(object):
    def __init__(self, name, required=True):
        self.name = name
        self.required = required
        self.arguments = []

    def add_argument(self, name, help, type=str, choices=None):
        self.arguments.append(ConfigArgument(name, help, type, choices))

    def __repr__(self):
        return '<ConfigSection(name={self.name}, required={self.required}, ' \
            'arguments={self.arguments})>'.format(self=self)


class Config(object):
    def __init__(self):
        self.config_paths = []
        self.sections = {}
        self.arg_parser = ArgumentParser()
        self.config_parser = SafeConfigParser(allow_no_value=True)
        self.command_parser = None
        self.arguments = None

    def add_path(self, path):
        self.config_paths.append(path)

    def add_paths(self, paths):
        self.config_paths.extend(paths)

    def add_section(self, name, required=True):
        section = ConfigSection(name, required)
        self.sections[name] = section
        return section

    def get_section(self, name):
        try:
            return self.sections[name]
        except KeyError:
            raise SectionError(name)

    def add_command(self, name, help):
        if self.command_parser is None:
            self.command_parser = self.arg_parser.add_subparsers(
                title='available commands', help='command help',
                dest='command', metavar='')
        self.command_parser.add_parser(name=name, help=help)

    def parse(self):
        # Select appropriate parser to add arguments to
        if self.command_parser:
            for parser in self.command_parser.choices.values():
                parser.add_argument('--config', help='configuration file path')
                for section in self.sections.values():
                    for arg in section.arguments:
                        parser.add_argument('--' + arg.name,
                            help=arg.help, choices=arg.choices)
        else:
            self.arg_parser.add_argument('--config', help='configuration file path')
            for section in self.sections.values():
                for arg in section.arguments:
                    self.arg_parser.add_argument('--' + arg.name,
                        help=arg.help, choices=arg.choices)

        args = self.arg_parser.parse_args()

        if args.config is None and len(self.config_paths) == 0:
            raise AttributeError('Missing path to configuration file.')

        if args.config:
            self.config_parser.read(args.config)
        else:
            self.config_parser.read(self.config_paths)

        try:
            data = {k : self._section_args(args, self.config_parser, v)
                for (k, v) in self.sections.items()}
        except NoOptionError as e:
            raise ConfigError(e.args)
        except NoSectionError as e:
            raise MissingSection(e.section)

        if self.command_parser:
            data['command'] = args.command
        else:
            data['command'] = None

        class Arguments(object):
            def __init__(self, data):
                self.__dict__ = data

        self.arguments = Arguments(data)
        return self.arguments

    def _section_args(self, args, config, section):
        data = {arg.name: self._eval(getattr(args, arg.name, None) or
            self._get_arg(config, section.name, arg.name), arg.type)
            for arg in section.arguments}

        class Section(object):
            def __init__(self, data):
                self.__dict__ = data

        return Section(data)

    def _get_arg(self, config, section_name, arg_name):
        try:
            return config.get(section_name, arg_name)
        except NoOptionError as e:
            env_val = getenv(arg_name)
            if env_val:
                return env_val
            else:
                raise ConfigError(e.args)

    def _eval(self, arg, arg_type):
        if arg_type == bool:
            return eval(arg.capitalize())
        else:
            return arg_type(arg)

    def __repr__(self):
        items = self.__dict__.iteritems()
        vals = ', '.join('%s=%r' % (k, v) for (k, v) in items)
        return '<{0}({1}>'.format(self.__class__.__name__, vals)
