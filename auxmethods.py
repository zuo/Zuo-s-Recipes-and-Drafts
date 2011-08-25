#!/usr/bin/env python
#
# Copyright (c) 2011 Jan Kaliszewski (zuo). All rights reserved.
# Licensed under the MIT License.
#
# Python 2.5+/3.x-compatibile.
#
# The newest version of this module should be downloadable from:
# https://github.com/zuo/Zuo-s-Recipes-and-Drafts/blob/master/auxmethods.py

"""
CLOS-like `around`/`before`/`after` auxiliary methods
=====================================================

This module provides an easy way to define and use your own `around`/`before`
/`after` auxiliary methods, similar to those used in CLOS (Common Lisp Object
System).

Implementing the module I used a few native Python features:

* class and function decorators,
* class inheritance plus `super()` built-in function,
* private name mangling (to free users from necessity of redundant class name
  retyping).

How to use it
-------------

Decorate your classes using `aux()` class decorator and do the same with
chosen method using `primary()` function decorator:

    from auxmethods import aux, primary

    @aux
    class Parent(object):

        @primary
        def my_method(self, s):
            print('\nParent/primary %r\n' % s)
            return '\nmy_method() was called with argument %r\n' % s

        def my_method_around(self, s):
            # `around' aux method (aux methods don't need to be decorated)
            print('Parent/around-aux: %r' % s)
            # equivalent to CLOS's call-next-method:
            result = self.__my_method_around(s)
            print('Parent/around-aux exits')
            return result

    @aux
    class Child(Parent):

        def my_method_around(self, s):
            print('Child/around-aux: %r' % s)
            # equivalent of CLOS's call-next-method:
            result = self.__my_method_around(s)
            print('Child/around-aux exits')
            return result

        def my_method_before(self, s):
            print('Child/before-aux: %r' % s)

        def my_method_after(self, s):
            print('Child/after-aux: %r' % s)

Now, if you execute this:

    obj = Child()
    print(obj.my_method('spam'))

...the following text will be printed:

    Child/around-aux: 'spam'
    Parent/around-aux: 'spam'
    Child/before-aux: 'spam'

    Parent/primary 'spam'

    Child/after-aux: 'spam'
    Parent/around-aux exits
    Child/around-aux exits

    my_method() was called with argument 'spam'

In the source, below the "if __name__ == '__main__'" condition, you'll find
a bit more interesting example.

A few remarks
-------------

* Auxiliary (aux) method names are built on their primary method name --
  with an appropriate suffix added: `_around`, `_before` or `_after`. For
  example, if your primary method name is `spam`, your aux method names
  will be: `spam_around`, `spam_before`, `spam_after`.

* All auxiliary (`*_around`, `*_before`, `*_after`) methods are optional: you
  don't need to define all of them. If you define any, at least one primary
  method (decorated with the `primary()` decorator) with the appropriate
  name should be defined somewhere in your class hierarchy.

* You can place your primary/auxiliary methods freely in different places
  of your class hierarchy (decoupling particular partial actions in random
  ways...) -- the only requirement is that any class that contain primary
  and/or auxiliary method(s) should be decorated with the `aux()` class
  decorator and must be a new style-class (a direct or indirect `object`
  type subclass).

* Class-decorating with '@':

    @aux
    class SomeClass(object):
        ...

  ...is a Py2.6+/3.x syntax. The Py2.5 equivalent is:

    SomeClass = aux(SomeClass)  # below the class definition

  ...but using `AutoAuxBase` is probably more convenient (see below).

* If you don't use any special metaclasses you can make your life easier by
  using `AutoAuxBase` class as the root of your class hierarchy -- it will
  automatically decorate its ancestor classes with the `aux()` decorator
  (alternatively you can declare `AutoAuxMeta` class as the metaclass).

* `aux()` decorator adds some additional methods to the class. If the primary
  method name is `spam`, their names will be:

  * `spam_primary` -- the method you defined as spam (now `spam()` is
    a wrapper responsible for all that `around`/`before`/`primary`/`after`
    calls...),
  * `__spam`, `__spam_around`, `__spam_before`, `__spam_after` -- names of
    special helper methods (see below).

  You should consider these names as reserved and not define/set such class/
  /instance attributes in whole your class hierarchy (unless you really know
  what you do...). Please note that such a method will not be added if its
  name is already present in class __dict__ (which may lead to erroneous
  behaviour).

  Also, please note that `spam_primary()` and `__spam()` will not be added if
  the class doesn't contain the `spam()` primary method; and `__spam_around()`
  /`__spam_before()`/`__spam_after()` will not be added if the class doesn't
  contain the corresponding `spam_around()`/`spam_before()`/`spam_after()`
  aux method.

* The equivalents of CLOS's `call-next-method` are:

  * in primary methods: `self.__<primary method name>(<arguments>)`
  * in around aux methods: `self.__<primary method name>_around(<arguments>)`

* Unlike in CLOS, only the most specialized `before`/`after` aux methods are
  called automatically -- it's your responsibility to call those in
  superclasses, in the following way:

  * in `before` aux methods: `self.__<primary method name>_before(<arguments>)`
  * in `after` aux methods: `self.__<primary method name>_after(<arguments>)`

  (I believe this behaviour is not only more powerful but also more pythonic
  and more consistent with the `primary`/`around` behaviour).

* Because of Python private name mangling, all that `__*` method names are
  visible only within the particular class definition (thanks to that,
  behind the scenes, the Python standard `super()` function can be used
  properly without reduntant class name retyping). If you really need to
  access that methods from outside (in 99% of cases you won't) prefix their
  names with: '_' + the class name with any leading underscores stripped
  (see: http://docs.python.org/reference/expressions.html#atom-identifiers).

* Because private name mangling is in use, aux() decorator will raise
  ClassNameConflictError if it find that the name of the decorated class and
  any superclass name are -- after stripping leading underscores -- identical.

* All that `__*` methods make use of the standard `super()` function but they
  are a bit smarter: you can safely call them without concern whether
  appropriate methods exist in superclasses.

* `self.__<primary method name>_around(<arguments>)` works similarly to
  CLOS's `call-next-method` in `:around`-context -- i.e. it calls:

    <superclass>.<primary method name>_around(<arguments>)

  which *may* call (and return the result of) another:

    ...__<primary method name>_around(<arguments>)

  and so on... Finally, if there is no next `around` aux method to call,
  the following methods are called:

    self.<primary method name>_before(<arguments>)   # if the method exists
    self.<primary method name>_primary(<arguments>)  # may return something
    self.<primary method name>_after(<arguments>)    # if the method exists

  ...and then the result of the `*_primary()` method *may* be returned by
  consecutive (chained in the class hierarchy) `around` aux methods.

For information about CLOS auxiliary methods -- see:
http://www.aiai.ed.ac.uk/~jeff/clos-guide.html#meth-comb

For more information about this module -- read its source code.
"""

