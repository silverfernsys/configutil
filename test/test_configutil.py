#! /usr/bin/env python
import os
import sys
from tempfile import NamedTemporaryFile
import unittest

try:
    import mock
except:
    from unittest import mock

try:
    from cStringIO import StringIO
except:
    from io import StringIO

try:
    from ConfigParser import SafeConfigParser
except:
    from configparser import SafeConfigParser

from contextlib import contextmanager

try:
    from configutil import Config
except:
    from configutil.configutil import Config


@contextmanager
def capture(command, *args, **kwargs):
    out, sys.stdout = sys.stdout, StringIO()
    err, sys.stderr = sys.stderr, StringIO()
    try:
        command(*args, **kwargs)
        sys.stdout.seek(0)
        sys.stderr.seek(0)
        yield (sys.stdout.read().strip(), sys.stderr.read().strip())
    finally:
        sys.stdout = out
        sys.stderr = err


class TestConfigutil(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_path = NamedTemporaryFile().name

        parser = SafeConfigParser()
        parser.add_section('section0')
        parser.set('section0', 'arg0a', '1234.123')
        parser.set('section0', 'arg0b', 'True')
        parser.set('section0', 'arg0c', 'False')
        parser.add_section('section1')
        parser.set('section1', 'arg1a', 'configstring1a')
        parser.set('section1', 'arg1b', 'configstring1b')
        parser.set('section1', 'arg1c', '1000')

        with open(cls.config_path, 'w') as file:
            parser.write(file)

        cls.missing_path = NamedTemporaryFile().name

        parser = SafeConfigParser()
        parser.add_section('section0')
        parser.set('section0', 'arg0a', '1234.123')
        parser.add_section('section1')
        parser.set('section1', 'arg1c', '1000')

        with open(cls.missing_path, 'w') as file:
            parser.write(file)

    def setup_config(self, path):
        config = Config()
        config.add_path(path)
        section = config.add_section('section0')
        section.add_argument('arg0a', 'a float', float)
        section.add_argument('arg0b', 'a boolean', bool)
        section.add_argument('arg0c', 'a boolean', bool)

        section = config.add_section('section1')
        section.add_argument('arg1a', 'a string', str)
        section.add_argument('arg1b', 'a string', str)
        section.add_argument('arg1c', 'an int', int)

        return config

    def test_config(self):
        sys.argv = [sys.argv[0]]
        config = self.setup_config(self.config_path)
        args = config.parse()
        self.assertEqual(args, config.arguments)
        self.assertEqual(args.section0.arg0a, 1234.123)
        self.assertEqual(args.section0.arg0b, True)
        self.assertEqual(args.section0.arg0c, False)
        self.assertEqual(args.section1.arg1a, 'configstring1a')
        self.assertEqual(args.section1.arg1b, 'configstring1b')
        self.assertEqual(args.section1.arg1c, 1000)
        self.assertEqual(args.command, None)

    def test_config_with_argv(self):
        sys.argv = [sys.argv[0]]
        sys.argv.extend(['--arg0b', 'false', '--arg1b', 'argstring1b',
            '--arg1c', '2000'])
        config = self.setup_config(self.config_path)
        args = config.parse()
        self.assertEqual(args, config.arguments)
        self.assertEqual(args.section0.arg0a, 1234.123)
        self.assertEqual(args.section0.arg0b, False)
        self.assertEqual(args.section0.arg0c, False)
        self.assertEqual(args.section1.arg1a, 'configstring1a')
        self.assertEqual(args.section1.arg1b, 'argstring1b')
        self.assertEqual(args.section1.arg1c, 2000)
        self.assertEqual(args.command, None)

    def test_config_with_commands(self):
        sys.argv = [sys.argv[0]]
        sys.argv.extend((['command1', '--arg0a', '1.1',
            '--arg1a', 'argstring1a']))
        config = self.setup_config(self.config_path)
        config.add_command('command0', 'command0 help')
        config.add_command('command1', 'command1 help')
        config.add_command('command2', 'command2 help')
        args = config.parse()
        self.assertEqual(args, config.arguments)
        self.assertEqual(args.section0.arg0a, 1.1)
        self.assertEqual(args.section0.arg0b, True)
        self.assertEqual(args.section0.arg0c, False)
        self.assertEqual(args.section1.arg1a, 'argstring1a')
        self.assertEqual(args.section1.arg1b, 'configstring1b')
        self.assertEqual(args.section1.arg1c, 1000)
        self.assertTrue(args.command, 'command1')

    def test_config_with_multiple_commands(self):
        sys.argv = [sys.argv[0]]
        sys.argv.extend((['command1', 'command0', '--arg0a', '1.1',
            '--arg1a', 'argstring1a']))
        config = self.setup_config(self.config_path)
        config.add_command('command0', 'command0 help')
        config.add_command('command1', 'command1 help')
        expected_output = 'usage: {cmd} [-h]  ...\n' \
            '{cmd}: error: unrecognized arguments: command0'.format(cmd=sys.argv[0])
        with self.assertRaises(SystemExit) as cm:
            with capture(config.parse) as (out, err):
                self.assertEqual(expected_output, err)
        self.assertEqual(cm.exception.code, 2)

    
    @mock.patch('configutil.configutil.getenv')
    def test_config_with_envs(self, mock_env):
        sys.argv = [sys.argv[0]]
        envs = {'arg0b': 'True', 'arg0c': 'False',
            'arg1a': 'argstring1a', 'arg1b': 'argstring1b'}
        mock_env.side_effect = lambda k: envs.get(k, None)

        config = self.setup_config(self.missing_path)
        args = config.parse()

        self.assertEqual(mock_env.call_count, 4)
        self.assertEqual(args, config.arguments)
        self.assertEqual(args.section0.arg0a, 1234.123)
        self.assertEqual(args.section0.arg0b, True)
        self.assertEqual(args.section0.arg0c, False)
        self.assertEqual(args.section1.arg1a, 'argstring1a')
        self.assertEqual(args.section1.arg1b, 'argstring1b')
        self.assertEqual(args.section1.arg1c, 1000)
        self.assertEqual(args.command, None)

    @mock.patch('configutil.configutil.getenv')
    def test_config_with_command_envs(self, mock_env):
        sys.argv = [sys.argv[0]]
        sys.argv.extend((['command0', '--arg0a', '1.1',
            '--arg1a', 'argstring1a']))
        envs = {'arg0b': 'True', 'arg0c': 'False',
            'arg1a': 'envstring1a', 'arg1b': 'envstring1b'}
        mock_env.side_effect = lambda k: envs.get(k, None)

        config = self.setup_config(self.missing_path)
        config.add_command('command0', 'command0 help')
        config.add_command('command1', 'command1 help')
        config.add_command('command2', 'command2 help')

        args = config.parse()

        self.assertEqual(mock_env.call_count, 3)
        self.assertEqual(args, config.arguments)
        self.assertEqual(args.section0.arg0a, 1.1)
        self.assertEqual(args.section0.arg0b, True)
        self.assertEqual(args.section0.arg0c, False)
        self.assertEqual(args.section1.arg1a, 'argstring1a')
        self.assertEqual(args.section1.arg1b, 'envstring1b')
        self.assertEqual(args.section1.arg1c, 1000)
        self.assertEqual(args.command, 'command0')
    
    def test_config_help(self):
        sys.argv = [sys.argv[0]]
        sys.argv.extend((['--help']))

        config = self.setup_config(self.config_path)
        config.add_command('command0', 'command0 help')
        config.add_command('command1', 'command1 help')
        config.add_command('command2', 'command2 help')

        expected_output = 'usage: {cmd} [-h]  ...\n' \
        '\n' \
        'optional arguments:\n' \
        '  -h, --help  show this help message and exit\n' \
        '\n' \
        'available commands:\n' \
        '              command help\n' \
        'command0  command0 help\n' \
        'command1  command1 help\n' \
        'command2  command2 help\n'.format(cmd=sys.argv[0])

        with self.assertRaises(SystemExit) as cm:
            with capture(config.parse) as (out, err):
                self.assertEqual(expected_output, err)
        self.assertEqual(cm.exception.code, 0)

    def test_command_help(self):
        sys.argv = [sys.argv[0]]
        sys.argv.extend((['command1', '--help']))

        config = self.setup_config(self.config_path)
        config.add_command('command0', 'command0 help')
        config.add_command('command1', 'command1 help')
        config.add_command('command2', 'command2 help')

        expected_output = 'usage: {cmd} command1 [-h] [--config CONFIG] [--arg1a ARG1A]\n' \
        '                            [--arg1b ARG1B] [--arg1c ARG1C] [--arg0a ARG0A]\n' \
        '                            [--arg0b ARG0B] [--arg0c ARG0C]\n' \
        '\n' \
        'optional arguments:\n' \
        '  -h, --help       show this help message and exit\n' \
        '  --config CONFIG  configuration file path\n' \
        '  --arg1a ARG1A    a string\n' \
        '  --arg1b ARG1B    a string\n' \
        '  --arg1c ARG1C    an int\n' \
        '  --arg0a ARG0A    a float\n' \
        '  --arg0b ARG0B    a boolean\n' \
        '  --arg0c ARG0C    a boolean\n'.format(cmd=sys.argv[0])

        with self.assertRaises(SystemExit) as cm:
            with capture(config.parse) as (out, err):
                self.assertEqual(expected_output, err)
        self.assertEqual(cm.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
