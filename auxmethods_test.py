#!/usr/bin/env python
# Copyright (c) 2011 Jan Kaliszewski (zuo). All rights reserved.
# Licensed under the MIT License. Python 2.5+/3.x-compatibile.

from __future__ import with_statement  # (Py2.5 needs this)

import sys
import time
import unittest

from auxmethods import *


#
# helper class and its instance

class _OutputForTests(list):

    def __call__(self, *args):
        arg_list = list(args)
        self.append(arg_list)
        return arg_list

    def check(self, test_case, *expected_tbuf_content):
        test_case.assertEqual(self, list(expected_tbuf_content))
        del self[:]

ot = _OutputForTests()


#
# actual classes and data for tests

class WithNoAuxMethods(object):
    @primary
    def spam(self, arg):
        return 'WithNoAuxMethods.spam: %r' % arg
WithNoAuxMethods = aux(WithNoAuxMethods)


class A(object):
    @primary
    def foo(self, arg):
        return ot('A.foo', arg, self.__foo(arg))
    def foo_before(self, arg):
        return ot('A.foo_before', arg, self.__foo_before(arg))
    def foo_after(self, arg):
        return ot('A.foo_after', arg, self.__foo_after(arg))
    def foo_around(self, arg):
        return ot('A.foo_around (begin)', arg) and ot(
            'A.foo_around (end)', arg, self.__foo_around(arg))
    @primary
    def _bar(self, arg):
        return ot('A._bar', arg, self.___bar(arg))
    def _bar_before(self, arg):
        return ot('A._bar_before', arg, self.___bar_before(arg))
    def _bar_after(self, arg):
        return ot('A._bar_after', arg, self.___bar_after(arg))
    def _bar_around(self, arg):
        return ot('A._bar_around (begin)', arg) and ot(
            'A._bar_around (end)', arg, self.___bar_around(arg))
A = aux(A)

class _A_(A):
    @primary
    def foo(self, arg):
        return ot('_A_.foo', arg, self.__foo(arg))
    def foo_before(self, arg):
        return ot('_A_.foo_before', arg, self.__foo_before(arg))
    def foo_after(self, arg):
        return ot('_A_.foo_after', arg, self.__foo_after(arg))
    def foo_around(self, arg):
        return ot('_A_.foo_around (begin)', arg) and ot(
            '_A_.foo_around (end)', arg, self.__foo_around(arg))
    @primary
    def _bar(self, arg):
        return ot('_A_._bar', arg, self.___bar(arg))
    def _bar_before(self, arg):
        return ot('_A_._bar_before', arg, self.___bar_before(arg))
    def _bar_after(self, arg):
        return ot('_A_._bar_after', arg, self.___bar_after(arg))
    def _bar_around(self, arg):
        return ot('_A_._bar_around (begin)', arg) and ot(
            '_A_._bar_around (end)', arg, self.___bar_around(arg))
_A_ = aux(_A_)

AB_TEST_PATTERN = """
a.%(basename)s_primary('%(arg)s'); ot.check(self,
    ['A.%(basename)s', '%(arg)s', None])
a.%(basename)s_before('%(arg)s'); ot.check(self,
    ['A.%(basename)s_before', '%(arg)s', None])
a.%(basename)s_after('%(arg)s'); ot.check(self,
    ['A.%(basename)s_after', '%(arg)s', None])
a.%(basename)s_around('%(arg)s'); ot.check(self,
    ['A.%(basename)s_around (begin)', '%(arg)s'],
    ['A.%(basename)s_before', '%(arg)s', None],
    ['A.%(basename)s', '%(arg)s', None],
    ['A.%(basename)s_after', '%(arg)s', None],
    ['A.%(basename)s_around (end)', '%(arg)s',
        ['A.%(basename)s', '%(arg)s', None]])

a.%(basename)s('%(arg)s'); ot.check(self,
    ['A.%(basename)s_around (begin)', '%(arg)s'],
    ['A.%(basename)s_before', '%(arg)s', None],
    ['A.%(basename)s', '%(arg)s', None],
    ['A.%(basename)s_after', '%(arg)s', None],
    ['A.%(basename)s_around (end)', '%(arg)s',
        ['A.%(basename)s', '%(arg)s', None]])

_a_.%(basename)s('%(arg)s'); ot.check(self,
    ['_A_.%(basename)s_around (begin)', '%(arg)s'],
    ['A.%(basename)s_around (begin)', '%(arg)s'],
    ['A.%(basename)s_before', '%(arg)s', None],
    ['_A_.%(basename)s_before', '%(arg)s',
        ['A.%(basename)s_before', '%(arg)s', None]],
    ['A.%(basename)s', '%(arg)s', None],
    ['_A_.%(basename)s', '%(arg)s',
        ['A.%(basename)s', '%(arg)s', None]],
    ['A.%(basename)s_after', '%(arg)s', None],
    ['_A_.%(basename)s_after', '%(arg)s',
        ['A.%(basename)s_after', '%(arg)s', None]],
    ['A.%(basename)s_around (end)', '%(arg)s',
        ['_A_.%(basename)s', '%(arg)s',
            ['A.%(basename)s', '%(arg)s', None]]],
    ['_A_.%(basename)s_around (end)', '%(arg)s',
        ['A.%(basename)s_around (end)', '%(arg)s',
            ['_A_.%(basename)s', '%(arg)s',
                ['A.%(basename)s', '%(arg)s', None]]]])
"""