from __future__ import with_statement  # (Py2.5 needs this)

from functools import wraps
from inspect import getmro, isfunction

__all__ = (
    'ClassNameConflictError',
    'aux', 'primary',
    'AutoAuxBase', 'AutoAuxMeta',
)


#
# exceptions

class ClassNameConflictError(Exception):
    """
    aux()-ed class and superclass names conflict (after stripping leading '_').
    """

    def __str__(self):
        cls1, cls2 = self.args
        return (
            'Class names: %r and %r -- are identical after stripping leading '
            'underscores, which is forbidden when using aux/primary methods.'
            % (cls1.__name__, cls2.__name__))


#
# non-public stuff

_SUFFIXES = '_primary', '_before', '_after', '_around'


class _WrappedMethodPlaceholder(object):

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        raise TypeError('method placeholder is not callable '
                        '(forgot to apply aux() class decorator?)')


def _next_around(obj_around, self, basename, *args, **kwargs):
    # try to get and call next `around` aux method
    meth_around = getattr(obj_around, basename + '_around', None)
    if meth_around is not None:
        return meth_around(*args, **kwargs)
    else:
        # if there is no more `around` methods, get and call:
        # `before` aux method (it can call superclasses' `before` methods)
        meth_before = getattr(self, basename + '_before', None)
        if meth_before is not None:
            meth_before(*args, **kwargs)
        # primary method (it can call superclasses' primary methods)
        meth_primary = getattr(self, basename + '_primary')
        pri_result = meth_primary(*args, **kwargs)
        # `after` aux method (it can call superclasses' `after` methods)
        meth_after = getattr(self, basename + '_after', None)
        if meth_after is not None:
            meth_after(*args, **kwargs)
        return pri_result

def _provide_wrapper(cls, func, basename):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return _next_around(self, self, basename, *args, **kwargs)
    added_doc = '(See: %s%s() signature).' % (basename, '_primary')
    existing_doc = (getattr(wrapper, '__doc__', None) or '').rstrip()
    if existing_doc:
        wrapper.__doc__ = '%s\n\n%s' % (existing_doc, added_doc)
    else:
        wrapper.__doc__ = added_doc
    setattr(cls, basename, wrapper)

def _provide_primary(cls, func, basename):
    suffixed_name = basename + '_primary'
    func.__name__ = suffixed_name
    func.__doc__ = (
        'The actual method implementation '
        '(%s() is only a wrapper).' % basename)
    setattr(cls, suffixed_name, func)

def _provide_wrapped_primary(cls, func):
    basename = func.__name__
    _provide_wrapper(cls, func, basename)
    _provide_primary(cls, func, basename)

def _strip_and_check_cls_name(cls):
    cls_stripped_name = cls.__name__.lstrip('_')
    for supercls in getmro(cls):
        if (supercls is not cls and
              cls_stripped_name == supercls.__name__.lstrip('_')):
            raise ClassNameConflictError(supercls, cls)
    return cls_stripped_name

def _provide_call_next(cls, suffixed_name):
    cls_stripped_name = _strip_and_check_cls_name(cls)
    basename, qualifier = suffixed_name.rsplit('_', 1)
    cn_name = '_%s__%s' % (
        cls_stripped_name,
        (basename if qualifier == 'primary' else suffixed_name))
    if cn_name in vars(cls):
        return
    if qualifier == 'around':
        def call_next(self, *args, **kwargs):
            return _next_around(
                super(cls, self), self, basename, *args, **kwargs)
    else:
        def call_next(self, *args, **kwargs):
            super_meth = getattr(super(cls, self), suffixed_name, None)
            if super_meth is not None:
                return super_meth(*args, **kwargs)
    call_next.__name__ = cn_name
    setattr(cls, cn_name, call_next)


#
# actual decorators

def aux(cls):
    """Class decorator (for classes containing primary and/or aux methods)."""
    if not isinstance(cls, type):
        raise TypeError('%r is not a type' % cls)
    # wrap/rename primary methods
    for name, obj in tuple(vars(cls).items()):  # (Py2.x/3.x-compatibile way)
        if isinstance(obj, _WrappedMethodPlaceholder):
            _provide_wrapped_primary(cls, obj.func)
    # provide `call-next-method`-like methods
    for name, obj in tuple(vars(cls).items()):
        if isfunction(obj) and obj.__name__.endswith(_SUFFIXES):
            _provide_call_next(cls, obj.__name__)
    return cls

def primary(func):
    """Method decorator (for primary methods only)."""
    if not isfunction(func):
        raise TypeError('%r is not a function' % func)
    return _WrappedMethodPlaceholder(func)


#
# convenience classes (any of them can be used *optionally*...)

class AutoAuxMeta(type):
    """Convenience metaclass: aux()-decorates all classes created by it."""
    def __new__(mcs, name, bases, attr_dict):
        return aux(type.__new__(mcs, name, bases, attr_dict))

# (Py2.x/3.x-compatibile way to create class with custom metaclass)
AutoAuxBase = AutoAuxMeta('AutoAuxBase', (object,), {'__doc__':
    """Convenience base class: its metaclass is AutoAuxMeta."""})


#
# basic example

if __name__ == '__main__':

    import sys
    import time

    class TimedAction(AutoAuxBase):
        # note: AutoAuxBase automatically decorates your classes with aux()

        def action_before(self, *args, **kwargs):
            """Start action timer."""
            print('starting action timer...')
            self.start_time = time.time()

        def action_after(self, *args, **kwargs):
            """Stop action timer and report measured duration."""
            self.action_duration = time.time() - self.start_time
            print('action duration: %f' % self.action_duration)


    class FileContentAction(AutoAuxBase):

        def action_around(self, path):
            """Read file and pass its content on; report success or error."""
            print('opening file %r...' % path)
            try:
                with open(path) as f:
                    content = f.read()
            except EnvironmentError:
                print(sys.exc_info()[1])
            else:
                result = self.__action_around(path, content)
                print('file %r processed successfully' % path)
                return result


    class NewlinesCounter(FileContentAction, TimedAction):

        item_descr = 'newlines'

        @primary
        def action(self, path, content):
            """Get number of newlines in a given string."""
            return content.count('\n')

        def action_before(self, path, *args):
            """Print a message and go on..."""
            print('counting %s in file %r will start...' % (
                self.item_descr, path))
            self.__action_before(path, *args)

        def action_around(self, path):
            """Start operation with given file path. Finally, show summary."""
            result = self.__action_around(path)
            if result is not None:
                print('%s in file %r: %s\n' % (
                    self.item_descr, path, result))
            else:
                print('could not count %s in file %r\n' % (
                    self.item_descr, path))
            return result


    class SpacesAndNewlinesCounter(NewlinesCounter):

        item_descr = 'spaces and newlines'

        @primary
        def action(self, path, content):
            """Get number of spaces and newlines in a given string."""
            spaces = content.count(' ')
            newlines = self.__action(path, content)
            return spaces + newlines


    example_file_paths = __file__, 'spam/spam/spam/non-existent'

    nl_counter = NewlinesCounter()
    spc_nl_counter = SpacesAndNewlinesCounter()

    for path in example_file_paths:
        nl_counter.action(path)
        spc_nl_counter.action(path)