class TimedAction(AutoAuxBase):

    def action_before(self, *args, **kwargs):
        """Start action timer."""
        ot('TimedAction.action_before', args, kwargs,
           self.__action_before(*args, **kwargs))
        self.start_time = time.time()

    def action_after(self, *args, **kwargs):
        """Stop action timer and report measured duration."""
        self.action_duration = time.time() - self.start_time
        ot('TimedAction.action_after', args, kwargs,
           self.__action_after(*args, **kwargs))


class FileContentAction(AutoAuxBase):

    def action_around(self, path):
        """Read file and pass its content on; report success or error."""
        ot('FileContentAction.action_around (begin)', path)
        try:
            with open(path) as f:
                content = f.read()
        except EnvironmentError:
            result = content = None
        else:
            result = self.__action_around(path, content)
        ot('FileContentAction.action_around (end)', content, result)
        return result


class NewlinesCounter(FileContentAction, TimedAction):

    item_descr = 'newlines'

    @primary
    def action(self, path, content):
        """Get number of newlines in a given string."""
        result = content.count('\n')
        ot('NewlinesCounter.action', path, content, result,
           self.__action(path, content))
        return result

    def action_before(self, path, *args):
        ot('NewlinesCounter.action_before', path, args)
        self.__action_before(path, *args)

    def action_around(self, path):
        """Start operation with given file path. Finally, show summary."""
        ot('NewlinesCounter.action_around (begin)', path)
        result = self.__action_around(path)
        ot('NewlinesCounter.action_around (end)', result)
        if result is not None:
            return '%s in file %r: %s (counted in %fs)\n' % (
                self.item_descr, path, result, self.action_duration)
        else:
            return 'could not count %s in file %r\n' % (self.item_descr, path)


class SpacesAndNewlinesCounter(NewlinesCounter):

    item_descr = 'spaces and newlines'

    @primary
    def action(self, path, content):
        """Get number of spaces and newlines in a given string."""
        ot('SpacesAndNewlinesCounter.action (begin)', path, content)
        spaces = content.count(' ')
        newlines = self.__action(path, content)
        result = spaces + newlines
        ot('SpacesAndNewlinesCounter.action (end)', newlines, result)
        return result

    def action_after(self, path, *args):
        self.__action_after(path, *args)
        ot('SpacesAndNewlinesCounter.action_after', path, args)


#
# test cases

class TestSimple(unittest.TestCase):

    def setUp(self):
        del ot[:]

    def test_with_no_aux_methods(self):
        self.assertTrue(hasattr(WithNoAuxMethods, '_WithNoAuxMethods__spam'))
        self.assertTrue(hasattr(WithNoAuxMethods, 'spam_primary'))
        wnam = WithNoAuxMethods()
        self.assertEqual(
            wnam.spam('spammish inquisition'),
            "WithNoAuxMethods.spam: 'spammish inquisition'")

    def test_a_and_a(self):
        self.assertTrue(hasattr(A, 'foo_primary'))
        self.assertTrue(hasattr(A, '_bar_primary'))
        self.assertTrue(hasattr(_A_, 'foo_primary'))
        self.assertTrue(hasattr(_A_, '_bar_primary'))
        a = A()
        _a_ = _A_()
        exec(AB_TEST_PATTERN % dict(basename='foo', arg='spam'))
        exec(AB_TEST_PATTERN % dict(basename='_bar', arg='nee'))


class TestMoreRealistic(unittest.TestCase):

    def setUp(self):
        del ot[:]
        with open(__file__) as f:
            self.content = f.read()
        self.nl_num = self.content.count('\n')
        self.spc_nl_num = self.content.count(' ') + self.nl_num
        self.non_existent = 'spam/spam/spam/non-existent-file'

    def test_nl_counter(self):
        self.assertTrue(hasattr(NewlinesCounter, 'action_primary'))
        nl_counter = NewlinesCounter()

        self.assertEqual(
            nl_counter.action(self.non_existent),
            'could not count newlines in file %r\n' % self.non_existent)
        self.assertFalse(hasattr(nl_counter, 'start_time'))
        self.assertFalse(hasattr(nl_counter, 'action_duration'))
        ot.check(self,
            ['NewlinesCounter.action_around (begin)', self.non_existent],
            ['FileContentAction.action_around (begin)', self.non_existent],
            ['FileContentAction.action_around (end)', None, None],
            ['NewlinesCounter.action_around (end)', None])

        self.assertEqual(
            nl_counter.action(__file__),
            'newlines in file %r: %s (counted in %fs)\n' % (
                __file__, self.nl_num, nl_counter.action_duration))
        self.assertTrue(hasattr(nl_counter, 'start_time'))
        self.assertTrue(hasattr(nl_counter, 'action_duration'))
        ot.check(self,
            ['NewlinesCounter.action_around (begin)',
             __file__],
            ['FileContentAction.action_around (begin)',
             __file__],
            ['NewlinesCounter.action_before',
             __file__, (self.content,)],
            ['TimedAction.action_before',
             (__file__, self.content), {}, None],
            ['NewlinesCounter.action',
             __file__, self.content, self.nl_num, None],
            ['TimedAction.action_after',
             (__file__, self.content), {}, None],
            ['FileContentAction.action_around (end)',
             self.content, self.nl_num],
            ['NewlinesCounter.action_around (end)',
             self.nl_num])

    def test_scp_nl_counter(self):
        self.assertTrue(hasattr(SpacesAndNewlinesCounter, 'action_primary'))
        spc_nl_counter = SpacesAndNewlinesCounter()

        self.assertEqual(
            spc_nl_counter.action(self.non_existent),
            'could not count spaces and newlines in file %r\n' %
                self.non_existent)
        self.assertFalse(hasattr(spc_nl_counter, 'start_time'))
        self.assertFalse(hasattr(spc_nl_counter, 'action_duration'))
        ot.check(self,
            ['NewlinesCounter.action_around (begin)', self.non_existent],
            ['FileContentAction.action_around (begin)', self.non_existent],
            ['FileContentAction.action_around (end)', None, None],
            ['NewlinesCounter.action_around (end)', None])

        self.assertEqual(
            spc_nl_counter.action(__file__),
            'spaces and newlines in file %r: %s (counted in %fs)\n' % (
                __file__, self.spc_nl_num, spc_nl_counter.action_duration))
        ot.check(self,
            ['NewlinesCounter.action_around (begin)',
             __file__],
            ['FileContentAction.action_around (begin)',
             __file__],
            ['NewlinesCounter.action_before',
             __file__, (self.content,)],
            ['TimedAction.action_before',
             (__file__, self.content), {}, None],
            ['SpacesAndNewlinesCounter.action (begin)',
             __file__, self.content],
            ['NewlinesCounter.action',
             __file__, self.content, self.nl_num, None],
            ['SpacesAndNewlinesCounter.action (end)',
             self.nl_num, self.spc_nl_num],
            ['TimedAction.action_after',
             (__file__, self.content), {}, None],
            ['SpacesAndNewlinesCounter.action_after',
             __file__, (self.content,)],
            ['FileContentAction.action_around (end)',
             self.content, self.spc_nl_num],
            ['NewlinesCounter.action_around (end)',
             self.spc_nl_num])


if __name__ == '__main__':
    unittest.main()
